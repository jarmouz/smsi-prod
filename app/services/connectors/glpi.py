"""GLPI : parc matériel géré (API REST)."""
from app.models import AssetCategory, AssetStatus
from app.services import importer
from app.services.connectors import ConnectorError, Kind, Param, call, check_url

PAGE = 200
TYPES = (("Computer", "Ordinateur"), ("NetworkEquipment", "Équipement réseau"), ("Printer", "Imprimante"), ("Phone", "Téléphone"))


def _status(state):
    s = importer.norm(str(state or ""))
    if any(w in s for w in ("rebut", "retire", "reforme", "hors service")):
        return AssetStatus.RETIRE
    if any(w in s for w in ("maintenance", "reparation")):
        return AssetStatus.MAINTENANCE
    return None


def _text(v):
    return None if v in (None, 0, "0", "", "&nbsp;") else str(v)


def fetch(cfg, secrets):
    base = (cfg.get("url") or "").strip().rstrip("/")
    if base.endswith("/apirest.php"):
        base = base[:-len("/apirest.php")]
    api = base + "/apirest.php"
    check_url(api)
    head = {"App-Token": secrets.get("app_token", "")}
    r = call("GLPI", "GET", f"{api}/initSession", headers={**head, "Authorization": f"user_token {secrets.get('user_token', '')}"})
    head["Session-Token"] = r.json().get("session_token", "")
    if not head["Session-Token"]:
        raise ConnectorError("GLPI : session refusée.")
    try:
        for itemtype, label in TYPES:
            start = 0
            while True:
                r = call("GLPI", "GET", f"{api}/{itemtype}", headers=head,
                         params={"range": f"{start}-{start + PAGE - 1}", "expand_dropdowns": "true"})
                rows = r.json() or []
                for x in rows:
                    if x.get("is_template") or x.get("is_deleted"):
                        continue
                    detail = " - ".join(p for p in (label, f"série {x['serial']}" if x.get("serial") else None) if p)
                    yield {"external_id": f"{itemtype}:{x.get('id')}", "name": x.get("name") or "", "category": AssetCategory.MATERIEL,
                           "description": f"{detail} (GLPI)", "location": _text(x.get("locations_id")),
                           "holder": _text(x.get("users_id")), "status": _status(x.get("states_id"))}
                total = int((r.headers.get("Content-Range") or "/0").rsplit("/", 1)[-1] or 0)
                start += PAGE
                if not rows or start >= total:
                    break
    finally:
        try:
            call("GLPI", "GET", f"{api}/killSession", headers=head)
        except ConnectorError:
            pass


KIND = Kind("glpi", "GLPI", "Ordinateurs, équipements réseau, imprimantes et téléphones du parc.",
            "Un compte GLPI dédié en lecture seule, son jeton d'API personnel, et un jeton d'application du client API.",
            [Param("url", "Adresse de GLPI", hint="https://glpi.exemple.tn"),
             Param("app_token", "Jeton d'application (App-Token)", secret=True),
             Param("user_token", "Jeton d'API de l'utilisateur", secret=True)],
            fetch, bound_to=("url",))
