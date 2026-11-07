"""Référentiels : catalogues, activation par organisation, rattachement des éléments communs.

Le catalogue de chaque norme est décrit dans CATALOGUES et synchronisé en base
(sync_catalogues, idempotent) au démarrage (flask upgrade-db) et à l'installation.
"""
from sqlalchemy import text, inspect

from app.extensions import db
from app.models import (Framework, FrameworkItem, OrgFramework, FrameworkLink, Control, ControlStatus,
                        ISO27001)

# Référentiel toujours actif tant que l'application est construite autour de lui
CORE = ISO27001


def _iso27001_items():
    from app.seed import ANNEX_A
    order = 0
    for theme, items in ANNEX_A.items():
        for ref, title in items:
            order += 1
            yield {"kind": "control", "ref": ref, "group": theme.value, "title": title, "sort_order": order}


# code -> définition. "items" est une fonction (évaluée à la synchronisation).
CATALOGUES = {
    ISO27001: {"name": "ISO/IEC 27001:2022", "short_name": "27001", "domain": "Sécurité de l'information",
               "kind": "controls", "sort_order": 10, "items": _iso27001_items},
}


# --------------------------------------------------------------------------
# Catalogues (niveau plateforme)
# --------------------------------------------------------------------------
def sync_catalogues():
    """Crée ou met à jour les référentiels et leurs éléments. Ne supprime rien."""
    for code, d in CATALOGUES.items():
        fw = Framework.query.filter_by(code=code).first()
        if fw is None:
            fw = Framework(code=code)
            db.session.add(fw)
        fw.name, fw.short_name, fw.domain = d["name"], d["short_name"], d["domain"]
        fw.kind, fw.sort_order, fw.available = d["kind"], d["sort_order"], True
        db.session.flush()
        existing = {(i.kind, i.ref): i for i in FrameworkItem.query.filter_by(framework_id=fw.id)}
        for it in d["items"]():
            row = existing.get((it["kind"], it["ref"]))
            if row is None:
                row = FrameworkItem(framework_id=fw.id, kind=it["kind"], ref=it["ref"])
                db.session.add(row)
            row.group, row.title, row.sort_order = it["group"], it["title"], it["sort_order"]
    db.session.commit()


def get(code):
    return Framework.query.filter_by(code=code).first()


def all_frameworks():
    return Framework.query.order_by(Framework.sort_order, Framework.id).all()


# --------------------------------------------------------------------------
# Activation par organisation (contexte d'organisation courant)
# --------------------------------------------------------------------------
def active():
    """Référentiels activés par l'organisation courante, dans l'ordre d'affichage."""
    return (Framework.query.join(OrgFramework, OrgFramework.framework_id == Framework.id)
            .filter(OrgFramework.enabled.is_(True))
            .order_by(Framework.sort_order, Framework.id).all())


def is_enabled(code):
    return any(f.code == code for f in active())


def enable(code):
    """Active une norme pour l'organisation courante et copie son catalogue de mesures
    (seulement les mesures absentes : rappeler enable ne duplique rien)."""
    fw = get(code)
    if fw is None:
        sync_catalogues()
        fw = get(code)
    if fw is None or not fw.available:
        raise ValueError(f"Référentiel indisponible : {code}")
    of = OrgFramework.query.filter_by(framework_id=fw.id).first()
    if of is None:
        db.session.add(OrgFramework(framework_id=fw.id, enabled=True))
    else:
        of.enabled = True
    if fw.kind == "controls":
        have = {c.ref for c in Control.query.filter_by(framework_id=fw.id)}
        for it in FrameworkItem.query.filter_by(framework_id=fw.id, kind="control").order_by(FrameworkItem.sort_order):
            if it.ref not in have:
                db.session.add(Control(framework_id=fw.id, ref=it.ref, theme=it.group, title=it.title,
                                       applicable=True, status=ControlStatus.NON_DEMARRE))
    db.session.flush()
    return fw


def disable(code):
    """Désactive une norme (les données sont conservées et réapparaissent à la réactivation)."""
    if code == CORE:
        raise ValueError("L'ISO 27001 ne peut pas être désactivée.")
    fw = get(code)
    of = fw and OrgFramework.query.filter_by(framework_id=fw.id).first()
    if of:
        of.enabled = False
        db.session.flush()


# --------------------------------------------------------------------------
# Rattachement des éléments communs à des normes
# --------------------------------------------------------------------------
def _etype(entity):
    return type(entity).__name__


def frameworks_of(entity):
    """Normes auxquelles l'élément est rattaché ; liste vide = toutes les normes actives."""
    return (Framework.query.join(FrameworkLink, FrameworkLink.framework_id == Framework.id)
            .filter(FrameworkLink.entity_type == _etype(entity), FrameworkLink.entity_id == entity.id)
            .order_by(Framework.sort_order).all())


def set_links(entity, codes):
    """Remplace les rattachements de l'élément (codes de normes actives ; vide = toutes)."""
    allowed = {f.code: f for f in active()}
    wanted = {allowed[c].id for c in codes if c in allowed}
    if wanted and len(wanted) == len(allowed):
        wanted = set()                      # toutes les normes actives = pas de restriction
    rows = FrameworkLink.query.filter_by(entity_type=_etype(entity), entity_id=entity.id).all()
    for r in rows:
        if r.framework_id not in wanted:
            db.session.delete(r)
    have = {r.framework_id for r in rows}
    for fid in wanted - have:
        db.session.add(FrameworkLink(entity_type=_etype(entity), entity_id=entity.id, framework_id=fid))


def links_from_form(entity, form):
    """Lit les cases « fw » d'un formulaire (macro framework_picker), si elles sont présentes."""
    if form.get("fw_present"):
        set_links(entity, form.getlist("fw"))


def delete_links(entity):
    FrameworkLink.query.filter_by(entity_type=_etype(entity), entity_id=entity.id).delete()


# --------------------------------------------------------------------------
# Migration d'une base mono-référentiel (versions 2.x) : idempotente
# --------------------------------------------------------------------------
def migrate():
    """Rattache les mesures existantes à l'ISO 27001 et l'active pour chaque organisation.
    Appelée par flask upgrade-db après db.create_all()."""
    sync_catalogues()
    fid = get(ISO27001).id
    cols = {c["name"] for c in inspect(db.engine).get_columns("controls")}
    with db.engine.begin() as conn:
        if "framework_id" not in cols:
            conn.execute(text("ALTER TABLE controls ADD COLUMN framework_id INTEGER REFERENCES frameworks(id)"))
        conn.execute(text("UPDATE controls SET framework_id = :f WHERE framework_id IS NULL"), {"f": fid})
        conn.execute(text("ALTER TABLE controls ALTER COLUMN framework_id SET NOT NULL"))
        conn.execute(text("ALTER TABLE controls ALTER COLUMN theme TYPE VARCHAR(40)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_controls_framework_id ON controls (framework_id)"))
        conn.execute(text("ALTER TABLE controls DROP CONSTRAINT IF EXISTS uq_controls_org_ref"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_controls_org_fw_ref "
                          "ON controls (organization_id, framework_id, ref)"))
        conn.execute(text(
            "INSERT INTO org_frameworks (organization_id, framework_id, enabled, enabled_at) "
            "SELECT o.id, :f, true, now() FROM organizations o "
            "WHERE NOT EXISTS (SELECT 1 FROM org_frameworks x WHERE x.organization_id = o.id AND x.framework_id = :f)"),
            {"f": fid})
    return fid
