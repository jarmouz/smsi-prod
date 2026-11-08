"""Synchronisation de l'inventaire avec des outils externes (3.15).

Règle centrale : la source alimente les faits techniques (nom, localisation, détenteur, dates).
Les besoins DIC+T, la classification, le propriétaire et les dépendances restent des décisions
humaines : ils ne sont jamais modifiés. Un actif disparu de la source est signalé, jamais supprimé.
"""
import base64
import hashlib
import ipaddress
import json
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
from urllib.parse import urlparse

import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from sqlalchemy import text

from app.extensions import db
from app.models import Asset, AssetCategory, AssetStatus, Classification, Connector, ConnectorRun, User
from app.services import importer

MAX_ITEMS = 20000
WEB_DEADLINE = 90        # secondes, sous la limite de gunicorn
HTTP_TIMEOUT = 30
UPDATED_FIELDS = ("name", "location", "status", "holder_id", "acquired_on", "end_of_support")


class ConnectorError(Exception):
    """Erreur présentable à l'utilisateur ; ne contient jamais de secret."""


@dataclass
class Param:
    key: str
    label: str
    secret: bool = False
    required: bool = True
    hint: str = ""


@dataclass
class Kind:
    key: str
    label: str
    summary: str
    access: str                       # droits minimaux à accorder
    params: list
    fetch: Callable
    bound_to: tuple = field(default=())   # paramètres dont le changement impose de ressaisir les secrets


# --- Secrets -------------------------------------------------------------------------------
def _fernet():
    digest = hashlib.sha256(b"integra-connectors:" + current_app.config["SECRET_KEY"].encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(secrets):
    return _fernet().encrypt(json.dumps(secrets).encode()).decode()


def unseal(token):
    if not token:
        return {}
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken:
        raise ConnectorError("Secrets illisibles (clé de l'application modifiée) : ressaisissez-les.")


# --- Appels sortants -----------------------------------------------------------------------
def check_url(url):
    """Refuse les adresses internes, sauf sur une installation qui l'autorise (GLPI du réseau local).
    Empêche d'atteindre la base ou les métadonnées de l'hébergeur à partir d'une URL saisie."""
    p = urlparse(url or "")
    allow_private = current_app.config.get("CONNECTORS_ALLOW_PRIVATE")
    if p.scheme not in ("https", "http") or not p.hostname:
        raise ConnectorError("Adresse invalide.")
    if p.scheme != "https" and not allow_private:
        raise ConnectorError("Adresse en https obligatoire.")
    try:
        addrs = {i[4][0] for i in socket.getaddrinfo(p.hostname, p.port or 443, type=socket.SOCK_STREAM)}
    except OSError:
        raise ConnectorError(f"Nom d'hôte introuvable : {p.hostname}.")
    for raw in addrs:
        ip = ipaddress.ip_address(raw)
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or (not ip.is_global and not allow_private):
            raise ConnectorError(f"Adresse interne refusée : {p.hostname}.")


def call(label, method, url, **kw):
    """Requête HTTP sans redirection ; attend brièvement en cas de limitation de débit par la source."""
    for attempt in range(4):
        try:
            r = requests.request(method, url, timeout=HTTP_TIMEOUT, allow_redirects=False, **kw)
        except requests.RequestException as e:
            raise ConnectorError(f"{label} injoignable ({e.__class__.__name__}).")
        if r.status_code in (429, 503) and attempt < 3:
            time.sleep(min(int(r.headers.get("Retry-After", "2") or 2), 10))
            continue
        if r.status_code >= 300:
            raise ConnectorError(f"{label} : réponse HTTP {r.status_code}. Vérifiez l'adresse et les droits accordés.")
        return r


# --- Registre ------------------------------------------------------------------------------
def kinds():
    from app.services.connectors import aws, glpi, microsoft
    return {k.key: k for k in (glpi.KIND, microsoft.INTUNE, microsoft.ENTRA, microsoft.AZURE, aws.KIND)}


def fetch(connector):
    kind = kinds().get(connector.kind)
    if kind is None:
        raise ConnectorError("Ce connecteur est alimenté par l'API : rien à lancer depuis Integra.")
    return kind.fetch(connector.config or {}, unseal(connector.secret_enc))


def test(connector):
    """Lit le premier élément de la source ; retourne son nom, ou None si la source est vide."""
    items = fetch(connector)
    try:
        first = next(iter(items), None)
    finally:
        if hasattr(items, "close"):
            items.close()
    return first["name"] if first else None


# --- Rapprochement -------------------------------------------------------------------------
def _people():
    by_email, by_name, by_local = {}, {}, {}
    for u in User.query.all():
        email = u.email.lower()
        by_email[email] = u
        by_name.setdefault(importer.norm(u.name), []).append(u)
        by_local.setdefault(email.split("@")[0], []).append(u)
    return by_email, by_name, by_local


def _holder(value, people):
    v = (value or "").strip()
    if not v:
        return None
    by_email, by_name, by_local = people
    if v.lower() in by_email:
        return by_email[v.lower()]
    for hits in (by_name.get(importer.norm(v), []), by_local.get(v.lower(), [])):
        if len(hits) == 1:
            return hits[0]
    return None


def _values(item, people):
    v = {"name": item["name"].strip()[:300]}
    for key in ("location",):
        if item.get(key):
            v[key] = str(item[key])[:255]
    for key in ("status", "acquired_on", "end_of_support"):
        if item.get(key):
            v[key] = item[key]
    holder = _holder(item.get("holder"), people)
    if holder:
        v["holder_id"] = holder.id
    return v


def plan_and_apply(connector, items, apply, complete=True, deadline=None):
    """Compare la source à l'inventaire ; écrit seulement si apply. Retourne le bilan."""
    res = {"create": [], "update": [], "adopt": [], "same": 0, "duplicate": [], "invalid": 0, "missing": [],
           "restored": 0, "warning": None}
    now = datetime.utcnow()
    assets = Asset.query.all()
    mine = {a.external_id: a for a in assets if a.connector_id == connector.id}
    free, foreign = {}, set()
    for a in assets:
        if a.connector_id is None:
            free.setdefault(importer.norm(a.name), []).append(a)
        elif a.connector_id != connector.id:
            foreign.add(importer.norm(a.name))
    alloc, people, seen = importer.RefAllocator([a.ref for a in assets], "ACT"), _people(), set()
    for count, item in enumerate(items, 1):
        if deadline and time.monotonic() > deadline:
            raise ConnectorError("Source trop volumineuse pour un lancement manuel : réduisez le périmètre ou planifiez le connecteur.")
        if count > MAX_ITEMS:
            raise ConnectorError(f"Plus de {MAX_ITEMS} éléments : réduisez le périmètre.")
        ext, name = str(item.get("external_id") or "").strip()[:255], (item.get("name") or "").strip()
        if not ext or not name:
            res["invalid"] += 1
            continue
        if ext in seen:
            continue
        seen.add(ext)
        key = importer.norm(name)
        a = mine.get(ext)
        adopted = False
        if a is None:
            candidates = free.get(key, [])
            if len(candidates) == 1:
                a, adopted = candidates.pop(), True
            elif key in foreign:
                res["duplicate"].append(name)
                continue
        vals = _values(item, people)
        if a is None:
            res["create"].append(name)
            if apply:
                db.session.add(Asset(ref=alloc.take(), name=vals["name"], category=item.get("category", AssetCategory.SERVICE),
                                     description=item.get("description"), classification=Classification.INTERNE,
                                     status=vals.get("status", AssetStatus.ACTIF), location=vals.get("location"),
                                     holder_id=vals.get("holder_id"), acquired_on=vals.get("acquired_on"),
                                     end_of_support=vals.get("end_of_support"), connector_id=connector.id,
                                     external_id=ext, source_seen_at=now))
            continue
        if a.status == AssetStatus.RETIRE:      # un retrait décidé dans Integra n'est jamais annulé par la source
            vals.pop("status", None)
        changes = {k: v for k, v in vals.items() if k in UPDATED_FIELDS and getattr(a, k) != v}
        if adopted:
            res["adopt"].append(name)
        elif changes:
            res["update"].append(name)
        else:
            res["same"] += 1
        if a.source_missing_since:
            res["restored"] += 1
        if apply:
            for k, v in changes.items():
                setattr(a, k, v)
            a.connector_id, a.external_id, a.source_seen_at, a.source_missing_since = connector.id, ext, now, None
    if complete and not seen and mine:
        res["warning"] = "La source n'a renvoyé aucun élément : aucune absence n'a été enregistrée."
    elif complete:
        for ext, a in mine.items():
            if ext not in seen and a.status != AssetStatus.RETIRE and not a.source_missing_since:
                res["missing"].append(a.name)
                if apply:
                    a.source_missing_since = now
    return res


def summary(res):
    parts = [f"{len(res['create'])} créé(s)", f"{len(res['update'])} mis à jour", f"{len(res['adopt'])} rapproché(s)",
             f"{res['same']} inchangé(s)", f"{len(res['missing'])} absent(s)"]
    if res["duplicate"]:
        parts.append(f"{len(res['duplicate'])} déjà suivi(s) par un autre connecteur")
    if res["invalid"]:
        parts.append(f"{res['invalid']} invalide(s)")
    return ", ".join(parts)


def _record(connector, status, text_):
    connector.last_run_at, connector.last_status, connector.last_summary = datetime.utcnow(), status, text_[:400]
    db.session.add(ConnectorRun(connector_id=connector.id, status=status, summary=text_[:400]))


def execute(connector, items, apply, complete=True, deadline=None):
    """Exécute le rapprochement sous verrou (un seul passage à la fois par connecteur)."""
    if not db.session.execute(text("SELECT pg_try_advisory_xact_lock(7710, :i)"), {"i": connector.id}).scalar():
        db.session.rollback()
        raise ConnectorError("Une synchronisation de ce connecteur est déjà en cours.")
    cid = connector.id
    try:
        res = plan_and_apply(connector, items, apply, complete, deadline)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        message = str(e) if isinstance(e, ConnectorError) else f"Erreur inattendue ({e.__class__.__name__})."
        if not isinstance(e, ConnectorError):
            current_app.logger.exception("Connecteur %s", cid)
        if apply:
            _record(db.session.get(Connector, cid), "erreur", message)
            db.session.commit()
        raise ConnectorError(message)
    if apply:
        text_ = summary(res) + (f". {res['warning']}" if res["warning"] else "")
        _record(connector, "ok", text_)
        db.session.commit()
    else:
        db.session.rollback()
    return res


def run(connector, apply, web=True):
    deadline = time.monotonic() + WEB_DEADLINE if web else None
    cid = connector.id
    try:
        items = fetch(connector)
    except ConnectorError as e:
        if apply:
            _record(db.session.get(Connector, cid), "erreur", str(e))
            db.session.commit()
        raise
    return execute(connector, items, apply, deadline=deadline)


def run_scheduled(log=print, org_slug=None):
    """Connecteurs en mode automatique de toutes les organisations (commande flask sync-connectors)."""
    from app.models import Organization
    from app.services.tenancy import tenant_scope
    q = Organization.query.filter_by(is_active=True)
    if org_slug:
        q = q.filter_by(slug=org_slug)
    stats = {"ok": 0, "erreur": 0}
    for org in q.all():
        with tenant_scope(org.id):
            for cid in [c.id for c in Connector.query.filter_by(auto=True).all()]:
                c = db.session.get(Connector, cid)
                try:
                    res = run(c, apply=True, web=False)
                    stats["ok"] += 1
                    log(f"{org.slug} / {c.name} : {summary(res)}")
                except ConnectorError as e:
                    stats["erreur"] += 1
                    log(f"{org.slug} / {cid} : ERREUR {e}")
    return stats
