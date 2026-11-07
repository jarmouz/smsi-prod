"""Client WebDAV pour l'explorateur de fichiers « Docs » (Nextcloud).
Toutes les opérations sont relatives au dossier racine de l'organisation courante
(Organization.docs_folder, défaut NEXTCLOUD_DOCS_FOLDER/<slug>), via le compte de
service - transparent pour l'utilisateur."""
import urllib.parse
import xml.etree.ElementTree as ET

from flask import current_app

DAV = "{DAV:}"


def enabled():
    c = current_app.config
    return c.get("STORAGE_BACKEND", "").lower() == "webdav" and bool(c.get("NEXTCLOUD_URL"))


def docs_root(org):
    """Dossier racine Docs d'une organisation (relatif au compte de service).
    Par défaut NEXTCLOUD_ORGS_FOLDER/<slug>, hors du dossier Docs historique
    pour qu'aucune organisation ne voie les dossiers d'une autre."""
    if org.docs_folder:
        return org.docs_folder.strip("/")
    base = (current_app.config.get("NEXTCLOUD_ORGS_FOLDER") or "SMSI-Organisations").strip("/")
    return f"{base}/{org.slug}"


def _cfg():
    from app.services.tenancy import current_org
    org = current_org()
    if org is None:
        raise RuntimeError("Aucune organisation courante.")
    c = current_app.config
    return {
        "base": (c.get("NEXTCLOUD_URL") or "").rstrip("/"),
        "user": c.get("NEXTCLOUD_USER") or "",
        "password": c.get("NEXTCLOUD_PASSWORD") or "",
        "root": docs_root(org),
        "timeout": int(c.get("NEXTCLOUD_TIMEOUT", 20)),
    }


def _session(cfg):
    import requests
    s = requests.Session()
    s.auth = (cfg["user"], cfg["password"])
    return s


def _root_url(cfg):
    return f"{cfg['base']}/remote.php/dav/files/{cfg['user']}"


def safe_rel(rel):
    """Normalise un chemin relatif et interdit toute remontée hors racine."""
    parts = []
    for seg in (rel or "").replace("\\", "/").split("/"):
        seg = seg.strip()
        if seg in ("", "."):
            continue
        if seg == "..":
            raise ValueError("Chemin invalide.")
        parts.append(seg)
    return "/".join(parts)


def clean_name(name):
    name = (name or "").strip().replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "")
    if name in ("", ".", ".."):
        raise ValueError("Nom invalide.")
    return name[:255]


def _quote(path):
    return "/".join(urllib.parse.quote(p) for p in path.split("/")) if path else ""


def _url(cfg, rel):
    rel = safe_rel(rel)
    full = f"{cfg['root']}/{rel}" if rel else cfg["root"]
    return f"{_root_url(cfg)}/{_quote(full)}"


def ensure_root(cfg=None, s=None):
    cfg = cfg or _cfg()
    s = s or _session(cfg)
    path, ok = "", True
    for seg in cfg["root"].split("/"):
        path = f"{path}/{seg}" if path else seg
        r = s.request("MKCOL", f"{_root_url(cfg)}/{_quote(path)}", timeout=cfg["timeout"])
        ok = r.status_code in (201, 405, 301)
    return ok


def list_dir(rel=""):
    cfg = _cfg()
    s = _session(cfg)
    ensure_root(cfg, s)
    body = ('<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop>'
            '<d:resourcetype/><d:getcontentlength/><d:getlastmodified/>'
            '</d:prop></d:propfind>')
    r = s.request("PROPFIND", _url(cfg, rel),
                  headers={"Depth": "1", "Content-Type": "application/xml"},
                  data=body, timeout=cfg["timeout"])
    if r.status_code == 404:
        return []
    if r.status_code != 207:
        raise RuntimeError(f"PROPFIND {r.status_code}")
    return _parse(cfg, rel, r.content)


def _parse(cfg, rel, xml_bytes):
    root = ET.fromstring(xml_bytes)
    prefix = urllib.parse.urlparse(_root_url(cfg)).path.rstrip("/")
    docroot = cfg["root"].strip("/")
    base = safe_rel(rel)
    out = []
    for resp in root.findall(f"{DAV}response"):
        href_el = resp.find(f"{DAV}href")
        if href_el is None or not href_el.text:
            continue
        path = urllib.parse.unquote(urllib.parse.urlparse(href_el.text).path).strip("/")
        if prefix and path.startswith(prefix.strip("/")):
            path = path[len(prefix.strip("/")):].strip("/")
        if path == docroot or not path.startswith(docroot):
            # tolérer docroot manquant si le serveur renvoie déjà relatif
            if not path.startswith(docroot):
                pass
        # chemin relatif à la racine docs
        relpath = path[len(docroot):].strip("/") if path.startswith(docroot) else path
        if relpath == base or relpath == "":
            continue
        parent = "/".join(relpath.split("/")[:-1])
        if parent != base:
            continue
        prop = resp.find(f"{DAV}propstat/{DAV}prop")
        is_dir = prop is not None and prop.find(f"{DAV}resourcetype/{DAV}collection") is not None
        size_el = prop.find(f"{DAV}getcontentlength") if prop is not None else None
        mod_el = prop.find(f"{DAV}getlastmodified") if prop is not None else None
        size = int(size_el.text) if (size_el is not None and size_el.text and size_el.text.isdigit()) else None
        out.append({"name": relpath.split("/")[-1], "rel": relpath, "is_dir": is_dir,
                    "size": size, "mtime": (mod_el.text if mod_el is not None else None)})
    out.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return out


def download(rel):
    cfg = _cfg()
    r = _session(cfg).get(_url(cfg, rel), timeout=cfg["timeout"])
    if r.status_code != 200:
        raise RuntimeError(f"GET {r.status_code}")
    return r.content


def upload(rel_dir, filename, data):
    cfg = _cfg()
    s = _session(cfg)
    ensure_root(cfg, s)
    fn = clean_name(filename)
    rel = (safe_rel(rel_dir) + "/" + fn).strip("/")
    r = s.put(_url(cfg, rel), data=data, timeout=cfg["timeout"])
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"PUT {r.status_code}")
    return fn


def mkdir(rel_dir, name):
    cfg = _cfg()
    s = _session(cfg)
    nm = clean_name(name)
    rel = (safe_rel(rel_dir) + "/" + nm).strip("/")
    r = s.request("MKCOL", _url(cfg, rel), timeout=cfg["timeout"])
    if r.status_code not in (201, 405):
        raise RuntimeError(f"MKCOL {r.status_code}")
    return nm


def delete(rel):
    cfg = _cfg()
    if not safe_rel(rel):
        raise ValueError("Chemin vide.")
    r = _session(cfg).delete(_url(cfg, rel), timeout=cfg["timeout"])
    if r.status_code not in (200, 204, 404):
        raise RuntimeError(f"DELETE {r.status_code}")


def human_size(n):
    if n is None:
        return ""
    x = float(n)
    for u in ("o", "Ko", "Mo", "Go"):
        if x < 1024:
            return f"{x:.0f} {u}" if u == "o" else f"{x:.1f} {u}"
        x /= 1024
    return f"{x:.1f} To"


def stat(rel):
    """Métadonnées d'un fichier (PROPFIND Depth 0). Retourne {size, mtime}."""
    cfg = _cfg()
    body = ('<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop>'
            '<d:getcontentlength/><d:getlastmodified/></d:prop></d:propfind>')
    r = _session(cfg).request("PROPFIND", _url(cfg, rel),
                              headers={"Depth": "0", "Content-Type": "application/xml"},
                              data=body, timeout=cfg["timeout"])
    if r.status_code != 207:
        raise RuntimeError(f"PROPFIND {r.status_code}")
    root = ET.fromstring(r.content)
    prop = root.find(f"{DAV}response/{DAV}propstat/{DAV}prop")
    size_el = prop.find(f"{DAV}getcontentlength") if prop is not None else None
    mod_el = prop.find(f"{DAV}getlastmodified") if prop is not None else None
    return {"size": int(size_el.text) if (size_el is not None and size_el.text and size_el.text.isdigit()) else None,
            "mtime": mod_el.text if mod_el is not None else None}
