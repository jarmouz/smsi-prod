"""Reprise de l'existant : dépôt en masse de documents (fichiers isolés ou ZIP).

Les fichiers sont déposés un par un (ou en ZIP) dans un espace temporaire, leurs
métadonnées sont lues (propriétés Office / OpenDocument / PDF, page de garde),
puis l'utilisateur corrige le tableau proposé avant de créer les documents.
Rien n'est créé dans la gestion documentaire avant la confirmation.
"""
import fcntl
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import time
import uuid
import zipfile
from contextlib import contextmanager
from datetime import date, datetime

from app.models import DocType
from app.services.importer import IMPORT_DIR, TTL, ImportError_, norm, match_table, match_user, parse_date

DOC_EXT = {"pdf", "doc", "docx", "docm", "odt", "rtf", "xls", "xlsx", "xlsm", "ods", "ppt", "pptx", "odp",
           "txt", "md", "csv", "vsdx"}
MAX_FILES = 500
MAX_FILE = 50 * 1024 * 1024
MAX_ZIP_TOTAL = 400 * 1024 * 1024
JUNK = re.compile(r"(^|/)(__MACOSX|\.DS_Store|Thumbs\.db|desktop\.ini|~\$[^/]*|\.~lock[^/]*)($|/)", re.I)


# --------------------------------------------------------------- Espace temporaire
def _dir(token):
    if not re.fullmatch(r"[0-9a-f]{32}", token or ""):
        raise ImportError_("Import introuvable.")
    return os.path.join(IMPORT_DIR, "docs-" + token)


def _cleanup():
    now = time.time()
    try:
        names = os.listdir(IMPORT_DIR)
    except OSError:
        return
    for f in names:
        p = os.path.join(IMPORT_DIR, f)
        try:
            if now - os.path.getmtime(p) > TTL:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        except OSError:
            pass


def create(org_id, user_id):
    os.makedirs(IMPORT_DIR, mode=0o700, exist_ok=True)
    _cleanup()
    token = uuid.uuid4().hex
    os.makedirs(_dir(token), mode=0o700)
    _write(token, {"org": org_id, "user": user_id, "items": [], "seq": 0})
    return token


def _manifest(token):
    return os.path.join(_dir(token), "manifest.json")


def _write(token, st):
    tmp = _manifest(token) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)
    os.replace(tmp, _manifest(token))


@contextmanager
def locked(token, org_id, user_id):
    """Manifeste verrouillé (dépôts parallèles) ; enregistré à la sortie du bloc."""
    d = _dir(token)
    if not os.path.isdir(d):
        raise ImportError_("Import expiré ou introuvable : recommencez le dépôt.")
    with open(os.path.join(d, ".lock"), "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        with open(_manifest(token), encoding="utf-8") as fh:
            st = json.load(fh)
        if st.get("org") != org_id or st.get("user") != user_id:
            raise ImportError_("Import introuvable.")
        yield st
        _write(token, st)


def load(token, org_id, user_id):
    try:
        with open(_manifest(token), encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        raise ImportError_("Import expiré ou introuvable : recommencez le dépôt.")
    if st.get("org") != org_id or st.get("user") != user_id:
        raise ImportError_("Import introuvable.")
    return st


def read_file(token, item):
    with open(os.path.join(_dir(token), item["stored"]), "rb") as fh:
        return fh.read()


def discard(token):
    try:
        shutil.rmtree(_dir(token))
    except (OSError, ImportError_):
        pass


# --------------------------------------------------------------- Dépôt
def ext_of(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def add_upload(st, token, filename, data):
    """Ajoute un fichier (ou le contenu d'un ZIP). -> (ajoutés, messages d'erreur)."""
    filename = os.path.basename((filename or "").replace("\\", "/")) or "fichier"
    if ext_of(filename) == "zip":
        return _add_zip(st, token, filename, data)
    err = _add_one(st, token, filename, filename, data)
    return (0, [err]) if err else (1, [])


def _add_zip(st, token, zipname, data):
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return 0, [f"{zipname} : archive ZIP illisible."]
    added, errors, total = 0, [], 0
    infos = [i for i in zf.infolist() if not i.is_dir() and not JUNK.search(i.filename)]
    for info in infos:
        # noms d'archives Windows : CP437 sans le drapeau UTF-8
        path = info.filename
        if not info.flag_bits & 0x800:
            try:
                raw = info.filename.encode("cp437")
                try:
                    path = raw.decode("utf-8")
                except UnicodeDecodeError:
                    path = raw.decode("cp850")         # Explorateur Windows français
            except UnicodeEncodeError:
                pass
        path = "/".join(p for p in path.replace("\\", "/").split("/") if p not in ("", ".", ".."))
        name = path.rsplit("/", 1)[-1]
        if ext_of(name) not in DOC_EXT:
            errors.append(f"{path} : type de fichier ignoré.")
            continue
        if info.file_size > MAX_FILE:
            errors.append(f"{path} : fichier trop volumineux (> 50 Mo).")
            continue
        total += info.file_size
        if total > MAX_ZIP_TOTAL:
            errors.append(f"{zipname} : contenu décompressé trop volumineux, archive tronquée.")
            break
        err = _add_one(st, token, name, f"{zipname}/{path}", zf.read(info))
        if err:
            errors.append(err)
        else:
            added += 1
    if not infos:
        errors.append(f"{zipname} : archive vide.")
    return added, errors


def _add_one(st, token, name, path, data):
    if ext_of(name) not in DOC_EXT:
        return f"{name} : type de fichier non pris en charge pour un document."
    if len(st["items"]) >= MAX_FILES:
        return f"{name} : limite de {MAX_FILES} fichiers par import atteinte."
    if not data:
        return f"{name} : fichier vide."
    sha = hashlib.sha256(data).hexdigest()
    dup = next((i for i in st["items"] if i["sha"] == sha), None)
    if dup:
        return f"{path} : contenu identique à {dup['path']} (ignoré)."
    st["seq"] += 1
    stored = f"{st['seq']:04d}.{ext_of(name)}"
    with open(os.path.join(_dir(token), stored), "wb") as fh:
        fh.write(data)
    st["items"].append({"id": st["seq"], "name": name[:300], "path": path[:500], "stored": stored,
                        "size": len(data), "sha": sha, "meta": extract(data, name, path)})
    return None


# --------------------------------------------------------------- Lecture des métadonnées
BAD_TITLES = re.compile(r"^(document\d*|doc\d*|untitled|sans titre|titre|title|microsoft word.*|presentation\d*|"
                        r"présentation\d*|classeur\d*|book\d*|diapositive.*|modele|modèle|template|page de garde)$", re.I)
VERSION_RE = re.compile(r"\b(?:version|vers\.|indice|révision|revision|rév\.)\s*(?:n°|no\.?)?\s*[:：]?\s*v?\s*"
                        r"(\d{1,2}(?:[.,]\d{1,2}){0,2})\b", re.I)
FILE_VERSION_RE = re.compile(r"(?:^|[\s_\-(])v(?:er(?:sion)?)?[\s._-]?(\d{1,2}(?:[._]\d{1,2}){0,2})(?=$|[\s_\-)])", re.I)
REF_RE = re.compile(r"\b(?:référence|reference|réf\.?|ref\.?|code(?: du document)?|identifiant)\s*(?:du document)?"
                    r"\s*[:：]\s*([A-Z0-9][A-Z0-9_./\-]{2,30})", re.I)
FILE_REF_RE = re.compile(r"^((?:[A-Z]{2,6}[-_]){1,3}\d{1,4})(?=[\s_\-.]|$)")
DATE_TXT = r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})"
APPROVAL_RE = re.compile(r"(?:date d['’]\s*approbation|approuvée?\s+le|date de validation|validée?\s+le|"
                         r"date de (?:mise en )?(?:application|vigueur)|en vigueur (?:le|depuis le)|"
                         r"date de diffusion|diffusée?\s+le)\s*[:：]?\s*" + DATE_TXT, re.I)
DATE_ANY = re.compile(r"\bdate\s*[:：]\s*" + DATE_TXT, re.I)
OWNER_RE = re.compile(r"(?:propriétaire|rédigée?\s+par|rédacteur|auteur|responsable(?: du document)?)\s*[:：]\s*"
                      r"([A-ZÀ-Ý][\w.'’\- ]{2,60}?)(?=\s{2,}|\s+:\s|\n|$|\s+(?:date|version|approuv|vérifi|valid))", re.I)
APPROVER_RE = re.compile(r"(?:approuvée?\s+par|validée?\s+par|approbateur)\s*[:：]\s*"
                         r"([A-ZÀ-Ý][\w.'’\- ]{2,60}?)(?=\s{2,}|\s+:\s|\n|$|\s+(?:date|version|le\b))", re.I)

TYPE_TABLE = [
    (DocType.POLITIQUE, ["politique", "politiques", "pssi", "charte", "policy", "directive", "principes",
                         "engagement de la direction", "manuel", "manuel smsi", "code de conduite"]),
    (DocType.ENREGISTREMENT, ["registre", "enregistrement", "rapport", "compte rendu", "cr", "pv",
                              "proces verbal", "formulaire", "fiche", "checklist", "check list", "journal",
                              "attestation", "bilan", "tableau de bord", "inventaire", "declaration d applicabilite",
                              "dda", "soa", "analyse de risque", "analyse des risques", "plan de traitement",
                              "revue de direction", "audit", "liste", "matrice", "evaluation", "preuve", "release",
                              "emargement", "convocation"]),
    (DocType.PROCEDURE, ["procedure", "procedures", "processus", "mode operatoire", "instruction", "instructions",
                         "guide", "plan", "pca", "pra", "pci", "methodologie", "methode", "standard", "norme interne",
                         "regle", "regles", "consigne", "consignes", "process", "playbook", "runbook",
                         "fiche reflexe", "gestion des"]),
]


def _xml_text(xml):
    """Texte brut d'un XML Office : un paragraphe par ligne, cellules séparées par « | »."""
    xml = re.sub(r"</w:p>|</text:p>|</text:h>|</a:p>", "\n", xml)
    xml = re.sub(r"</w:tc>|</table:table-cell>", " | ", xml)
    xml = re.sub(r"<w:tab/>|<text:tab/>", " ", xml)
    txt = re.sub(r"<[^>]+>", "", xml)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'")):
        txt = txt.replace(a, b)
    return "\n".join(re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in txt.split("\n") if ln.strip())


def _zip_member(zf, name, limit=6 * 1024 * 1024):
    try:
        info = zf.getinfo(name)
    except KeyError:
        return None
    if info.file_size > limit:
        with zf.open(info) as fh:
            return fh.read(limit).decode("utf-8", "ignore")
    return zf.read(info).decode("utf-8", "ignore")


def _tag(xml, tag):
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml or "", re.S)
    return _xml_text(m.group(1)).strip() if m else ""


def _ooxml(data, ext):
    meta, text, heading = {}, "", ""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return meta, text, heading
    core = _zip_member(zf, "docProps/core.xml") or ""
    meta["title"] = _tag(core, "dc:title")
    meta["author"] = _tag(core, "dc:creator") or _tag(core, "cp:lastModifiedBy")
    meta["subject"] = _tag(core, "dc:subject")
    meta["modified"] = _tag(core, "dcterms:modified")[:10] or _tag(core, "dcterms:created")[:10]
    custom = _zip_member(zf, "docProps/custom.xml") or ""
    for m in re.finditer(r'<property[^>]*name="([^"]+)"[^>]*>(.*?)</property>', custom, re.S):
        key, val = norm(m.group(1)), _xml_text(m.group(2)).strip()
        if key in ("version", "indice", "revision", "numero de version") and val:
            meta["version_prop"] = val
        elif key in ("reference", "ref", "code", "identifiant", "code document") and val:
            meta["ref_prop"] = val
        elif key in ("proprietaire", "owner", "responsable", "redacteur") and val:
            meta["owner_prop"] = val
    if ext in ("docx", "docm"):
        doc = _zip_member(zf, "word/document.xml") or ""
        parts = [_zip_member(zf, n) or "" for n in zf.namelist() if re.match(r"word/header\d*\.xml$", n)]
        # titre : premier paragraphe en style Titre / Title / Heading 1
        for p in re.findall(r"<w:p[ >].*?</w:p>", doc[:400000], re.S)[:80]:
            if re.search(r'<w:pStyle w:val="(Title|Titre|Heading1|Titre1|Titredudocument|Couverture)"', p, re.I):
                heading = _xml_text(p).strip()
                if heading:
                    break
        text = _xml_text("".join(parts)) + "\n" + _xml_text(doc[:600000])
    elif ext in ("pptx",):
        slide = _zip_member(zf, "ppt/slides/slide1.xml") or ""
        text = _xml_text(slide)
        heading = text.split("\n", 1)[0] if text else ""
    elif ext in ("xlsx", "xlsm"):
        text = _xml_text((_zip_member(zf, "xl/sharedStrings.xml") or "")[:200000])
    return meta, text, heading


def _odf(data):
    meta, text, heading = {}, "", ""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return meta, text, heading
    m = _zip_member(zf, "meta.xml") or ""
    meta["title"] = _tag(m, "dc:title")
    meta["author"] = _tag(m, "meta:initial-creator") or _tag(m, "dc:creator")
    meta["modified"] = _tag(m, "dc:date")[:10]
    content = _zip_member(zf, "content.xml") or ""
    hm = re.search(r'<text:(?:h|p)[^>]*text:style-name="[^"]*(?:Title|Titre|Heading_20_1)[^"]*"[^>]*>(.*?)</text:(?:h|p)>', content, re.S)
    heading = _xml_text(hm.group(1)) if hm else ""
    text = _xml_text(content[:600000])
    return meta, text, heading


def _pdf_string(raw):
    if raw.startswith(b"<"):
        try:
            raw = bytes.fromhex(re.sub(rb"[^0-9a-fA-F]", b"", raw[1:-1]).decode())
        except ValueError:
            return ""
    else:
        raw = raw[1:-1]
        raw = re.sub(rb"\\([nrtbf()\\])", lambda m: {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"",
                                                      b"f": b"", b"(": b"(", b")": b")", b"\\": b"\\"}[m.group(1)], raw)
        raw = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8) & 0xFF]), raw)
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", "ignore")
    return raw.decode("latin-1", "ignore")


def _pdf(data):
    """Dictionnaire d'information du PDF (non compressé dans la grande majorité des cas)."""
    meta = {}
    for key, out in ((b"Title", "title"), (b"Author", "author"), (b"Subject", "subject")):
        m = re.search(rb"/" + key + rb"\s*(\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>)", data)
        if m:
            meta[out] = _pdf_string(m.group(1)).strip()
    m = re.search(rb"/ModDate\s*\(D:(\d{8})", data) or re.search(rb"/CreationDate\s*\(D:(\d{8})", data)
    if m:
        d = m.group(1).decode()
        meta["modified"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return meta, "", ""


def _clean_title(t):
    t = re.sub(r"\s+", " ", (t or "")).strip(" -_|:")
    t = re.sub(r"^microsoft (word|excel|powerpoint) - ", "", t, flags=re.I)
    t = re.sub(r"\.(docx?|pdf|xlsx?|pptx?|odt)$", "", t, flags=re.I)
    return "" if not t or BAD_TITLES.match(t) or len(t) < 3 else t[:300]


def _title_from_name(name):
    base = name.rsplit(".", 1)[0]
    base = FILE_VERSION_RE.sub(" ", base)
    base = re.sub(r"[_]+", " ", base)
    base = re.sub(r"^\s*\d{1,3}\s*[-.)]?\s+", "", base)               # « 02 - … » « 3. … »
    base = re.sub(r"\s*\b(final|vf|def|definitif|signe|signée?)\b\s*$", "", base, flags=re.I)
    base = re.sub(r"\s+", " ", base).strip(" -.")
    return base[:1].upper() + base[1:] if base else name


def extract(data, name, path=""):
    ext = ext_of(name)
    if ext in ("docx", "docm", "xlsx", "xlsm", "pptx", "vsdx"):
        meta, text, heading = _ooxml(data, ext)
    elif ext in ("odt", "ods", "odp"):
        meta, text, heading = _odf(data)
    elif ext == "pdf":
        meta, text, heading = _pdf(data)
    elif ext in ("txt", "md"):
        text = data[:200000].decode("utf-8", "ignore")
        meta, heading = {}, (text.strip().split("\n", 1)[0].lstrip("# ").strip() if text.strip() else "")
    else:
        meta, text, heading = {}, "", ""
    # page de garde et cartouche : début du document ; « Version | 3.2 » (cellules) -> « Version : 3.2 »
    head = re.sub(r"\s*[:：]?\s*\|\s*", " : ", text[:8000])
    out = {"source": {}}

    for cand, src in ((meta.get("title"), "propriétés du fichier"), (heading, "titre du document")):
        t = _clean_title(cand)
        if t:
            out["title"], out["source"]["title"] = t, src
            break
    else:
        out["title"], out["source"]["title"] = _title_from_name(name), "nom du fichier"

    m = VERSION_RE.search(head)
    if meta.get("version_prop"):
        out["version"], out["source"]["version"] = meta["version_prop"][:16], "propriétés du fichier"
    elif m:
        out["version"], out["source"]["version"] = m.group(1).replace(",", ".")[:16], "page de garde"
    else:
        fm = FILE_VERSION_RE.search(name.rsplit(".", 1)[0])
        if fm:
            out["version"], out["source"]["version"] = fm.group(1).replace("_", ".")[:16], "nom du fichier"
    v = out.get("version", "")
    if v and "." not in v and v.isdigit():
        out["version"] = f"{int(v)}.0"

    m = REF_RE.search(head)
    fm = FILE_REF_RE.match(name)
    if meta.get("ref_prop"):
        out["ref"], out["source"]["ref"] = meta["ref_prop"][:32], "propriétés du fichier"
    elif m and re.search(r"\d", m.group(1)):
        out["ref"], out["source"]["ref"] = m.group(1).rstrip(".-/")[:32], "page de garde"
    elif fm:
        out["ref"], out["source"]["ref"] = fm.group(1).replace("_", "-")[:32], "nom du fichier"

    m = APPROVAL_RE.search(head)
    d = parse_date(m.group(1)) if m else None
    if d:
        out["approved"], out["source"]["approved"] = d.isoformat(), "page de garde"
    else:
        m = DATE_ANY.search(head)
        d = parse_date(m.group(1)) if m else None
        if d:
            out["approved"], out["source"]["approved"] = d.isoformat(), "date du cartouche"
        elif meta.get("modified"):
            d = parse_date(meta["modified"])
            if d:
                out["approved"], out["source"]["approved"] = d.isoformat(), "dernière modification du fichier"
    if out.get("approved") and out["approved"] > date.today().isoformat():
        out.pop("approved")

    m = OWNER_RE.search(head)
    out["owner_hint"] = (meta.get("owner_prop") or (m.group(1).strip() if m else "") or meta.get("author") or "")[:80]
    m = APPROVER_RE.search(head)
    if m:
        out["approver_hint"] = m.group(1).strip()[:80]

    hay = norm(" ".join([out["title"], path, meta.get("subject", "")]))
    out["doc_type"] = (match_table(hay, TYPE_TABLE) or DocType.AUTRE).value
    return out


# --------------------------------------------------------------- Proposition
def proposal(st, users, existing_docs):
    """Lignes du tableau à valider : valeurs proposées + doublons détectés."""
    by_title = {norm(d.title): d for d in existing_docs}
    by_ref = {d.ref.lower(): d for d in existing_docs}
    rows = []
    for it in st["items"]:
        m = dict(it["meta"])
        ai = it.get("ai") or {}
        for k in ("title", "doc_type", "ref", "version", "approved", "owner_hint"):   # l'IA complète / corrige
            if ai.get(k):
                m[k] = ai[k]
        ov = st.get("edits", {}).get(str(it["id"]), {})
        owner = match_user(m.get("owner_hint"), users) if m.get("owner_hint") else None
        dup = by_ref.get((m.get("ref") or "").lower()) or by_title.get(norm(m["title"]))
        rows.append({
            "id": it["id"], "name": it["name"], "path": it["path"], "size": it["size"],
            "title": ov.get("title", m["title"]), "ref": ov.get("ref", m.get("ref", "")),
            "doc_type": ov.get("doc_type", m["doc_type"]), "version": ov.get("version", m.get("version", "1.0")),
            "owner_id": ov.get("owner_id", owner.id if owner else None),
            "approved": ov.get("approved", m.get("approved", "")),
            "include": ov.get("include", dup is None),
            "controls": ov.get("controls", ai.get("controls", "")), "summary": ov.get("summary", ai.get("summary", "")),
            "ai": bool(ai), "source": m.get("source", {}), "owner_hint": m.get("owner_hint", ""),
            "approver_hint": m.get("approver_hint", ""), "dup": dup,
        })
    return rows


# --------------------------------------------------------------- Création
def create_documents(st, token, user, budget=40):
    """Crée les documents retenus (un document + son fichier par ligne).
    Mode « APPROUVE » (RSSI) : reprise d'un document déjà en vigueur, enregistré comme
    version approuvée avec la date d'approbation d'origine. Le dépôt vers le stockage (Nextcloud)
    prend environ une seconde par fichier : on s'arrête après `budget` secondes, les lignes
    restantes sont traitées par l'appel suivant. -> (réfs créées, erreurs, lignes restantes)."""
    from datetime import timedelta
    from app.extensions import db
    from app.models import Document, DocumentVersion, DocStatus, User
    from app.services import attachments as att_svc
    from app.services.importer import RefAllocator

    opts = st.get("options", {})
    approve = opts.get("mode") == "APPROUVE"
    months = int(opts.get("review_months", 12))
    users = User.query.all()
    alloc = RefAllocator([d.ref for d in Document.query.all()], "DOC", width=3, yearly=False)
    rows = {r["id"]: r for r in proposal(st, users, Document.query.all())}
    created, errors, done_ids = [], [], []
    today = date.today()
    start = time.time()
    todo = [it for it in st["items"] if rows[it["id"]]["include"]]
    for n, it in enumerate(todo):
        if n and time.time() - start > budget:
            break
        r = rows[it["id"]]
        done_ids.append(it["id"])
        approved = parse_date(r["approved"]) if r["approved"] else None
        if approved and approved > today:
            approved = None
        ref = alloc.take(r["ref"] or None)
        note = f"Repris de l'existant : « {it['path']} » (dépôt du {today:%d/%m/%Y})."
        if r.get("summary"):
            note += f"\nRésumé : {r['summary']}"
        if r.get("controls"):
            note += f"\nMesures de l'Annexe A concernées : {r['controls']}"
        d = Document(ref=ref, title=r["title"], doc_type=DocType(r["doc_type"]), version=r["version"] or "1.0",
                     owner_id=r["owner_id"] or None, note=note, status=DocStatus.BROUILLON)
        if approve:
            when = approved or today
            d.status = DocStatus.APPROUVE
            d.approved_at = when
            d.approved_by_id = user.id
            d.next_review_at = when + timedelta(days=round(months * 30.44))
            summary = "Reprise de l'existant : version en vigueur avant l'adoption de la plateforme"
            if approved:
                summary += f", approuvée le {approved:%d/%m/%Y}"
            if r.get("approver_hint"):
                summary += f" par {r['approver_hint']}"
            d.change_summary = summary + "."
        db.session.add(d)
        db.session.flush()
        if approve:
            db.session.add(DocumentVersion(document_id=d.id, version=d.version, change_summary=d.change_summary,
                                           approved_by_id=user.id,
                                           approved_at=datetime.combine(d.approved_at, datetime.min.time())))
        att, msg = att_svc.save_data(read_file(token, it), it["name"], mimetypes.guess_type(it["name"])[0], "document", d.id, user, commit=False)
        if att is None:
            db.session.rollback()
            alloc.taken.discard(ref.lower())
            errors.append(f"{it['name']} : {msg} Document non créé.")
            continue
        db.session.commit()
        created.append(ref)
    with locked(token, st["org"], st["user"]) as stl:
        # les lignes traitées (créées ou en échec) sortent de l'espace de dépôt
        stl["items"] = [i for i in stl["items"] if i["id"] not in done_ids]
        stl["created"] = stl.get("created", []) + created
        stl["failed"] = stl.get("failed", []) + errors
        remaining = sum(1 for i in stl["items"] if rows.get(i["id"], {}).get("include"))
    return created, errors, remaining
