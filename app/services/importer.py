"""Reprise de l'existant : import de tableurs (CSV / Excel) en trois étapes.

1. lecture du fichier (toutes les feuilles, détection de la ligne d'en-têtes) ;
2. correspondance colonnes du fichier -> champs SMSI (proposée automatiquement,
   ajustable par l'utilisateur) ;
3. aperçu ligne par ligne (création / mise à jour / inchangé / erreur) puis
   application en une seule transaction.

Le fichier lu est conservé côté serveur (JSON dans IMPORT_DIR) entre les étapes :
le navigateur ne transporte qu'un jeton. Rien n'est écrit en base avant la
confirmation, et l'application recalcule l'aperçu à partir du fichier stocké.

Les types importables sont décrits dans SPECS ; chacun fournit ses champs
(avec synonymes d'en-têtes) et ses fonctions plan() / apply().
"""
import csv
import difflib
import io
import json
import os
import re
import time
import unicodedata
import uuid
from datetime import date, datetime

from app.extensions import db

IMPORT_DIR = os.environ.get("IMPORT_DIR", "/tmp/smsi-imports")
MAX_ROWS = 5000
TTL = 24 * 3600


# --------------------------------------------------------------- Normalisation
def norm(s):
    """Minuscules, sans accents ni ponctuation, espaces simples."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9%]+", " ", s.lower()).strip()


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, datetime):
        v = v.date()
    if isinstance(v, date):
        return v.isoformat()
    return str(v).strip()


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# --------------------------------------------------------------- Lecture
class ImportError_(Exception):
    pass


def read_file(file_storage):
    """-> {nom_feuille: [[cellule, ...], ...]} (chaînes)."""
    name = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if name.endswith(".xls"):
        raise ImportError_("Ancien format Excel (.xls) : enregistrez le fichier en .xlsx puis réessayez.")
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        except Exception as e:  # noqa: BLE001
            raise ImportError_(f"Fichier Excel illisible ({e.__class__.__name__}).")
        sheets = {}
        for ws in wb.worksheets:
            rows = []
            for r in ws.iter_rows(values_only=True):
                rows.append([_cell(v) for v in r])
                if len(rows) > MAX_ROWS + 50:
                    break
            sheets[ws.title] = _trim(rows)
        wb.close()
        sheets = {k: v for k, v in sheets.items() if v}
        if not sheets:
            raise ImportError_("Le classeur est vide.")
        return sheets
    if name.endswith((".csv", ".txt")):
        for enc in ("utf-8-sig", "cp1252"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sample = text[:4000]
        delim = max((";", ",", "\t"), key=sample.count)
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), delimiter=delim)]
        rows = _trim(rows[:MAX_ROWS + 50])
        if not rows:
            raise ImportError_("Le fichier CSV est vide.")
        return {"CSV": rows}
    raise ImportError_("Format non pris en charge : utilisez un fichier .xlsx ou .csv.")


def _trim(rows):
    """Supprime les lignes et colonnes entièrement vides en fin de tableau."""
    while rows and not any(rows[-1]):
        rows.pop()
    width = max((max((i + 1 for i, c in enumerate(r) if c), default=0) for r in rows), default=0)
    return [(r + [""] * width)[:width] for r in rows]


def detect_header(rows, spec):
    """Ligne d'en-têtes = celle (parmi les 20 premières) qui ressemble le plus
    aux en-têtes attendus ; à défaut la première ligne avec 2 cellules remplies."""
    best, best_score = None, 0
    for i, r in enumerate(rows[:20]):
        filled = [c for c in r if c]
        if len(filled) < 2:
            continue
        score = sum(1 for c in filled if _header_score(c, spec)[1] > 0)
        if score > best_score:
            best, best_score = i, score
    if best is not None:
        return best
    for i, r in enumerate(rows[:20]):
        if sum(1 for c in r if c) >= 2:
            return i
    return 0


def _field_score(header, f):
    """Ressemblance entre un en-tête et un champ : 3 = identique, 2 = contenu."""
    h = norm(header)
    if not h:
        return 0
    best = 0
    for syn in [f["label"]] + f["synonyms"]:
        s = norm(syn)
        if h == s:
            return 3
        if len(s) > 2 and re.search(rf"(^| ){re.escape(s)}( |$)", h):
            best = 2
    return best


def _header_score(header, spec):
    """(clé du champ, score) le plus probable pour un en-tête de colonne."""
    best = (None, 0)
    for f in spec["fields"]:
        sc = _field_score(header, f)
        if sc > best[1]:
            best = (f["key"], sc)
    return best


def auto_map(headers, spec):
    """-> {clé_champ: index_colonne} ; chaque colonne n'est utilisée qu'une fois.
    Affectation gloutonne sur toutes les paires (colonne, champ) : une colonne
    « Contrôle » peut ainsi aller à l'intitulé si la référence est déjà prise."""
    cands = []
    for i, h in enumerate(headers):
        for order, f in enumerate(spec["fields"]):
            sc = _field_score(h, f)
            if sc:
                cands.append((-sc, i, order, f["key"]))
    mapping, used = {}, set()
    for _, i, _, key in sorted(cands):
        if key not in mapping and i not in used:
            mapping[key] = i
            used.add(i)
    return mapping


# --------------------------------------------------------------- Stockage temporaire
def _path(token):
    if not re.fullmatch(r"[0-9a-f]{32}", token or ""):
        raise ImportError_("Import introuvable.")
    return os.path.join(IMPORT_DIR, token + ".json")


def save(state):
    os.makedirs(IMPORT_DIR, mode=0o700, exist_ok=True)
    now = time.time()
    for f in os.listdir(IMPORT_DIR):        # ménage des imports abandonnés
        p = os.path.join(IMPORT_DIR, f)
        try:
            if now - os.path.getmtime(p) > TTL:
                os.remove(p)
        except OSError:
            pass
    token = state.get("token") or uuid.uuid4().hex
    state["token"] = token
    with open(_path(token), "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False)
    return token


def load(token, org_id, user_id, kind):
    try:
        with open(_path(token), encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        raise ImportError_("Import expiré ou introuvable : rechargez le fichier.")
    if st.get("org") != org_id or st.get("user") != user_id or st.get("kind") != kind:
        raise ImportError_("Import introuvable.")
    return st


def discard(token):
    try:
        os.remove(_path(token))
    except (OSError, ImportError_):
        pass


def table(st):
    """(en-têtes, lignes de données) de la feuille courante."""
    rows = st["sheets"][st["sheet"]]
    h = st["header_row"]
    return rows[h] if h < len(rows) else [], rows[h + 1:]


def samples(st, limit=3):
    headers, data = table(st)
    out = []
    for i in range(len(headers)):
        vals = []
        for r in data:
            if i < len(r) and r[i] and r[i] not in vals:
                vals.append(r[i][:60])
            if len(vals) >= limit:
                break
        out.append(vals)
    return out


# --------------------------------------------------------------- Conversions
def match_table(value, table_, default=None):
    """table_ = [(valeur, [synonymes normalisés...]), ...] ; égalité d'abord,
    puis synonyme contenu dans la valeur (dans l'ordre de la table)."""
    v = norm(value)
    if not v:
        return default
    for val, syns in table_:
        if v in syns:
            return val
    vs = _singular(v)
    for val, syns in table_:
        for s in syns:
            if len(s) > 3 and re.search(rf"(^| ){re.escape(_singular(s))}( |$)", vs):
                return val
    return default


def _singular(text):
    """« ordinateurs portables » -> « ordinateur portable » (pluriels simples)."""
    return " ".join(w[:-1] if len(w) > 3 and w[-1] in "sx" else w for w in text.split())


BOOL_TABLE = [
    (False, ["non", "n", "no", "0", "false", "faux", "exclu", "exclue", "exclus", "na", "n a", "non applicable",
             "non retenu", "non retenue", "not applicable", "excluded", "hors perimetre", "hors scope"]),
    (True, ["oui", "o", "yes", "y", "x", "1", "true", "vrai", "applicable", "inclus", "incluse", "inclue",
            "retenu", "retenue", "selectionne", "selectionnee", "included", "dans le perimetre"]),
]


def parse_bool(value):
    v = (value or "").strip()
    if v in ("✓", "✔", "☑", "☒"):
        return True
    return match_table(v, BOOL_TABLE)


def match_user(value, users):
    """Utilisateur par e-mail, nom exact, ou nom unique contenant la valeur."""
    v = norm(value)
    if not v:
        return None
    raw = (value or "").strip().lower()
    for u in users:
        if u.email.lower() == raw or norm(u.name) == v:
            return u
    hits = [u for u in users if v in norm(u.name) or (len(norm(u.name)) > 3 and norm(u.name) in v)]
    return hits[0] if len(hits) == 1 else None


# --------------------------------------------------------------- DdA
from app.models import (Control, ControlStatus, Asset, AssetCategory, Classification,  # noqa: E402
                        AssetStatus, User)

STATUS_TABLE = [
    (ControlStatus.NON_APPLICABLE, ["non applicable", "na", "n a", "not applicable", "exclu", "exclue"]),
    (ControlStatus.NON_DEMARRE, ["non demarre", "non demarree", "a faire", "a mettre en place", "a mettre en oeuvre",
                                 "non implemente", "non implementee", "non mis en oeuvre", "non mise en oeuvre",
                                 "non realise", "absent", "absente", "inexistant", "non", "0", "0%",
                                 "not started", "not implemented", "todo", "to do", "non conforme", "aucun", "nok"]),
    (ControlStatus.EN_COURS, ["en cours", "partiel", "partielle", "partiellement", "partiellement implemente",
                              "partiellement mis en oeuvre", "planifie", "planifiee", "a ameliorer", "en projet",
                              "in progress", "partial", "partially implemented", "planned", "en deploiement",
                              "partiellement conforme", "initie", "initialise", "demarre"]),
    (ControlStatus.IMPLEMENTE, ["implemente", "implementee", "mis en oeuvre", "mise en oeuvre", "en place", "fait",
                                "realise", "realisee", "conforme", "oui", "ok", "termine", "terminee", "done",
                                "implemented", "operationnel", "operationnelle", "en production", "100%", "100",
                                "applique", "appliquee", "deploye", "deployee"]),
]

REF_RE = re.compile(r"(?<![\d.])(?:a\s*\.?\s*)?(\d{1,2})\s*[.\-]\s*(\d{1,2})(?:\s*[.\-]\s*(\d{1,2}))?(?![\d.])", re.I)


def parse_status(value):
    v = norm(value)
    m = re.fullmatch(r"(\d{1,3})(?: ?%)?", v)
    if m:   # taux de mise en œuvre
        n = int(m.group(1))
        return ControlStatus.IMPLEMENTE if n >= 100 else (ControlStatus.NON_DEMARRE if n == 0 else ControlStatus.EN_COURS)
    return match_table(value, STATUS_TABLE)


def parse_ref(value):
    """'A.5.1', '5.1', 'A 5.1 - Politiques…' -> ('5.1', None) ; 'A.9.2.3' -> (None, 'A.9.2.3')."""
    m = REF_RE.search(value or "")
    if not m:
        return None, None
    a, b, c = m.groups()
    if c is not None:
        return None, f"A.{int(a)}.{int(b)}.{int(c)}"
    return f"{int(a)}.{int(b)}", None


def _title_match(title, controls):
    t = norm(title)
    if len(t) < 6:
        return None, 0
    best, score = None, 0
    for c in controls:
        r = difflib.SequenceMatcher(None, t, norm(c.title)).ratio()
        if r > score:
            best, score = c, r
    return best, score


# Correspondance ISO/IEC 27001:2013 -> 2022 (ISO/IEC 27002:2022, annexe B, tableau B.2).
# 114 mesures 2013 -> 93 mesures 2022 ; A.18.2.3 alimente deux mesures.
MAP_2013 = {
    "5.1.1": ["5.1"], "5.1.2": ["5.1"],
    "6.1.1": ["5.2"], "6.1.2": ["5.3"], "6.1.3": ["5.5"], "6.1.4": ["5.6"], "6.1.5": ["5.8"],
    "6.2.1": ["8.1"], "6.2.2": ["6.7"],
    "7.1.1": ["6.1"], "7.1.2": ["6.2"], "7.2.1": ["5.4"], "7.2.2": ["6.3"], "7.2.3": ["6.4"], "7.3.1": ["6.5"],
    "8.1.1": ["5.9"], "8.1.2": ["5.9"], "8.1.3": ["5.10"], "8.1.4": ["5.11"], "8.2.1": ["5.12"], "8.2.2": ["5.13"],
    "8.2.3": ["5.10"], "8.3.1": ["7.10"], "8.3.2": ["7.10"], "8.3.3": ["7.10"],
    "9.1.1": ["5.15"], "9.1.2": ["5.15"], "9.2.1": ["5.16"], "9.2.2": ["5.18"], "9.2.3": ["8.2"], "9.2.4": ["5.17"],
    "9.2.5": ["5.18"], "9.2.6": ["5.18"], "9.3.1": ["5.17"], "9.4.1": ["8.3"], "9.4.2": ["8.5"], "9.4.3": ["5.17"],
    "9.4.4": ["8.18"], "9.4.5": ["8.4"],
    "10.1.1": ["8.24"], "10.1.2": ["8.24"],
    "11.1.1": ["7.1"], "11.1.2": ["7.2"], "11.1.3": ["7.3"], "11.1.4": ["7.5"], "11.1.5": ["7.6"], "11.1.6": ["7.2"],
    "11.2.1": ["7.8"], "11.2.2": ["7.11"], "11.2.3": ["7.12"], "11.2.4": ["7.13"], "11.2.5": ["7.10"],
    "11.2.6": ["7.9"], "11.2.7": ["7.14"], "11.2.8": ["8.1"], "11.2.9": ["7.7"],
    "12.1.1": ["5.37"], "12.1.2": ["8.32"], "12.1.3": ["8.6"], "12.1.4": ["8.31"], "12.2.1": ["8.7"],
    "12.3.1": ["8.13"], "12.4.1": ["8.15"], "12.4.2": ["8.15"], "12.4.3": ["8.15"], "12.4.4": ["8.17"],
    "12.5.1": ["8.19"], "12.6.1": ["8.8"], "12.6.2": ["8.19"], "12.7.1": ["8.34"],
    "13.1.1": ["8.20"], "13.1.2": ["8.21"], "13.1.3": ["8.22"], "13.2.1": ["5.14"], "13.2.2": ["5.14"],
    "13.2.3": ["5.14"], "13.2.4": ["6.6"],
    "14.1.1": ["5.8"], "14.1.2": ["8.26"], "14.1.3": ["8.26"], "14.2.1": ["8.25"], "14.2.2": ["8.32"],
    "14.2.3": ["8.32"], "14.2.4": ["8.32"], "14.2.5": ["8.27"], "14.2.6": ["8.31"], "14.2.7": ["8.30"],
    "14.2.8": ["8.29"], "14.2.9": ["8.29"], "14.3.1": ["8.33"],
    "15.1.1": ["5.19"], "15.1.2": ["5.20"], "15.1.3": ["5.21"], "15.2.1": ["5.22"], "15.2.2": ["5.22"],
    "16.1.1": ["5.24"], "16.1.2": ["6.8"], "16.1.3": ["6.8"], "16.1.4": ["5.25"], "16.1.5": ["5.26"],
    "16.1.6": ["5.27"], "16.1.7": ["5.28"],
    "17.1.1": ["5.29"], "17.1.2": ["5.29"], "17.1.3": ["5.29"], "17.2.1": ["8.14"],
    "18.1.1": ["5.31"], "18.1.2": ["5.32"], "18.1.3": ["5.33"], "18.1.4": ["5.34"], "18.1.5": ["5.31"],
    "18.2.1": ["5.35"], "18.2.2": ["5.36"], "18.2.3": ["5.36", "8.8"],
}
# Mesures créées en 2022, sans équivalent 2013 : à évaluer après une conversion.
NEW_2022 = ["5.7", "5.23", "5.30", "7.4", "8.9", "8.10", "8.11", "8.12", "8.16", "8.23", "8.28"]

_PROGRESS = {ControlStatus.NON_DEMARRE: 0, ControlStatus.EN_COURS: 1, ControlStatus.IMPLEMENTE: 2}


def _soa_values(g, users):
    """Valeurs DdA d'une ligne (indépendantes de la mesure cible) + avertissements."""
    v, warns = {}, []
    if g("applicable", "").strip():
        b = parse_bool(g("applicable"))
        if b is None:
            warns.append(f"Applicabilité « {g('applicable')} » non reconnue : ignorée.")
        else:
            v["applicable"] = b
    if g("status", "").strip():
        s = parse_status(g("status"))
        if s is None:
            warns.append(f"Statut « {g('status')} » non reconnu : ignoré.")
        else:
            v["status"] = s
            if s == ControlStatus.NON_APPLICABLE and "applicable" not in v:
                v["applicable"] = False
    for k in ("justification", "implementation"):
        if g(k, "").strip():
            v[k] = g(k).strip()
    if g("owner", "").strip():
        u = match_user(g("owner"), users)
        if u:
            v["owner_id"] = u.id
        else:
            warns.append(f"Responsable « {g('owner')} » introuvable parmi les utilisateurs : laissé tel quel.")
    return v, warns


def _merge_2013(entries):
    """Fusionne plusieurs lignes 2013 qui alimentent la même mesure 2022.
    Applicable si au moins une source l'est ; statut : Implémenté seulement si toutes
    les sources applicables le sont, Non démarré si aucune n'a commencé, sinon En cours."""
    v, warns = {}, []
    apps = [e["values"]["applicable"] for e in entries if "applicable" in e["values"]]
    if apps:
        v["applicable"] = any(apps)
    sts = [e["values"]["status"] for e in entries
           if e["values"].get("status") in _PROGRESS and e["values"].get("applicable", True)]
    if sts:
        lo, hi = min(_PROGRESS[s] for s in sts), max(_PROGRESS[s] for s in sts)
        v["status"] = sts[0] if lo == hi else ControlStatus.EN_COURS
        if lo != hi:
            warns.append("Statuts différents selon les mesures 2013 d'origine : « En cours » retenu.")
    elif v.get("applicable") is False or any(e["values"].get("status") == ControlStatus.NON_APPLICABLE for e in entries):
        v.setdefault("applicable", False)
    for k in ("justification", "implementation"):
        texts = [(e["src"], e["values"][k]) for e in entries if e["values"].get(k)]
        distinct = list(dict.fromkeys(t for _, t in texts))
        if len(distinct) == 1:
            v[k] = distinct[0]
        elif distinct:
            seen = set()
            v[k] = "\n".join(f"[{src}] {t}" for src, t in texts if not (t in seen or seen.add(t)))
    owners = list(dict.fromkeys(e["values"]["owner_id"] for e in entries if e["values"].get("owner_id")))
    if owners:
        v["owner_id"] = owners[0]
        if len(owners) > 1:
            warns.append("Responsables différents selon les mesures 2013 d'origine : le premier est retenu.")
    return v, warns


def _soa_plan(rows, ctx):
    controls = Control.query.all()
    by_ref = {c.ref: c for c in controls}
    users = ctx["users"]
    out, entries = [], []

    # 1) identification de la (des) mesure(s) 2022 visée(s) par chaque ligne
    for line, row in rows:
        g = row.get
        if not any((v or "").strip() for v in row.values()):
            continue
        ref, ref2013 = parse_ref(g("ref"))
        title = (g("title") or "").strip()
        if not ref and not ref2013 and title:      # référence parfois dans la colonne intitulé
            ref, ref2013 = parse_ref(title[:12])
        values, warns = _soa_values(g, users)
        if ref2013:
            key = ref2013[2:]
            targets = [by_ref[r] for r in MAP_2013.get(key, []) if r in by_ref]
            if not targets:
                out.append({"line": line, "label": (g("ref") or title)[:80], "action": "error", "changes": [],
                            "warnings": [], "values": {},
                            "errors": [f"{ref2013} n'existe pas dans l'Annexe A de l'ISO 27001:2013."]})
                continue
            for c in targets:
                entries.append({"line": line, "target": c, "src": ref2013, "values": values, "warnings": warns})
            continue
        res_w = []
        c = by_ref.get(ref) if ref else None
        tm, ts = _title_match(title, controls) if title else (None, 0)
        if c and tm and tm is not c and ts >= 0.85 and difflib.SequenceMatcher(None, norm(title), norm(c.title)).ratio() < 0.6:
            res_w.append(f"Réf. {g('ref')} ne correspond pas à l'intitulé : rapprochée par intitulé de A.{tm.ref}.")
            c = tm
        if not c and tm and ts >= 0.85:
            c = tm
            res_w.append(f"Rapprochée par intitulé ({int(ts * 100)} %).")
        if not c:
            err = (f"Mesure A.{ref} inexistante dans l'Annexe A:2022." if ref
                   else "Mesure non identifiée (référence ou intitulé manquant).")
            out.append({"line": line, "label": (g("ref") or title or "")[:80], "action": "error", "changes": [],
                        "warnings": [], "values": {}, "errors": [err]})
            continue
        entries.append({"line": line, "target": c, "src": None, "values": values, "warnings": res_w + warns})

    # 2) regroupement par mesure 2022 (fusion des mesures 2013 regroupées)
    groups = {}
    for e in entries:
        groups.setdefault(e["target"].id, []).append(e)
    labels = {"applicable": "Applicable", "status": "Statut", "justification": "Justification",
              "implementation": "Mise en œuvre", "owner_id": "Responsable"}
    n2013 = set()
    for grp in groups.values():
        c = grp[0]["target"]
        direct = [e for e in grp if not e["src"]]
        conv = [e for e in grp if e["src"]]
        n2013.update(e["line"] for e in conv)
        for e in direct[1:]:
            out.append({"line": e["line"], "label": f"A.{c.ref} {c.title}", "action": "error", "changes": [],
                        "warnings": [], "values": {},
                        "errors": [f"Doublon : la mesure A.{c.ref} figure déjà ligne {direct[0]['line']}."]})
        res = {"label": f"A.{c.ref} {c.title}", "action": "update", "errors": [], "changes": [], "target": c}
        if direct:
            e = direct[0]
            res.update(line=e["line"], values=dict(e["values"]), warnings=list(e["warnings"]))
            if conv:
                res["warnings"].append("Lignes 2013 ignorées (" + ", ".join(x["src"] for x in conv)
                                       + ") : la mesure figure aussi au format 2022.")
        else:
            v, w = _merge_2013(conv)
            srcs = list(dict.fromkeys(e["src"] for e in conv))
            res.update(line=", ".join(str(x) for x in dict.fromkeys(e["line"] for e in conv)), values=v, warnings=[])
            res["source"] = "Converti de " + ", ".join(srcs)
            for e in conv:
                res["warnings"] += [f"{e['src']} : {x}" for x in e["warnings"] if f"{e['src']} : {x}" not in res["warnings"]]
            res["warnings"] += w
        v = res["values"]
        if v.get("applicable") is False:
            v["status"] = ControlStatus.NON_APPLICABLE
        elif v.get("applicable") is True and v.get("status", c.status) == ControlStatus.NON_APPLICABLE:
            v["status"] = ControlStatus.NON_DEMARRE
        if v.get("applicable") is False and not (v.get("justification") or c.justification):
            res["warnings"].append("Exclusion sans justification (exigée par 6.1.3 d).")
        for k, new in v.items():
            old = getattr(c, k)
            if old != new:
                res["changes"].append((labels[k], _show(k, old, ctx), _show(k, new, ctx)))
        if not res["changes"]:
            res["action"] = "same"
        out.append(res)

    if n2013:
        touched = {c_id for c_id, grp in groups.items() if any(e["src"] for e in grp)}
        ctx["notice"] = {
            "kind": "dda2013", "rows": len(n2013), "controls": len(touched),
            "new": [by_ref[r] for r in NEW_2022 if r in by_ref],
        }
    out.sort(key=lambda r: int(str(r["line"]).split(",")[0]))
    return out


def _soa_apply(plan, ctx):
    n = 0
    for r in plan:
        if r["action"] != "update":
            continue
        for k, val in r["values"].items():
            setattr(r["target"], k, val)
        n += 1
    return {"update": n}


def _show(k, val, ctx):
    if val is None or val == "":
        return "-"
    if isinstance(val, bool):
        return "Oui" if val else "Non"
    if hasattr(val, "label"):
        return val.label
    if k == "owner_id":
        u = ctx["users_by_id"].get(val)
        return u.name if u else "-"
    if isinstance(val, (list, tuple, set)):
        return ", ".join(getattr(x, "annex_ref", None) or getattr(x, "ref", str(x)) for x in val) or "-"
    if isinstance(val, date):
        return val.strftime("%d/%m/%Y")
    s = str(val)
    return s if len(s) <= 90 else s[:87] + "…"


# --------------------------------------------------------------- Actifs
CATEGORY_TABLE = [
    (AssetCategory.PERSONNEL, ["personnel", "personne", "personnes", "humain", "humains", "rh", "ressource humaine",
                               "ressources humaines", "people", "collaborateur", "collaborateurs", "employe", "equipe"]),
    (AssetCategory.SITE, ["site", "sites", "local", "locaux", "batiment", "bureau", "bureaux", "salle", "datacenter",
                          "data center", "salle serveur", "premises", "physique", "infrastructure physique"]),
    (AssetCategory.SERVICE, ["service", "services", "saas", "cloud", "prestation", "prestataire", "iaas", "paas",
                             "hebergement", "infogerance", "fournisseur", "service externe", "telecom", "messagerie"]),
    (AssetCategory.LOGICIEL, ["logiciel", "logiciels", "application", "applications", "applicatif", "software",
                              "app", "progiciel", "erp", "crm", "systeme d exploitation", "os", "base de donnees",
                              "sgbd", "outil", "licence"]),
    (AssetCategory.MATERIEL, ["materiel", "materiels", "hardware", "equipement", "equipements", "serveur", "serveurs",
                              "poste", "postes", "pc", "ordinateur", "laptop", "portable", "reseau", "routeur",
                              "switch", "pare feu", "firewall", "imprimante", "telephone", "smartphone", "stockage",
                              "nas", "san", "support amovible", "cle usb", "infrastructure"]),
    (AssetCategory.INFORMATION, ["information", "informations", "donnee", "donnees", "data", "document", "documents",
                                 "dossier", "fichier", "fichiers", "base documentaire", "archive", "archives",
                                 "informationnel", "actif informationnel", "actif primaire", "processus"]),
]

CLASSIF_TABLE = [
    (Classification.SECRET, ["secret", "tres confidentiel", "strictement confidentiel", "c3", "c4", "top secret",
                             "secret defense", "critique"]),
    (Classification.CONFIDENTIEL, ["confidentiel", "confidentielle", "c2", "restreint", "restreinte",
                                   "diffusion restreinte", "sensible", "confidential", "restricted"]),
    (Classification.INTERNE, ["interne", "usage interne", "c1", "internal", "diffusion interne", "limite"]),
    (Classification.PUBLIC, ["public", "publique", "c0", "diffusion libre", "libre", "ouvert", "non classifie"]),
]

ASTATUS_TABLE = [
    (AssetStatus.RETIRE, ["retire", "retiree", "decommissionne", "hors service", "obsolete", "archive", "supprime",
                          "fin de vie", "retired", "reforme", "inactif", "inactive"]),
    (AssetStatus.MAINTENANCE, ["maintenance", "en maintenance", "en reparation", "en panne"]),
    (AssetStatus.ACTIF, ["actif", "active", "en service", "production", "en production", "utilise", "en usage",
                         "operationnel", "in use", "en exploitation", "oui"]),
]


def _conf_level(value, top):
    """Niveau C du DIC (1..top) -> classification."""
    try:
        n = int(float(value.replace(",", ".")))
    except (ValueError, AttributeError):
        return None
    if top <= 3:
        return {1: Classification.INTERNE, 2: Classification.CONFIDENTIEL, 3: Classification.SECRET}.get(n)
    return {0: Classification.PUBLIC, 1: Classification.PUBLIC, 2: Classification.INTERNE,
            3: Classification.CONFIDENTIEL}.get(n, Classification.SECRET if n >= 4 else None)


def _asset_plan(rows, ctx):
    from app.services.refs import next_ref
    existing = Asset.query.all()
    by_ref = {a.ref.lower(): a for a in existing}
    by_name = {}
    for a in existing:
        by_name.setdefault(norm(a.name), a)
    users = ctx["users"]
    conf_vals = [r.get("confidentiality", "") for _, r in rows]
    nums = [int(float(x.replace(",", "."))) for x in conf_vals if re.fullmatch(r"\d+([.,]0+)?", x or "")]
    conf_top = max(nums) if nums else 4
    seen_ref, seen_name, new_refs = {}, {}, set()
    gen_base = next_ref(Asset, "ACT")
    m = re.match(r"(.*-)(\d+)$", gen_base)
    gen_prefix, gen_n = m.group(1), int(m.group(2))
    out = []
    for line, row in rows:
        g = row.get
        if not any((v or "").strip() for v in row.values()):
            continue
        res = {"line": line, "label": "", "action": "create", "errors": [], "warnings": [], "changes": [], "values": {}}
        name = (g("name") or "").strip()
        cref = (g("ref") or "").strip()
        res["label"] = name[:80] or cref
        if not name:
            res["errors"].append("Nom de l'actif manquant.")
            res["action"] = "error"
            out.append(res)
            continue
        key_n = norm(name)
        target = by_ref.get(cref.lower()) if cref else None
        if target is None:
            target = by_name.get(key_n)
        dup = seen_ref.get(cref.lower()) if cref else None
        dup = dup or seen_name.get(key_n)
        if dup:
            res["errors"].append(f"Doublon : même actif que la ligne {dup}.")
            res["action"] = "error"
            out.append(res)
            continue
        if cref:
            seen_ref[cref.lower()] = line
        seen_name[key_n] = line

        v = res["values"]
        v["name"] = name[:300]
        if g("category", "").strip():
            cat = match_table(g("category"), CATEGORY_TABLE)
            if cat is None:
                res["warnings"].append(f"Catégorie « {g('category')} » non reconnue" + (" : Information par défaut." if not target else " : inchangée."))
            else:
                v["category"] = cat
        cls = None
        if g("classification", "").strip():
            cls = match_table(g("classification"), CLASSIF_TABLE)
            if cls is None and re.fullmatch(r"\d", g("classification").strip()):
                cls = _conf_level(g("classification"), conf_top)
            if cls is None:
                res["warnings"].append(f"Classification « {g('classification')} » non reconnue.")
        if cls is None and g("confidentiality", "").strip():
            cls = _conf_level(g("confidentiality"), conf_top)
            if cls:
                res["warnings"].append(f"Classification déduite du niveau de confidentialité C={g('confidentiality')} : {cls.label}.")
        if cls:
            v["classification"] = cls
        if g("status", "").strip():
            st = match_table(g("status"), ASTATUS_TABLE)
            if st is None:
                res["warnings"].append(f"Statut « {g('status')} » non reconnu.")
            else:
                v["status"] = st
        for k, lim in (("description", None), ("custodian", 255), ("location", 255)):
            if g(k, "").strip():
                v[k] = g(k).strip()[:lim] if lim else g(k).strip()
        if g("owner", "").strip():
            u = match_user(g("owner"), users)
            if u:
                v["owner_id"] = u.id
            elif not g("custodian", "").strip() and not (target and target.custodian):
                v["custodian"] = g("owner").strip()[:255]
                res["warnings"].append(f"Propriétaire « {g('owner')} » sans compte utilisateur : noté comme dépositaire.")
            else:
                res["warnings"].append(f"Propriétaire « {g('owner')} » introuvable parmi les utilisateurs.")

        if target is not None:
            res["action"] = "update"
            res["target"] = target
            res["label"] = f"{target.ref} {name}"[:90]
            labels = {"name": "Nom", "category": "Catégorie", "classification": "Classification", "status": "Statut",
                      "description": "Description", "custodian": "Dépositaire", "location": "Localisation",
                      "owner_id": "Propriétaire"}
            for k, new in v.items():
                old = getattr(target, k)
                if old != new:
                    res["changes"].append((labels[k], _show(k, old, ctx), _show(k, new, ctx)))
            if not res["changes"]:
                res["action"] = "same"
        else:
            res["changes"] = [(lbl, None, _show(k, v[k], ctx)) for k, lbl in
                              (("category", "Catégorie"), ("classification", "Classification"), ("owner_id", "Propriétaire"),
                               ("custodian", "Dépositaire"), ("location", "Localisation")) if v.get(k)]
            v.setdefault("category", AssetCategory.INFORMATION)
            if not g("category", "").strip():
                res["warnings"].append("Catégorie absente : Information par défaut.")
            v.setdefault("classification", Classification.INTERNE)
            v.setdefault("status", AssetStatus.ACTIF)
            if cref and len(cref) <= 24 and cref.lower() not in by_ref and cref.lower() not in new_refs:
                ref = cref           # on conserve l'identifiant du client
            else:
                if cref:
                    res["warnings"].append(f"Réf. « {cref} » non réutilisable : nouvelle référence attribuée.")
                while f"{gen_prefix}{gen_n:04d}".lower() in by_ref or f"{gen_prefix}{gen_n:04d}".lower() in new_refs:
                    gen_n += 1
                ref = f"{gen_prefix}{gen_n:04d}"
                gen_n += 1
            new_refs.add(ref.lower())
            v["ref"] = ref
            res["label"] = f"{ref} {name}"[:90]
        out.append(res)
    return out


def _asset_apply(plan, ctx):
    stats = {"create": 0, "update": 0}
    for r in plan:
        if r["action"] == "create":
            db.session.add(Asset(**r["values"]))
            stats["create"] += 1
        elif r["action"] == "update":
            for k, val in r["values"].items():
                setattr(r["target"], k, val)
            stats["update"] += 1
    return stats


# --------------------------------------------------------------- Outils communs
def parse_date(value):
    """'2026-05-01', '01/05/2026', '1.5.26', '05/2026' -> date (ou None)."""
    v = (value or "").strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d.%m.%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(v[:10], fmt).date()
        except ValueError:
            continue
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{4})", v)
    if m and 1 <= int(m.group(1)) <= 12:
        return date(int(m.group(2)), int(m.group(1)), 1)
    return None


def split_list(value):
    return [x.strip() for x in re.split(r"[;,\n/|]+", value or "") if x.strip()]


class RefAllocator:
    """Références nouvelles sans collision, y compris pour plusieurs créations d'un même import.
    La référence du client est conservée si elle est libre."""

    def __init__(self, existing_refs, prefix, width=4, yearly=True):
        self.taken = {r.lower() for r in existing_refs}
        year = datetime.utcnow().year
        self.prefix = f"{prefix}-{year}-" if yearly else f"{prefix}-"
        self.width = width
        self.n = 1 + sum(1 for r in self.taken if r.startswith(self.prefix.lower()))

    def free(self, ref):
        return bool(ref) and len(ref) <= 24 and ref.lower() not in self.taken

    def take(self, client_ref=None):
        if self.free(client_ref):
            ref = client_ref
        else:
            while f"{self.prefix}{self.n:0{self.width}d}".lower() in self.taken:
                self.n += 1
            ref = f"{self.prefix}{self.n:0{self.width}d}"
        self.taken.add(ref.lower())
        return ref


def parse_controls(value, by_ref):
    """Références Annexe A dans un texte libre (2022, ou 2013 converties).
    -> (mesures, références inconnues, conversions 2013 effectuées)."""
    found, unknown, conv = [], [], []
    for m in REF_RE.finditer(value or ""):
        a, b, c = m.groups()
        if c is not None:
            src = f"{int(a)}.{int(b)}.{int(c)}"
            targets = MAP_2013.get(src)
            if not targets:
                unknown.append("A." + src)
                continue
            conv.append(f"A.{src} → " + ", ".join("A." + t for t in targets))
            refs = targets
        else:
            refs = [f"{int(a)}.{int(b)}"]
        for r in refs:
            if r in by_ref:
                if by_ref[r] not in found:
                    found.append(by_ref[r])
            else:
                unknown.append("A." + r)
    return found, unknown, conv


def _diff(res, target, values, labels, ctx, skip=()):
    for k, new in values.items():
        if k in skip:
            continue
        old = getattr(target, k)
        if isinstance(new, list):
            if {x.id for x in old} == {x.id for x in new}:
                continue
        elif old == new:
            continue
        res["changes"].append((labels[k], _show(k, old, ctx), _show(k, new, ctx)))


# --------------------------------------------------------------- Risques
from app.models import Risk, Treatment, RiskStatus  # noqa: E402

TREATMENT_TABLE = [
    (Treatment.EVITER, ["eviter", "evitement", "refuser", "refus", "supprimer", "suppression", "avoid", "avoidance",
                        "arreter", "abandonner"]),
    (Treatment.PARTAGER, ["partager", "partage", "transferer", "transfert", "assurance", "assurer", "share",
                          "transfer", "externaliser", "sous traiter"]),
    (Treatment.ACCEPTER, ["accepter", "acceptation", "accepte", "retenir", "maintenir", "tolerer", "accept",
                          "retain", "prise de risque", "conserver"]),
    (Treatment.REDUIRE, ["reduire", "reduction", "traiter", "traitement", "attenuer", "attenuation", "mitiger",
                         "mitigation", "mitigate", "reduce", "modifier", "modification", "diminuer", "maitriser"]),
]
RSTATUS_TABLE = [
    (RiskStatus.CLOTURE, ["cloture", "cloturee", "ferme", "fermee", "clos", "close", "closed", "obsolete", "archive"]),
    (RiskStatus.ACCEPTE, ["accepte", "acceptee", "accepted", "risque accepte"]),
    (RiskStatus.TRAITE, ["traite", "traitee", "maitrise", "maitrisee", "mitige", "treated", "mitigated", "realise",
                         "termine", "terminee"]),
    (RiskStatus.EN_TRAITEMENT, ["en traitement", "en cours", "in progress", "planifie", "plan d action",
                                "en cours de traitement", "a traiter", "action en cours"]),
    (RiskStatus.IDENTIFIE, ["identifie", "identifiee", "nouveau", "ouvert", "open", "new", "a evaluer", "detecte"]),
]
# Échelle qualitative de référence à 5 crans, convertie ensuite vers l'échelle de l'organisation
LADDER = [
    (5, ["tres eleve", "tres elevee", "tres fort", "tres forte", "quasi certain", "quasi certaine", "certain",
         "certaine", "critique", "catastrophique", "vital", "very high", "almost certain", "critical", "extreme",
         "majeur critique", "inacceptable", "maximal", "maximale"]),
    (4, ["eleve", "elevee", "fort", "forte", "probable", "tres probable", "important", "importante", "grave",
         "majeur", "majeure", "high", "likely", "severe", "frequent", "frequente"]),
    (3, ["moyen", "moyenne", "modere", "moderee", "possible", "significatif", "significative", "medium",
         "moderate", "occasionnel", "occasionnelle", "sensible"]),
    (2, ["faible", "peu probable", "mineur", "mineure", "limite", "limitee", "low", "unlikely", "minor", "rare",
         "peu frequent"]),
    (1, ["tres faible", "negligeable", "insignifiant", "insignifiante", "minime", "improbable", "very low",
         "negligible", "exceptionnel", "tres rare", "tres peu probable"]),
]


def _num(value):
    try:
        f = float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else None


def _rating(value, file_n, org_n):
    """Cotation du fichier -> échelle de l'organisation. -> (valeur, message ou None)."""
    v = (value or "").strip()
    if not v:
        return None, None
    n = _num(v)
    if n is None:
        m = re.match(r"^(\d+)\s*[-–:.)]", v)          # « 3 - Probable »
        n = int(m.group(1)) if m else None
    if n is not None:
        if 1 <= n <= file_n:
            return risk_criteria().convert(n, file_n, org_n), None
        return None, f"« {v} » hors de l'échelle 1 à {file_n} : ignorée."
    pos = match_table(v, LADDER)
    if pos is None:
        return None, f"Cotation « {v} » non reconnue : ignorée."
    out = risk_criteria().convert(pos, 5, org_n)
    return out, f"« {v} » interprété comme {out}/{org_n}."


def risk_criteria():
    from app.services import risk_criteria as rc
    return rc


def _scales(rows, ctx):
    """Échelles du fichier : choisies par l'utilisateur, sinon max(échelle de l'organisation, valeur la plus haute lue)."""
    rc = risk_criteria()
    out = {}
    for axis, keys in (("likelihood", ("likelihood", "residual_likelihood")),
                       ("impact", ("impact", "residual_impact"))):
        org_n = rc.scale(axis)
        seen = [_num(r.get(k)) for _, r in rows for k in keys]
        seen = [x for x in seen if x is not None and 1 <= x <= 10]
        chosen = ctx["options"].get("scale_" + axis)
        file_n = int(chosen) if chosen else max([org_n] + seen)
        out[axis] = (max(2, min(10, file_n)), org_n)
    return out


def _risk_plan(rows, ctx):
    existing = Risk.query.all()
    by_ref = {r.ref.lower(): r for r in existing}
    by_title = {}
    for r in existing:
        by_title.setdefault(norm(r.title), r)
    ctrl_by_ref = {c.ref: c for c in Control.query.all()}
    assets = Asset.query.all()
    asset_idx = {a.ref.lower(): a for a in assets}
    for a in assets:
        asset_idx.setdefault(norm(a.name), a)
    users = ctx["users"]
    sc = _scales(rows, ctx)
    ctx["notice"] = {"kind": "scale", "likelihood": sc["likelihood"], "impact": sc["impact"]}
    rc = risk_criteria()
    alloc = RefAllocator(by_ref, "R")
    labels = {"title": "Titre", "description": "Description", "asset": "Actif (texte)", "threat": "Menace",
              "vulnerability": "Vulnérabilité", "likelihood": "Vraisemblance", "impact": "Impact",
              "treatment": "Traitement", "residual_likelihood": "Vraisemblance résiduelle",
              "residual_impact": "Impact résiduel", "status": "Statut", "owner_id": "Propriétaire",
              "review_date": "Prochaine revue", "controls": "Mesures", "assets": "Actifs liés"}
    seen_ref, seen_title, out = {}, {}, []
    for line, row in rows:
        g = row.get
        if not any((v or "").strip() for v in row.values()):
            continue
        res = {"line": line, "label": "", "action": "create", "errors": [], "warnings": [], "changes": [], "values": {}}
        title = (g("title") or "").strip()
        cref = (g("ref") or "").strip()
        res["label"] = title[:90] or cref
        if not title:
            res.update(action="error", errors=["Intitulé du risque manquant."])
            out.append(res)
            continue
        kt = norm(title)
        dup = (seen_ref.get(cref.lower()) if cref else None) or seen_title.get(kt)
        if dup:
            res.update(action="error", errors=[f"Doublon : même risque que la ligne {dup}."])
            out.append(res)
            continue
        if cref:
            seen_ref[cref.lower()] = line
        seen_title[kt] = line
        target = (by_ref.get(cref.lower()) if cref else None) or by_title.get(kt)
        v = res["values"]
        v["title"] = title[:300]
        for k, lim in (("description", None), ("threat", 255), ("vulnerability", 255)):
            if g(k, "").strip():
                v[k] = g(k).strip()[:lim] if lim else g(k).strip()
        if g("asset", "").strip():
            v["asset"] = g("asset").strip()[:255]
            linked, missing = [], []
            for part in split_list(g("asset")):
                a = asset_idx.get(part.lower()) or asset_idx.get(norm(part))
                (linked if a else missing).append(a or part)
            if linked:
                v["assets"] = list(dict.fromkeys(linked))
            if missing and assets:
                res["warnings"].append("Absent de l'inventaire (gardé en texte) : " + ", ".join(missing[:4])
                                       + ("…" if len(missing) > 4 else "") + ".")
        for k, axis in (("likelihood", "likelihood"), ("impact", "impact"),
                        ("residual_likelihood", "likelihood"), ("residual_impact", "impact")):
            val, msg = _rating(g(k), *sc[axis])
            if val is not None:
                v[k] = val
            if msg:
                res["warnings"].append(f"{labels[k]} : {msg}")
        if ("residual_likelihood" in v) != ("residual_impact" in v):
            res["warnings"].append("Risque résiduel incomplet : vraisemblance et impact résiduels vont ensemble.")
        if g("treatment", "").strip():
            t = match_table(g("treatment"), TREATMENT_TABLE)
            if t is None:
                res["warnings"].append(f"Traitement « {g('treatment')} » non reconnu.")
            else:
                v["treatment"] = t
        if g("status", "").strip():
            st = match_table(g("status"), RSTATUS_TABLE)
            if st is None:
                res["warnings"].append(f"Statut « {g('status')} » non reconnu.")
            else:
                v["status"] = st
        if g("owner", "").strip():
            u = match_user(g("owner"), users)
            if u:
                v["owner_id"] = u.id
            else:
                res["warnings"].append(f"Propriétaire « {g('owner')} » introuvable parmi les utilisateurs.")
        if g("review_date", "").strip():
            d = parse_date(g("review_date"))
            if d:
                v["review_date"] = d
            else:
                res["warnings"].append(f"Date de revue « {g('review_date')} » non reconnue.")
        if g("controls", "").strip():
            found, unknown, conv = parse_controls(g("controls"), ctrl_by_ref)
            if found:
                v["controls"] = found
            if conv:
                res["warnings"].append("Mesures 2013 converties : " + " ; ".join(conv) + ".")
            if unknown:
                res["warnings"].append("Mesures inconnues ignorées : " + ", ".join(unknown) + ".")
            if not found and not unknown:
                res["warnings"].append(f"Aucune référence de mesure reconnue dans « {g('controls')[:60]} ».")
        if v.get("treatment") == Treatment.ACCEPTER or v.get("status") == RiskStatus.ACCEPTE:
            res["warnings"].append("Acceptation à formaliser par le propriétaire du risque dans la plateforme (6.1.3 f).")

        if target is not None:
            res.update(action="update", target=target, label=f"{target.ref} {title}"[:90])
            _diff(res, target, v, labels, ctx)
            if not res["changes"]:
                res["action"] = "same"
        else:
            for k in ("likelihood", "impact"):
                if k not in v:
                    v[k] = rc.middle(k)
                    res["warnings"].append(f"{labels[k]} absente : valeur médiane {v[k]}.")
            if cref and not alloc.free(cref):
                res["warnings"].append(f"Réf. « {cref} » non réutilisable : nouvelle référence attribuée.")
            v["ref"] = alloc.take(cref)
            res["label"] = f"{v['ref']} {title}"[:90]
            score = v["likelihood"] * v["impact"]
            res["changes"] = [("Score", None, f"{score} ({rc.label_of(rc.level_of(score))})")]
            res["changes"] += [(labels[k], None, _show(k, v[k], ctx)) for k in ("treatment", "owner_id", "controls", "assets")
                               if v.get(k)]
        out.append(res)
    return out


def _risk_apply(plan, ctx):
    stats = {"create": 0, "update": 0}
    for r in plan:
        if r["action"] not in ("create", "update"):
            continue
        vals = dict(r["values"])
        rel = {k: vals.pop(k) for k in ("controls", "assets") if k in vals}
        if r["action"] == "create":
            obj = Risk(**vals)
            db.session.add(obj)
        else:
            obj = r["target"]
            for k, val in vals.items():
                setattr(obj, k, val)
        for k, val in rel.items():
            setattr(obj, k, val)
        stats[r["action"]] += 1
    return stats


# --------------------------------------------------------------- Fournisseurs
from app.models import (Supplier, SupplierCategory, Criticality, DataAccess, AssessmentResult,  # noqa: E402
                        SupplierStatus)

SCAT_TABLE = [
    (SupplierCategory.SECURITE, ["securite", "cybersecurite", "soc", "pentest", "test d intrusion", "audit securite",
                                 "edr", "antivirus", "mssp", "securite informatique", "gardiennage", "surete"]),
    (SupplierCategory.CLOUD, ["cloud", "hebergement", "hebergeur", "iaas", "paas", "datacenter", "data center",
                              "hosting", "infrastructure cloud", "stockage en ligne", "colocation"]),
    (SupplierCategory.TELECOM, ["telecom", "telecoms", "telecommunication", "operateur", "reseau", "fai", "internet",
                                "telephonie", "fibre", "connectivite", "isp", "mobile"]),
    (SupplierCategory.INFOGERANCE, ["infogerance", "support", "maintenance", "msp", "tma", "assistance", "helpdesk",
                                    "exploitation", "tierce maintenance", "service desk", "managed services"]),
    (SupplierCategory.LOGICIEL, ["logiciel", "saas", "editeur", "application", "software", "licence", "erp", "crm",
                                 "progiciel", "outil", "plateforme"]),
    (SupplierCategory.CONSEIL, ["conseil", "prestation", "prestations", "consulting", "consultant", "audit",
                                "formation", "cabinet", "esn", "expertise", "comptable", "juridique", "avocat"]),
    (SupplierCategory.MATERIEL, ["materiel", "hardware", "equipement", "equipements", "fourniture", "fournitures",
                                 "constructeur", "revendeur", "informatique", "imprimante", "postes"]),
]
CRIT_TABLE = [
    (Criticality.CRITIQUE, ["critique", "critical", "tres elevee", "tres eleve", "vital", "vitale", "haute", "haut",
                            "elevee", "eleve", "high", "forte", "fort", "majeur", "majeure", "p1", "niveau 1", "tier 1"]),
    (Criticality.IMPORTANT, ["important", "importante", "moyenne", "moyen", "medium", "significatif",
                             "significative", "modere", "moderee", "p2", "niveau 2", "tier 2"]),
    (Criticality.STANDARD, ["standard", "faible", "basse", "bas", "low", "normal", "normale", "mineur", "mineure",
                            "non critique", "p3", "niveau 3", "tier 3"]),
]
DATA_TABLE = [
    (DataAccess.PERSONNEL, ["personnel", "personnelles", "donnees personnelles", "dcp", "rgpd", "gdpr", "pii",
                            "donnees a caractere personnel", "personal data", "donnees clients", "donnees rh"]),
    (DataAccess.CONFIDENTIEL, ["confidentiel", "confidentielles", "donnees confidentielles", "sensible", "sensibles",
                               "secret", "restreint", "confidential"]),
    (DataAccess.INTERNE, ["interne", "internes", "donnees internes", "internal", "usage interne"]),
    (DataAccess.AUCUN, ["aucun", "aucune", "non", "none", "pas d acces", "sans acces", "no", "n a", "na", "0"]),
]
ASSESS_TABLE = [
    (AssessmentResult.NON_CONFORME, ["non conforme", "defavorable", "insatisfaisant", "ko", "refuse", "echec",
                                     "non satisfaisant", "non compliant", "rouge"]),
    (AssessmentResult.RESERVES, ["reserves", "avec reserves", "conforme avec reserves", "partiel", "partiellement",
                                 "partiellement conforme", "acceptable", "sous conditions", "a ameliorer", "orange",
                                 "moyen", "plan d action"]),
    (AssessmentResult.NON_EVALUE, ["non evalue", "a evaluer", "en attente", "na", "n a", "jamais", "a faire",
                                   "not assessed", "pending"]),
    (AssessmentResult.CONFORME, ["conforme", "ok", "satisfaisant", "favorable", "valide", "compliant", "vert",
                                 "bon", "approuve", "conforme sans reserve"]),
]
SSTATUS_TABLE = [
    (SupplierStatus.TERMINE, ["termine", "terminee", "resilie", "resiliee", "fin de contrat", "inactif", "ancien",
                              "clos", "cloture", "arrete", "ended", "terminated", "plus actif"]),
    (SupplierStatus.EN_SELECTION, ["en selection", "selection", "appel d offres", "consultation", "prospect",
                                   "en evaluation", "candidat", "rfp", "referencement"]),
    (SupplierStatus.ACTIF, ["actif", "active", "en cours", "en contrat", "sous contrat", "oui", "en service", "current"]),
]


def _supplier_plan(rows, ctx):
    existing = Supplier.query.all()
    by_ref = {x.ref.lower(): x for x in existing}
    by_name = {}
    for x in existing:
        by_name.setdefault(norm(x.name), x)
    users = ctx["users"]
    alloc = RefAllocator(by_ref, "FRN", width=3, yearly=False)
    data_header = norm(ctx["headers"].get("data_access", ""))
    labels = {"name": "Nom", "service": "Prestation", "category": "Catégorie", "criticality": "Criticité",
              "data_access": "Accès aux données", "status": "Statut", "contact": "Contact",
              "contract_ref": "Contrat", "contract_end": "Fin de contrat", "security_clauses": "Clauses de sécurité",
              "dpa": "Accord de traitement (DPA)", "certifications": "Certifications",
              "assessment_result": "Résultat d'évaluation", "last_assessment": "Dernière évaluation",
              "next_assessment": "Prochaine évaluation", "owner_id": "Responsable interne", "notes": "Notes"}
    seen_ref, seen_name, out = {}, {}, []
    for line, row in rows:
        g = row.get
        if not any((v or "").strip() for v in row.values()):
            continue
        res = {"line": line, "label": "", "action": "create", "errors": [], "warnings": [], "changes": [], "values": {}}
        name = (g("name") or "").strip()
        cref = (g("ref") or "").strip()
        res["label"] = name[:90] or cref
        if not name:
            res.update(action="error", errors=["Nom du fournisseur manquant."])
            out.append(res)
            continue
        kn = norm(name)
        dup = (seen_ref.get(cref.lower()) if cref else None) or seen_name.get(kn)
        if dup:
            res.update(action="error", errors=[f"Doublon : même fournisseur que la ligne {dup}."])
            out.append(res)
            continue
        if cref:
            seen_ref[cref.lower()] = line
        seen_name[kn] = line
        target = (by_ref.get(cref.lower()) if cref else None) or by_name.get(kn)
        v = res["values"]
        v["name"] = name[:300]
        for k, lim in (("service", None), ("contact", 255), ("contract_ref", 120), ("certifications", None),
                       ("notes", None)):
            if g(k, "").strip():
                v[k] = g(k).strip()[:lim] if lim else g(k).strip()
        for k, tbl, lbl in (("category", SCAT_TABLE, "Catégorie"), ("criticality", CRIT_TABLE, "Criticité"),
                            ("assessment_result", ASSESS_TABLE, "Résultat d'évaluation"),
                            ("status", SSTATUS_TABLE, "Statut")):
            if g(k, "").strip():
                val = match_table(g(k), tbl)
                if val is None:
                    res["warnings"].append(f"{lbl} « {g(k)} » non reconnu(e).")
                else:
                    v[k] = val
        if g("data_access", "").strip():
            val = match_table(g("data_access"), DATA_TABLE)
            b = parse_bool(g("data_access")) if val in (None, DataAccess.AUCUN) else None
            if b is True:      # colonne oui/non : le sens vient de l'en-tête
                val = (DataAccess.PERSONNEL if "personnel" in data_header or "dcp" in data_header
                       or "rgpd" in data_header else DataAccess.CONFIDENTIEL)
                res["warnings"].append(f"Accès aux données « {g('data_access')} » interprété comme : {val.label}.")
            if val is None:
                res["warnings"].append(f"Accès aux données « {g('data_access')} » non reconnu.")
            else:
                v["data_access"] = val
        for k in ("security_clauses", "dpa"):
            if g(k, "").strip():
                b = parse_bool(g(k))
                if b is None:
                    b = match_table(g(k), [(True, ["signe", "signee", "en place", "inclus", "incluses", "present",
                                                   "presente", "annexe", "valide", "ok"]),
                                           (False, ["absent", "absente", "manquant", "a signer", "en cours",
                                                    "non signe", "a faire"])])
                if b is None:
                    res["warnings"].append(f"{labels[k]} « {g(k)} » non reconnu (oui / non attendu).")
                else:
                    v[k] = b
        for k in ("contract_end", "last_assessment", "next_assessment"):
            if g(k, "").strip():
                d = parse_date(g(k))
                if d:
                    v[k] = d
                else:
                    res["warnings"].append(f"{labels[k]} « {g(k)} » : date non reconnue.")
        if g("owner", "").strip():
            u = match_user(g("owner"), users)
            if u:
                v["owner_id"] = u.id
            else:
                res["warnings"].append(f"Responsable interne « {g('owner')} » introuvable parmi les utilisateurs.")

        if target is not None:
            res.update(action="update", target=target, label=f"{target.ref} {name}"[:90])
            if v.get("last_assessment") and "next_assessment" not in v:
                v["next_assessment"] = Supplier(criticality=v.get("criticality", target.criticality)).default_next(v["last_assessment"])
            _diff(res, target, v, labels, ctx)
            if not res["changes"]:
                res["action"] = "same"
        else:
            v.setdefault("category", SupplierCategory.AUTRE)
            v.setdefault("criticality", Criticality.STANDARD)
            v.setdefault("data_access", DataAccess.AUCUN)
            v.setdefault("status", SupplierStatus.ACTIF)
            v.setdefault("assessment_result", AssessmentResult.NON_EVALUE)
            if v.get("last_assessment") and "next_assessment" not in v:
                v["next_assessment"] = Supplier(criticality=v["criticality"]).default_next(v["last_assessment"])
            if cref and not alloc.free(cref):
                res["warnings"].append(f"Réf. « {cref} » non réutilisable : nouvelle référence attribuée.")
            v["ref"] = alloc.take(cref)
            res["label"] = f"{v['ref']} {name}"[:90]
            res["changes"] = [(labels[k], None, _show(k, v[k], ctx)) for k in
                              ("category", "criticality", "data_access", "assessment_result", "next_assessment")
                              if v.get(k) is not None]
        probe = Supplier(**{k: val for k, val in v.items() if k != "ref"}) if target is None else None
        gaps = (probe.gaps if probe is not None else [])
        if gaps:
            res["warnings"].append("Écarts à traiter : " + ", ".join(gaps) + ".")
        out.append(res)
    return out


def _supplier_apply(plan, ctx):
    stats = {"create": 0, "update": 0}
    for r in plan:
        if r["action"] == "create":
            db.session.add(Supplier(**r["values"]))
            stats["create"] += 1
        elif r["action"] == "update":
            for k, val in r["values"].items():
                setattr(r["target"], k, val)
            stats["update"] += 1
    return stats


# --------------------------------------------------------------- Spécifications
def F(key, label, synonyms, required=False, hint=""):
    return {"key": key, "label": label, "synonyms": synonyms, "required": required, "hint": hint}


SPECS = {
    "dda": {
        "title": "Déclaration d'applicabilité",
        "item": "Mesure",
        "back": "soa.index",
        "intro": "Met à jour les 93 mesures de l'Annexe A:2022 déjà présentes. Les mesures absentes du fichier "
                 "et les cellules vides restent inchangées.",
        "fields": [
            F("ref", "Référence", ["ref", "réf", "réf.", "référence annexe a", "n°", "numéro", "num", "id", "clause",
                                   "annexe a", "contrôle n°", "mesure n°", "control id", "n° contrôle", "n° mesure",
                                   "identifiant", "article", "contrôle", "control"],
              hint="A.5.1, 5.1, « A.5.1 Politiques… »"),
            F("title", "Intitulé", ["intitulé de la mesure", "titre", "libellé", "mesure", "mesure de sécurité", "contrôle", "control",
                                    "nom de la mesure", "control name", "title", "désignation", "objectif"],
              hint="sert au rapprochement si la référence manque"),
            F("applicable", "Applicable", ["applicabilité", "applicable o n", "retenue", "retenu", "inclus",
                                           "incluse", "sélectionnée", "inclusion", "applicable oui non",
                                           "applicable (oui/non)", "dans le périmètre"], hint="Oui / Non / X / N/A"),
            F("justification", "Justification", ["justification d'inclusion", "justification d'exclusion",
                                                  "justification inclusion exclusion", "raison", "motif",
                                                  "motif d'exclusion", "justification de l'applicabilité",
                                                  "raison de l'exclusion", "justifications"]),
            F("status", "Statut de mise en œuvre", ["statut", "état", "status", "état de mise en œuvre",
                                                    "statut de mise en œuvre", "avancement", "état d'avancement",
                                                    "niveau de mise en œuvre", "implementation status",
                                                    "taux de mise en œuvre", "niveau de conformité", "conformité",
                                                    "maturité"], hint="Implémenté / En cours / Non démarré / %"),
            F("implementation", "Mise en œuvre", ["mise en œuvre", "description de la mise en œuvre", "commentaire",
                                                  "commentaires", "moyens", "moyens mis en œuvre", "comment",
                                                  "implementation", "observations", "remarques", "détails",
                                                  "dispositif", "preuves", "existant", "description"]),
            F("owner", "Responsable", ["propriétaire", "pilote", "owner", "porteur", "responsable de la mesure",
                                       "en charge", "responsable mise en œuvre"], hint="nom ou e-mail d'un utilisateur"),
        ],
        "plan": _soa_plan,
        "apply": _soa_apply,
        "needs_one_of": ("ref", "title"),
    },
    "actifs": {
        "title": "Inventaire des actifs",
        "item": "Actif",
        "back": "assets.index",
        "intro": "Crée les nouveaux actifs et met à jour ceux déjà présents (même référence ou même nom). "
                 "Les cellules vides ne modifient pas un actif existant.",
        "fields": [
            F("ref", "Référence", ["réf", "ref", "réf.", "identifiant", "id", "code", "n°", "numéro", "code actif",
                                   "référence actif", "asset id"], hint="conservée si elle est libre"),
            F("name", "Nom de l'actif", ["nom", "actif", "désignation", "libellé", "intitulé", "asset", "name",
                                         "élément", "nom actif", "actif informationnel", "description de l'actif",
                                         "asset name", "actifs"], required=True),
            F("category", "Catégorie", ["type", "type d'actif", "famille", "nature", "category", "catégorie d'actif",
                                        "typologie", "type actif", "catégorie de l'actif"],
              hint="Information, Logiciel, Matériel, Service, Personnel, Site"),
            F("description", "Description", ["détail", "commentaire", "commentaires", "remarques", "usage", "rôle",
                                             "utilisation", "observations", "fonction"]),
            F("owner", "Propriétaire", ["responsable", "owner", "propriétaire de l'actif", "responsable métier",
                                        "propriétaire métier", "asset owner", "responsable de l'actif"],
              hint="nom ou e-mail d'un utilisateur"),
            F("custodian", "Dépositaire", ["gestionnaire", "administrateur", "custodian", "détenteur", "exploitant",
                                           "responsable technique", "dépositaire technique", "gardien"]),
            F("classification", "Classification", ["niveau de classification", "sensibilité", "classe",
                                                    "niveau de sensibilité", "classification de l'information",
                                                    "label", "marquage"], hint="Public, Interne, Confidentiel, Secret, C0…C3"),
            F("confidentiality", "Confidentialité (C du DIC)", ["c", "confidentialité", "conf", "conf.", "c dic",
                                                                "besoin en confidentialité", "niveau c"],
              hint="utilisée si la classification est vide"),
            F("location", "Localisation", ["emplacement", "lieu", "site", "location", "hébergement", "localisation physique",
                                           "salle"]),
            F("status", "Statut", ["état", "status", "cycle de vie", "statut de l'actif", "en service"],
              hint="Actif, Maintenance, Retiré"),
        ],
        "plan": _asset_plan,
        "apply": _asset_apply,
        "needs_one_of": ("name",),
    },
    "risques": {
        "title": "Registre des risques",
        "item": "Risque",
        "back": "risks.index",
        "intro": "Crée les nouveaux risques et met à jour ceux déjà présents (même référence ou même intitulé). "
                 "Les cotations sont converties vers l'échelle de votre organisation ; les mesures peuvent être "
                 "citées en références 2022 ou 2013.",
        "fields": [
            F("ref", "Référence", ["réf", "ref", "réf.", "id", "identifiant", "n°", "numéro", "code", "id risque",
                                   "n° risque", "référence du risque"], hint="conservée si elle est libre"),
            F("title", "Intitulé du risque", ["risque", "titre", "libellé", "intitulé", "scénario", "scénario de risque",
                                              "nom du risque", "risk", "événement redouté", "description du risque",
                                              "risk title"], required=True),
            F("description", "Description", ["détail", "commentaire", "commentaires", "conséquences", "description détaillée",
                                             "remarques", "contexte"]),
            F("asset", "Actif concerné", ["actif", "actifs", "actif concerné", "actifs concernés", "actif support",
                                          "bien support", "biens supports", "périmètre", "asset", "système", "processus"],
              hint="lié à l'inventaire si le nom ou la réf. correspond"),
            F("threat", "Menace", ["menaces", "source de risque", "source de menace", "threat", "origine"]),
            F("vulnerability", "Vulnérabilité", ["vulnérabilités", "faiblesse", "vulnerability", "faille"]),
            F("likelihood", "Vraisemblance", ["probabilité", "proba", "p", "v", "occurrence", "fréquence",
                                              "likelihood", "probability", "vraisemblance initiale",
                                              "probabilité brute", "vraisemblance brute", "potentialité"],
              hint="chiffre ou texte (faible, probable…)"),
            F("impact", "Impact", ["gravité", "i", "g", "conséquence", "sévérité", "severity", "impact initial",
                                   "impact brut", "gravité brute"], hint="chiffre ou texte (mineur, grave…)"),
            F("treatment", "Traitement", ["option de traitement", "décision", "stratégie", "traitement du risque",
                                          "treatment", "option", "réponse au risque"],
              hint="Réduire / Accepter / Éviter / Partager"),
            F("residual_likelihood", "Vraisemblance résiduelle", ["probabilité résiduelle", "v résiduelle",
                                                                  "p résiduelle", "vraisemblance cible",
                                                                  "probabilité cible", "residual likelihood",
                                                                  "vraisemblance après traitement"]),
            F("residual_impact", "Impact résiduel", ["gravité résiduelle", "i résiduel", "impact cible",
                                                     "gravité cible", "residual impact", "impact résiduelle",
                                                     "impact après traitement"]),
            F("status", "Statut", ["état", "status", "statut du risque", "avancement"]),
            F("owner", "Propriétaire du risque", ["propriétaire", "responsable", "owner", "risk owner", "pilote",
                                                  "porteur"], hint="nom ou e-mail d'un utilisateur"),
            F("review_date", "Prochaine revue", ["date de revue", "revue", "échéance", "date cible",
                                                 "date de réévaluation", "review date", "date prévue"]),
            F("controls", "Mesures Annexe A", ["mesures", "mesures de sécurité", "contrôles", "controls",
                                               "mesures annexe a", "mesures iso 27001", "plan de traitement",
                                               "mesures associées", "réf. mesures", "contrôles iso"],
              hint="A.5.15, 8.2… (2013 converties)"),
        ],
        "plan": _risk_plan,
        "apply": _risk_apply,
        "needs_one_of": ("title",),
    },
    "fournisseurs": {
        "title": "Fournisseurs",
        "item": "Fournisseur",
        "back": "suppliers.index",
        "intro": "Crée les nouveaux fournisseurs et met à jour ceux déjà présents (même référence ou même nom). "
                 "La prochaine évaluation est calculée d'après la criticité si seule la dernière est connue.",
        "fields": [
            F("ref", "Référence", ["réf", "ref", "réf.", "id", "code", "code fournisseur", "n°", "identifiant"],
              hint="conservée si elle est libre"),
            F("name", "Nom du fournisseur", ["fournisseur", "nom", "raison sociale", "prestataire", "société",
                                             "sous traitant", "supplier", "vendor", "entreprise", "tiers"],
              required=True),
            F("service", "Prestation", ["service", "objet", "objet du contrat", "description", "produit",
                                        "prestation fournie", "périmètre", "services fournis"]),
            F("category", "Catégorie", ["type", "type de fournisseur", "catégorie fournisseur", "famille", "domaine",
                                        "category"], hint="Cloud, Logiciel/SaaS, Infogérance, Télécoms…"),
            F("criticality", "Criticité", ["niveau de criticité", "criticality", "importance", "niveau de risque",
                                           "tiering", "classification"], hint="Critique / Important / Standard"),
            F("data_access", "Accès aux données", ["données", "données traitées", "accès aux données personnelles",
                                                   "données personnelles", "dcp", "type de données", "data access",
                                                   "niveau d'accès"], hint="Aucun / Interne / Confidentiel / Personnel"),
            F("status", "Statut", ["état", "status", "statut contrat", "relation"]),
            F("contact", "Contact", ["contact fournisseur", "interlocuteur", "email", "e mail", "téléphone"]),
            F("contract_ref", "Référence du contrat", ["contrat", "n° contrat", "numéro de contrat", "contract"]),
            F("contract_end", "Fin de contrat", ["date de fin", "échéance contrat", "échéance", "expiration",
                                                 "date d'échéance", "fin", "renouvellement", "contract end"]),
            F("security_clauses", "Clauses de sécurité", ["clauses sécurité", "clause de sécurité", "pas",
                                                          "plan d'assurance sécurité", "annexe sécurité",
                                                          "exigences de sécurité", "clauses ssi"], hint="Oui / Non"),
            F("dpa", "Accord de traitement (DPA)", ["dpa", "accord de sous traitance", "clauses rgpd", "contrat rgpd",
                                                    "article 28", "accord de traitement des données", "rgpd"],
              hint="Oui / Non"),
            F("certifications", "Certifications", ["certification", "iso 27001", "soc 2", "labels", "attestations",
                                                   "certifié"]),
            F("assessment_result", "Résultat d'évaluation", ["évaluation", "résultat", "conformité", "note",
                                                             "résultat de l'évaluation", "avis", "assessment"]),
            F("last_assessment", "Dernière évaluation", ["date d'évaluation", "date dernière évaluation",
                                                         "évalué le", "dernier audit", "date évaluation"]),
            F("next_assessment", "Prochaine évaluation", ["prochaine revue", "prochain audit", "date prochaine évaluation",
                                                          "réévaluation"]),
            F("owner", "Responsable interne", ["responsable", "propriétaire", "owner", "gestionnaire du contrat",
                                               "acheteur", "référent", "pilote"], hint="nom ou e-mail d'un utilisateur"),
            F("notes", "Notes", ["commentaire", "commentaires", "remarques", "observations"]),
        ],
        "plan": _supplier_plan,
        "apply": _supplier_apply,
        "needs_one_of": ("name",),
    },
}


def context():
    users = User.query.order_by(User.name).all()
    return {"users": users, "users_by_id": {u.id: u for u in users}}


def mapped_rows(st):
    """[(n° de ligne Excel, {clé_champ: valeur}), ...] selon la correspondance."""
    _, data = table(st)
    mp = {k: int(v) for k, v in st.get("mapping", {}).items() if v not in (None, "")}
    base = st["header_row"] + 2
    out = []
    for i, r in enumerate(data[:MAX_ROWS]):
        out.append((base + i, {k: (r[c] if c < len(r) else "") for k, c in mp.items()}))
    return out


def plan(st):
    spec = SPECS[st["kind"]]
    ctx = context()
    ctx["options"] = st.get("options", {})
    headers, _ = table(st)
    ctx["headers"] = {k: headers[c] for k, c in st.get("mapping", {}).items() if c < len(headers)}
    p = spec["plan"](mapped_rows(st), ctx)
    counts = {"create": 0, "update": 0, "same": 0, "error": 0, "warnings": 0}
    for r in p:
        counts[r["action"]] += 1
        counts["warnings"] += 1 if r["warnings"] else 0
    return p, counts, ctx


def apply(st):
    spec = SPECS[st["kind"]]
    p, counts, ctx = plan(st)
    stats = spec["apply"](p, ctx)
    return stats, counts


# --------------------------------------------------------------- Modèles
def template_xlsx(kind):
    """Modèle Excel ; pour la DdA, pré-rempli avec l'état actuel des 93 mesures."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    spec = SPECS[kind]
    wb = Workbook()
    ws = wb.active
    ws.title = spec["title"][:31]
    heads = [f["label"] for f in spec["fields"]]
    ws.append(heads)
    if kind == "dda":
        users = {u.id: u for u in User.query.all()}
        for c in sorted(Control.query.all(), key=lambda c: tuple(int(x) for x in c.ref.split("."))):
            ws.append([f"A.{c.ref}", c.title, "Oui" if c.applicable else "Non", c.justification or "",
                       c.status.label, c.implementation or "", users[c.owner_id].name if c.owner_id in users else ""])
        dv = DataValidation(type="list", formula1='"Oui,Non"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"C2:C{ws.max_row}")
        dv2 = DataValidation(type="list", formula1='"' + ",".join(s.label for s in ControlStatus) + '"', allow_blank=True)
        ws.add_data_validation(dv2)
        dv2.add(f"E2:E{ws.max_row}")
        widths = [10, 60, 12, 45, 18, 60, 22]
    elif kind == "risques":
        ws.append(["", "Compromission de comptes à privilèges", "Accès administrateur sans MFA", "Serveur de fichiers",
                   "Attaquant externe", "MFA absente", "4", "5", "Réduire", "2", "4", "En traitement",
                   "Responsable SI", (date.today().replace(day=1)).isoformat(), "A.8.2; A.8.5; A.5.17"])
        ws.append(["", "Fuite de données clients via un prestataire", "", "Base clients CRM", "Prestataire",
                   "Contrat sans clauses de sécurité", "Probable", "Grave", "Partager", "", "", "Identifié", "", "",
                   "5.19, 5.20"])
        for col, vals in (("I", [t.label for t in Treatment]), ("L", [x.label for x in RiskStatus])):
            dv = DataValidation(type="list", formula1='"' + ",".join(vals) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{col}2:{col}1000")
        widths = [12, 40, 34, 24, 20, 24, 13, 10, 12, 13, 10, 15, 22, 15, 22]
    elif kind == "fournisseurs":
        ws.append(["", "Hébergeur Cloud SAS", "Hébergement de la plateforme de production", "Cloud / hébergement",
                   "Critique", "Données personnelles", "Actif", "support@hebergeur.example", "CT-2024-012",
                   "2027-06-30", "Oui", "Oui", "ISO 27001, HDS", "Conforme", "2026-03-15", "", "", ""])
        ws.append(["", "Cabinet comptable", "Tenue de la comptabilité", "Conseil / prestations", "Important",
                   "Données confidentielles", "Actif", "", "", "", "Non", "Non", "", "Non évalué", "", "", "", ""])
        for col, vals in (("D", [c.label for c in SupplierCategory]), ("E", [c.label for c in Criticality]),
                          ("F", [c.label for c in DataAccess]), ("G", [c.label for c in SupplierStatus]),
                          ("K", ["Oui", "Non"]), ("L", ["Oui", "Non"]), ("N", [c.label for c in AssessmentResult])):
            dv = DataValidation(type="list", formula1='"' + ",".join(vals) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{col}2:{col}1000")
        widths = [10, 28, 34, 20, 12, 22, 12, 24, 14, 13, 12, 12, 18, 18, 14, 14, 20, 24]
    else:
        ws.append(["SRV-001", "Serveur de fichiers", "Matériel", "Partages bureautiques", "DSI", "Équipe infra",
                   "Confidentiel", "", "Salle serveur", "Actif"])
        ws.append(["", "Base clients CRM", "Information", "Données clients et prospects", "Direction commerciale",
                   "", "", "3", "SaaS (UE)", "Actif"])
        for col, vals in (("C", [c.label for c in AssetCategory]), ("G", [c.label for c in Classification]),
                          ("J", [c.label for c in AssetStatus])):
            dv = DataValidation(type="list", formula1='"' + ",".join(vals) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{col}2:{col}1000")
        widths = [12, 34, 14, 40, 22, 20, 15, 12, 20, 12]
    for i, w in enumerate(widths):
        ws.column_dimensions[col_letter(i)].width = w
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1E5BB8")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
