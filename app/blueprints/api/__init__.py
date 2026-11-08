"""API REST en lecture seule (3.14), authentifiée par jeton d'organisation.

Seul l'en-tête « Authorization: Bearer <jeton> » donne accès : un cookie de session ne suffit pas.
Chaque appel authentifié est inscrit au journal d'activité de l'organisation."""
import re
import time
from datetime import date, datetime, timezone
from functools import wraps
from types import SimpleNamespace

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import case

from app.extensions import db
from app.models import ApiToken, Asset, AssetCategory, AssetStatus, Connector, Organization
from app.models.api_token import SCOPE_ASSETS_READ, SCOPE_ASSETS_WRITE, hash_token
from app.models.asset import NEED_KEYS, NEED_LEVELS
from app.services import connectors, inventory, tenancy
from app.services.audit_trail import _ip, log_event

bp = Blueprint("api", __name__, url_prefix="/api/v1")

RATE_LIMIT = 120           # appels par minute et par jeton
DEFAULT_PER_PAGE = 100
MAX_PER_PAGE = 500
MAX_PUSH = 1000


@bp.after_request
def _no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _error(status, code, message, headers=None):
    resp = jsonify({"erreur": {"code": code, "message": message}})
    resp.status_code = status
    resp.headers.update(headers or {})
    return resp


def _unauthorized(code, message):
    return _error(401, code, message, {"WWW-Authenticate": "Bearer"})


def _log(token, status, detail=""):
    actor = SimpleNamespace(id=None, name=f"API : {token.name}", organization_id=token.organization_id)
    path = request.full_path.rstrip("?")[:300]
    log_event("api", f"{request.method} {path} : {status}{detail}", user=actor)


def _hit(token_id):
    """Compte l'appel dans la minute courante (atomique, sur plusieurs processus) ; retourne le compteur."""
    minute, table = int(time.time() // 60), ApiToken.__table__
    stmt = (table.update().where(table.c.id == token_id).values(
        window_count=case((table.c.window_minute == minute, table.c.window_count + 1), else_=1),
        window_minute=minute, last_used_at=datetime.utcnow(), last_used_ip=_ip()).returning(table.c.window_count))
    with db.engine.begin() as conn:
        return conn.execute(stmt).scalar()


def token_required(scope):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            tenancy.set_current_org(None)       # un éventuel cookie de session n'a aucun effet ici
            scheme, _, raw = request.headers.get("Authorization", "").partition(" ")
            raw = raw.strip()
            if scheme.lower() != "bearer" or not raw:
                return _unauthorized("jeton_absent", "En-tête Authorization: Bearer <jeton> requis.")
            token = ApiToken.query.filter_by(token_hash=hash_token(raw)).first()
            if token is None:
                current_app.logger.warning("API : jeton inconnu depuis %s", _ip())
                return _unauthorized("jeton_invalide", "Jeton invalide.")
            tenancy.set_current_org(token.organization_id)
            if token.state != "actif":
                _log(token, 401, " (jeton révoqué)" if token.state == "revoque" else " (jeton expiré)")
                return _unauthorized(f"jeton_{token.state}", "Ce jeton n'est plus valide.")
            org = db.session.get(Organization, token.organization_id)
            if org is None or not org.is_active:
                return _error(403, "organisation_desactivee", "Organisation désactivée.")
            g.org = org
            if not token.allows(scope):
                _log(token, 403, " (portée insuffisante)")
                return _error(403, "portee_insuffisante", f"Portée {scope} requise.")
            if _hit(token.id) > RATE_LIMIT:
                retry = str(60 - int(time.time()) % 60)
                return _error(429, "trop_de_requetes", f"Limite de {RATE_LIMIT} appels par minute atteinte.",
                              {"Retry-After": retry})
            resp = fn(*a, **k)
            _log(token, resp.status_code, g.pop("api_detail", ""))
            return resp
        return wrapper
    return deco


def _iso(v):
    return v.isoformat() if v else None


def _person(u):
    return {"nom": u.name, "email": u.email} if u else None


def _link(a):
    return {"id": a.id, "reference": a.ref, "nom": a.name}


def serialize(a):
    needs = a.needs()
    return {
        "id": a.id, "reference": a.ref, "nom": a.name, "description": a.description,
        "role": "valeur_metier" if a.is_business else "bien_support",
        "categorie": a.category.value, "categorie_libelle": a.category.label,
        "classification": a.classification.value, "statut": a.status.value,
        "proprietaire": _person(a.owner), "depositaire": a.custodian, "detenteur": _person(a.holder),
        "localisation": a.location,
        "besoins": {k: {"propre": getattr(a, f"need_{k}"), "retenu": needs[k][0],
                        "herite_de": needs[k][1].ref if needs[k][1] is not None else None} for k, _ in NEED_KEYS},
        "criticite": a.criticality, "criticite_libelle": NEED_LEVELS.get(a.criticality),
        "biens_supports": [_link(x) for x in a.supports], "valeurs_metier": [_link(x) for x in a.supported],
        "risques": [r.ref for r in a.risks],
        "cycle_de_vie": {
            "mise_en_service": _iso(a.acquired_on), "fin_de_support": _iso(a.end_of_support),
            "etat_support": a.eos_state, "a_restituer": a.to_recover,
            "elimination": {"date": _iso(a.disposed_on), "methode": a.disposal_method, "preuve": a.disposal_proof,
                            "preuve_manquante": a.disposal_missing}},
        "source": {"connecteur": a.connector.name, "id_externe": a.external_id, "vu_le": _iso(a.source_seen_at),
                   "absent_depuis": _iso(a.source_missing_since)} if a.connector else None,
        "cree_le": _iso(a.created_at), "modifie_le": _iso(a.updated_at),
    }


def _int_arg(name, default, low, high):
    raw = request.args.get(name)
    if raw is None:
        return default
    if not raw.isdigit() or not low <= int(raw) <= high:
        raise inventory.InvalidFilter(name, raw)
    return int(raw)


def _since():
    raw = request.args.get("modifie_depuis")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace(" ", "+"))
    except ValueError:
        raise inventory.InvalidFilter("modifie_depuis", raw)
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


@bp.route("/actifs")
@token_required(SCOPE_ASSETS_READ)
def assets():
    try:
        page = _int_arg("page", 1, 1, 1_000_000)
        per = _int_arg("par_page", DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)
        since = _since()
        rows = inventory.filter_assets(request.args, strict=True, eager=True)
    except inventory.InvalidFilter as e:
        return _error(400, "parametre_invalide", str(e))
    ref = (request.args.get("reference") or "").strip().lower()
    if ref:
        rows = [a for a in rows if a.ref.lower() == ref]
    if since:
        rows = [a for a in rows if (a.updated_at or a.created_at) >= since]
    total = len(rows)
    pages = (total + per - 1) // per
    batch = rows[(page - 1) * per:page * per]
    g.api_detail = f" ({len(batch)} actif(s) sur {total})"
    return jsonify({"donnees": [serialize(a) for a in batch],
                    "pagination": {"page": page, "par_page": per, "total": total, "pages": pages,
                                   "suivante": page + 1 if page < pages else None}})


@bp.route("/actifs/<int:asset_id>")
@token_required(SCOPE_ASSETS_READ)
def asset(asset_id):
    a = db.session.get(Asset, asset_id)
    if a is None:
        return _error(404, "introuvable", "Actif introuvable.")
    g.api_detail = f" ({a.ref})"
    return jsonify(serialize(a))


def _push_item(n, x):
    """Élément reçu -> format du rapprochement ; ValueError avec un message si invalide."""
    if not isinstance(x, dict) or not x.get("id_externe") or not x.get("nom"):
        raise ValueError(f"actifs[{n}] : id_externe et nom sont requis.")
    item = {"external_id": str(x["id_externe"]), "name": str(x["nom"]), "category": AssetCategory.SERVICE}
    if x.get("categorie"):
        if x["categorie"] not in [c.value for c in AssetCategory]:
            raise ValueError(f"actifs[{n}] : categorie inconnue.")
        item["category"] = AssetCategory(x["categorie"])
    if x.get("statut"):
        if x["statut"] not in [c.value for c in AssetStatus]:
            raise ValueError(f"actifs[{n}] : statut inconnu.")
        item["status"] = AssetStatus(x["statut"])
    for src, dst in (("description", "description"), ("localisation", "location"), ("detenteur", "holder")):
        if x.get(src):
            item[dst] = str(x[src])
    for src, dst in (("mise_en_service", "acquired_on"), ("fin_de_support", "end_of_support")):
        if x.get(src):
            try:
                item[dst] = date.fromisoformat(str(x[src]))
            except ValueError:
                raise ValueError(f"actifs[{n}] : {src} doit être une date AAAA-MM-JJ.")
    return item


@bp.route("/actifs/synchronisation", methods=["POST"])
@token_required(SCOPE_ASSETS_WRITE)
def push():
    """Création et mise à jour par un outil, selon les mêmes règles que les connecteurs."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error(400, "corps_invalide", "Corps JSON attendu.")
    source, rows = str(body.get("source") or ""), body.get("actifs")
    if not re.fullmatch(r"[\w.-]{1,60}", source):
        return _error(400, "parametre_invalide", "source : 1 à 60 lettres, chiffres, points ou tirets.")
    if not isinstance(rows, list) or len(rows) > MAX_PUSH:
        return _error(400, "parametre_invalide", f"actifs : liste de {MAX_PUSH} éléments au maximum.")
    try:
        items = [_push_item(n, x) for n, x in enumerate(rows)]
    except ValueError as e:
        return _error(400, "parametre_invalide", str(e))
    simulate = body.get("simulation") is True
    c = Connector.query.filter_by(kind="api", name=source).first()
    if c is None:
        c = Connector(kind="api", name=source)
        db.session.add(c)
        db.session.commit()
    try:
        res = connectors.execute(c, items, apply=not simulate, complete=body.get("complet") is True)
    except connectors.ConnectorError as e:
        return _error(409, "synchronisation_impossible", str(e))
    g.api_detail = f" ({connectors.summary(res)})"
    return jsonify({"simulation": simulate, "creations": len(res["create"]), "mises_a_jour": len(res["update"]),
                    "rapproches": len(res["adopt"]), "inchanges": res["same"], "doublons": len(res["duplicate"]),
                    "absents": len(res["missing"]), "avertissement": res["warning"]})


@bp.route("/openapi.json")
def openapi():
    """Description de l'API, sans donnée : consultable sans jeton par les outils d'intégration."""
    from app.blueprints.api.spec import document
    return jsonify(document())
