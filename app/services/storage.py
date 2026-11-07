"""Couche de stockage des pièces jointes : disque local OU Nextcloud (WebDAV).
Le backend est choisi par la configuration (STORAGE_BACKEND = local | webdav).
L'utilisateur du SMSI n'interagit jamais directement avec Nextcloud : le SMSI
lit/écrit via un compte de service (transparent, pas de seconde connexion)."""
import io
import os
import urllib.parse as _url

from flask import current_app


def backend():
    return (current_app.config.get("STORAGE_BACKEND") or "local").lower()


# --------------------------------------------------------------------------
# Backend LOCAL
# --------------------------------------------------------------------------
def _local_dir():
    d = current_app.config.get("UPLOAD_DIR") or os.path.join(current_app.instance_path, "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _local_save(data, name):
    with open(os.path.join(_local_dir(), name), "wb") as f:
        f.write(data)


def _local_read(name):
    with open(os.path.join(_local_dir(), name), "rb") as f:
        return f.read()


def _local_delete(name):
    p = os.path.join(_local_dir(), name)
    if os.path.exists(p):
        os.remove(p)


# --------------------------------------------------------------------------
# Backend WEBDAV (Nextcloud)
# --------------------------------------------------------------------------
def attachments_folder(org):
    """Dossier des pièces jointes d'une organisation : NEXTCLOUD_ATTACHMENTS_FOLDER/<slug>,
    distinct des dossiers Docs pour qu'aucun utilisateur ne puisse les déplacer."""
    base = (current_app.config.get("NEXTCLOUD_ATTACHMENTS_FOLDER") or "SMSI-PJ").strip("/")
    return f"{base}/{org.slug}"


def _dav():
    from app.services.tenancy import current_org
    org = current_org()
    if org is None:
        raise RuntimeError("Aucune organisation courante.")
    c = current_app.config
    return {
        "base": (c.get("NEXTCLOUD_URL") or "").rstrip("/"),
        "user": c.get("NEXTCLOUD_USER") or "",
        "password": c.get("NEXTCLOUD_PASSWORD") or "",
        "folder": attachments_folder(org),
        "timeout": int(c.get("NEXTCLOUD_TIMEOUT", 20)),
    }


def _dav_root(d):
    # Endpoint WebDAV des fichiers de l'utilisateur (compte de service)
    return f"{d['base']}/remote.php/dav/files/{d['user']}"


def _dav_url(d, name=None):
    base = f"{_dav_root(d)}/{d['folder']}"
    return f"{base}/{name}" if name else base


def _session(d):
    import requests
    s = requests.Session()
    s.auth = (d["user"], d["password"])
    return s


def ensure_folder():
    """Crée le dossier cible dans Nextcloud s'il n'existe pas (idempotent)."""
    if backend() != "webdav":
        return
    d = _dav()
    s = _session(d)
    # MKCOL (non récursif) sur chaque niveau : 201 = créé, 405 = existe déjà
    path = ""
    for seg in d["folder"].split("/"):
        path = f"{path}/{seg}" if path else seg
        r = s.request("MKCOL", f"{_dav_root(d)}/{_url.quote(path)}", timeout=d["timeout"])
        if r.status_code not in (201, 405, 301):
            raise RuntimeError(f"Nextcloud MKCOL {r.status_code} : {r.text[:200]}")


def _dav_save(data, name):
    d = _dav()
    s = _session(d)
    ensure_folder()
    r = s.put(_dav_url(d, name), data=data, timeout=d["timeout"])
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Nextcloud PUT {r.status_code} : {r.text[:200]}")


def _dav_read(name):
    d = _dav()
    s = _session(d)
    r = s.get(_dav_url(d, name), timeout=d["timeout"])
    if r.status_code != 200:
        raise RuntimeError(f"Nextcloud GET {r.status_code}")
    return r.content


def _dav_delete(name):
    d = _dav()
    s = _session(d)
    r = s.delete(_dav_url(d, name), timeout=d["timeout"])
    if r.status_code not in (200, 204, 404):
        raise RuntimeError(f"Nextcloud DELETE {r.status_code}")


def test_connection():
    """Vérifie l'accès WebDAV. Retourne (ok, message)."""
    if backend() != "webdav":
        return False, "Le stockage n'est pas en mode Nextcloud (STORAGE_BACKEND=local)."
    d = _dav()
    if not (d["base"] and d["user"] and d["password"]):
        return False, "Configuration Nextcloud incomplète (URL / utilisateur / mot de passe)."
    try:
        s = _session(d)
        # PROPFIND sur la racine de l'utilisateur = test d'authentification
        r = s.request("PROPFIND", _dav_root(d), headers={"Depth": "0"}, timeout=d["timeout"])
        if r.status_code in (401, 403):
            return False, "Authentification refusée (vérifiez l'utilisateur et le mot de passe d'application)."
        if r.status_code not in (207, 200):
            return False, f"Réponse inattendue de Nextcloud ({r.status_code})."
        ensure_folder()
        return True, f"Connexion Nextcloud OK - dossier « {d['folder']} » prêt."
    except Exception as e:  # noqa: BLE001
        return False, f"Connexion impossible : {e}"


# --------------------------------------------------------------------------
# API publique (indépendante du backend)
# --------------------------------------------------------------------------
def save_bytes(data, name):
    (_dav_save if backend() == "webdav" else _local_save)(data, name)


def read_bytes(name):
    return (_dav_read if backend() == "webdav" else _local_read)(name)


def delete(name):
    (_dav_delete if backend() == "webdav" else _local_delete)(name)


# --------------------------------------------------------------------------
# Navigation WebDAV (module « Docs » : explorateur de fichiers Nextcloud)
# --------------------------------------------------------------------------
import urllib.parse as _url
import xml.etree.ElementTree as _ET


def nextcloud_configured():
    c = current_app.config
    return bool(c.get("NEXTCLOUD_URL") and c.get("NEXTCLOUD_USER") and c.get("NEXTCLOUD_PASSWORD"))


def clean_subpath(subpath):
    """Nettoie un chemin relatif (anti path-traversal). Retourne 'a/b/c' sans / initial."""
    parts = []
    for seg in (subpath or "").replace("\\", "/").split("/"):
        seg = seg.strip()
        if seg in ("", ".", ".."):
            continue
        parts.append(seg)
    return "/".join(parts)


def _folder_url(d, subpath="", trailing=False):
    segs = [d["folder"]] + [p for p in clean_subpath(subpath).split("/") if p]
    quoted = "/".join(_url.quote(s) for s in segs)
    u = f"{_dav_root(d)}/{quoted}"
    return u + "/" if trailing and not u.endswith("/") else u


def dav_list(subpath=""):
    """Liste le contenu d'un dossier (Depth 1). Retourne une liste d'entrées."""
    d = _dav()
    s = _session(d)
    url = _folder_url(d, subpath, trailing=True)
    r = s.request("PROPFIND", url, headers={"Depth": "1"}, timeout=d["timeout"])
    if r.status_code == 404:
        return []
    if r.status_code != 207:
        raise RuntimeError(f"PROPFIND {r.status_code}")
    base_path = _url.unquote(_url.urlparse(url).path).rstrip("/")
    ns = {"d": "DAV:"}
    out = []
    for resp in _ET.fromstring(r.content).findall("d:response", ns):
        href_el = resp.find("d:href", ns)
        if href_el is None or not href_el.text:
            continue
        path = _url.unquote(_url.urlparse(href_el.text).path).rstrip("/")
        if path == base_path:
            continue  # le dossier lui-même
        rt = resp.find(".//d:resourcetype", ns)
        is_dir = rt is not None and rt.find("d:collection", ns) is not None
        size_el = resp.find(".//d:getcontentlength", ns)
        mod_el = resp.find(".//d:getlastmodified", ns)
        out.append({
            "name": path.split("/")[-1],
            "is_dir": is_dir,
            "size": int(size_el.text) if (size_el is not None and size_el.text) else None,
            "modified": mod_el.text if mod_el is not None else None,
        })
    out.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return out


def dav_mkdir(subpath):
    d = _dav()
    ensure_folder()
    r = _session(d).request("MKCOL", _folder_url(d, subpath), timeout=d["timeout"])
    if r.status_code not in (201, 405):
        raise RuntimeError(f"MKCOL {r.status_code}")


def dav_put_named(subpath_dir, filename, data):
    d = _dav()
    ensure_folder()
    target = (clean_subpath(subpath_dir) + "/" + filename).strip("/")
    r = _session(d).put(_folder_url(d, target), data=data, timeout=d["timeout"])
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"PUT {r.status_code}")


def dav_get_path(subpath):
    d = _dav()
    r = _session(d).get(_folder_url(d, subpath), timeout=d["timeout"])
    if r.status_code != 200:
        raise RuntimeError(f"GET {r.status_code}")
    return r.content


def dav_delete_path(subpath):
    d = _dav()
    sp = clean_subpath(subpath)
    if not sp:
        raise RuntimeError("Chemin vide")
    r = _session(d).delete(_folder_url(d, sp), timeout=d["timeout"])
    if r.status_code not in (200, 204, 404):
        raise RuntimeError(f"DELETE {r.status_code}")
