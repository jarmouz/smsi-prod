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
# Socle commun SMI (structure harmonisée ISO) : présent pour toute organisation,
# ce n'est pas une norme activable (pas d'OrgFramework, pas de rattachement d'éléments)
SOCLE = "SMI"


def _iso27001_items():
    from app.seed import ANNEX_A
    order = 0
    for theme, items in ANNEX_A.items():
        for ref, title in items:
            order += 1
            yield {"kind": "control", "ref": ref, "group": theme.value, "title": title, "sort_order": order}


def _items_from(groups, kind="control"):
    def gen():
        order = 0
        for group, items in groups:
            for ref, title in items:
                order += 1
                yield {"kind": kind, "ref": ref, "group": group, "title": title, "sort_order": order}
    return gen


def _catalogue(name, kind="control"):
    from app.services import catalogue_data
    return _items_from(getattr(catalogue_data, name), kind)()


# code -> définition. "items" est une fonction (évaluée à la synchronisation).
CATALOGUES = {
    SOCLE: {"name": "Socle commun SMI", "short_name": "Socle", "domain": "Exigences communes (structure harmonisée ISO)",
            "kind": "common", "sort_order": 1, "items": lambda: _catalogue("SOCLE", "clause")},
    ISO27001: {"name": "ISO/IEC 27001:2022", "short_name": "27001", "domain": "Sécurité de l'information",
               "kind": "controls", "sort_order": 10, "items": _iso27001_items},
    "ISO27701": {"name": "ISO/IEC 27701:2019", "short_name": "27701", "domain": "Protection de la vie privée",
                 "kind": "controls", "sort_order": 20, "items": lambda: _catalogue("ISO27701")},
    "ISO42001": {"name": "ISO/IEC 42001:2023", "short_name": "42001", "domain": "Intelligence artificielle",
                 "kind": "controls", "sort_order": 30, "items": lambda: _catalogue("ISO42001")},
    # Référentiels sans annexe de mesures : conformité évaluée exigence par exigence (chapitres 4 à 10)
    "ISO22301": {"name": "ISO 22301:2019", "short_name": "22301", "domain": "Continuité d'activité",
                 "kind": "requirements", "sort_order": 40, "items": lambda: _catalogue("ISO22301", "clause")},
    "ISO20000": {"name": "ISO/IEC 20000-1:2018", "short_name": "20000-1", "domain": "Management des services informatiques",
                 "kind": "requirements", "sort_order": 50, "items": lambda: _catalogue("ISO20000", "clause")},
    "ISO9001": {"name": "ISO 9001:2015", "short_name": "9001", "domain": "Management de la qualité",
                "kind": "requirements", "sort_order": 60, "items": lambda: _catalogue("ISO9001", "clause")},
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
    db.session.flush()
    _sync_mappings()
    db.session.commit()


def _common_map(code):
    from app.services.catalogue_data import COMMON
    return COMMON.get(code, {})


def common_relation(control):
    """(réf. socle, relation) d'une exigence de norme, ou None si elle est propre à la norme."""
    if control.framework is None:
        return None
    return _common_map(control.framework.code).get(control.ref)


def socle_framework():
    return get(SOCLE)


def ensure_common():
    """Crée le socle commun de l'organisation courante et y rattache les exigences
    des normes déjà activées. Idempotent ; ne modifie jamais une évaluation existante :
    une exigence déjà évaluée dans sa norme reste « évaluée séparément »."""
    fw = get(SOCLE)
    if fw is None:
        sync_catalogues()
        fw = get(SOCLE)
    socle = {c.ref: c for c in Control.query.filter_by(framework_id=fw.id)}
    for it in FrameworkItem.query.filter_by(framework_id=fw.id, kind="clause").order_by(FrameworkItem.sort_order):
        if it.ref not in socle:
            c = Control(framework_id=fw.id, ref=it.ref, theme=it.group, title=it.title,
                        applicable=True, status=ControlStatus.NON_DEMARRE)
            db.session.add(c)
            socle[it.ref] = c
    db.session.flush()
    for f in Framework.query.filter(Framework.kind == "requirements").all():
        cmap = _common_map(f.code)
        if not cmap:
            continue
        for c in Control.query.filter_by(framework_id=f.id).filter(Control.common_id.is_(None)):
            rel = cmap.get(c.ref)
            if rel is None:
                continue
            c.common_id = socle[rel[0]].id
            if rel[1] == "commune" and _untouched(c):
                c.inherit = True
                _copy_from(c, socle[rel[0]])
    db.session.flush()
    return fw


def _untouched(c):
    return (c.status == ControlStatus.NON_DEMARRE and c.applicable and not c.implementation
            and not c.justification and not c.owner_id and not c.evidences)


def _copy_from(c, s):
    c.applicable, c.status, c.owner_id = s.applicable, s.status, s.owner_id
    if not s.applicable and not c.justification:
        c.justification = s.justification


def propagate(socle_control):
    """Recopie l'évaluation d'une exigence du socle dans les exigences qui en héritent."""
    for c in Control.query.filter_by(common_id=socle_control.id, inherit=True):
        _copy_from(c, socle_control)
        c.justification = socle_control.justification if not socle_control.applicable else None


def heirs(socle_control):
    """Exigences des normes actives rattachées à une exigence du socle."""
    active_ids = {f.id for f in active()}
    rows = Control.query.filter_by(common_id=socle_control.id).all()
    for c in rows:
        c.socle_rel = common_relation(c)
    return sorted([c for c in rows if c.framework_id in active_ids], key=lambda c: (c.framework.sort_order, c.id))


def set_inherit(control, on):
    """Rattache (on) ou détache une exigence de l'évaluation du socle.
    Au rattachement, si le socle n'est pas encore évalué, l'évaluation de l'exigence
    y est reprise (rien n'est perdu) ; sinon c'est celle du socle qui s'applique."""
    if not control.common_id:
        return
    if on:
        s = control.common
        if s.status == ControlStatus.NON_DEMARRE and not s.implementation and control.status != ControlStatus.NON_DEMARRE:
            s.applicable, s.status, s.owner_id = control.applicable, control.status, control.owner_id
            s.justification = s.justification or control.justification
            s.implementation = control.implementation
            for e in control.evidences:
                if e not in s.evidences:
                    s.evidences.append(e)
            control.implementation = None
            propagate(s)
        control.inherit = True
        _copy_from(control, s)
    else:
        control.inherit = False
    db.session.flush()


def socle_stats():
    """Effet du socle pour l'organisation courante : exigences des normes actives
    couvertes par le socle (héritées / à compléter / évaluées séparément)."""
    active_ids = {f.id for f in active()}
    rows = [c for c in Control.query.filter(Control.common_id.isnot(None)).all() if c.framework_id in active_ids]
    out = {"heritees": 0, "complements": 0, "separees": 0}
    for c in rows:
        rel = common_relation(c)
        if c.inherited:
            out["heritees"] += 1
        elif rel and rel[1] == "complement":
            out["complements"] += 1
        else:
            out["separees"] += 1
    out["total"] = len(rows)
    return out


def _sync_mappings():
    from app.models import ItemMapping
    from app.services.catalogue_data import MAPPINGS
    ids = {(f.code, i.ref): i.id for f in Framework.query.all() for i in f.items if i.kind in ("control", "clause")}
    have = {(m.source_id, m.target_id) for m in ItemMapping.query.all()}
    for sc, sr, tc, tr in MAPPINGS:
        a, b = ids.get((sc, sr)), ids.get((tc, tr))
        if a and b and (a, b) not in have:
            db.session.add(ItemMapping(source_id=a, target_id=b, relation="partielle"))
            have.add((a, b))


def correspondences(control):
    """Mesures des AUTRES normes actives de l'organisation qui correspondent à cette mesure
    (correspondances proposées, dans les deux sens)."""
    from app.models import ItemMapping
    item = (FrameworkItem.query.filter_by(framework_id=control.framework_id, ref=control.ref)
            .filter(FrameworkItem.kind.in_(("control", "clause"))).first())
    if item is None:
        return []
    pairs = ItemMapping.query.filter(db.or_(ItemMapping.source_id == item.id, ItemMapping.target_id == item.id)).all()
    other_ids = {m.target_id if m.source_id == item.id else m.source_id for m in pairs}
    if not other_ids:
        return []
    active_ids = {f.id for f in active()}
    out = []
    for it in FrameworkItem.query.filter(FrameworkItem.id.in_(other_ids)).all():
        if it.framework_id in active_ids:
            c = Control.query.filter_by(framework_id=it.framework_id, ref=it.ref).first()
            # deux exigences rattachées au même élément du socle : le lien passe déjà par le socle
            if c and not (control.common_id and c.common_id == control.common_id):
                out.append(c)
    return sorted(out, key=lambda c: (c.framework.sort_order, c.id))


def controls_frameworks():
    """Socle commun puis normes actives évaluées élément par élément : mesures (DdA) ou exigences (conformité)."""
    socle = get(SOCLE)
    fws = [f for f in active() if f.kind in ("controls", "requirements")]
    if socle is not None and Control.query.filter_by(framework_id=socle.id).first() is not None:
        fws.insert(0, socle)
    return fws


def get(code):
    return Framework.query.filter_by(code=code).first()


def all_frameworks():
    """Normes activables (le socle commun n'en est pas une)."""
    return Framework.query.filter(Framework.kind != "common").order_by(Framework.sort_order, Framework.id).all()


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
    if fw is None or not fw.available or fw.kind == "common":
        raise ValueError(f"Référentiel indisponible : {code}")
    of = OrgFramework.query.filter_by(framework_id=fw.id).first()
    if of is None:
        db.session.add(OrgFramework(framework_id=fw.id, enabled=True))
    else:
        of.enabled = True
    if fw.kind in ("controls", "requirements"):        # mesures (DdA) ou exigences (conformité)
        have = {c.ref for c in Control.query.filter_by(framework_id=fw.id)}
        item_kind = "control" if fw.kind == "controls" else "clause"
        for it in FrameworkItem.query.filter_by(framework_id=fw.id, kind=item_kind).order_by(FrameworkItem.sort_order):
            if it.ref not in have:
                db.session.add(Control(framework_id=fw.id, ref=it.ref, theme=it.group, title=it.title,
                                       applicable=True, status=ControlStatus.NON_DEMARRE))
    db.session.flush()
    ensure_common()
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
    with db.engine.begin() as conn:     # colonnes élargies avant d'y écrire les groupes longs
        conn.execute(text("ALTER TABLE framework_items ALTER COLUMN \"group\" TYPE VARCHAR(80)"))
    sync_catalogues()
    fid = get(ISO27001).id
    cols = {c["name"] for c in inspect(db.engine).get_columns("controls")}
    with db.engine.begin() as conn:
        if "framework_id" not in cols:
            conn.execute(text("ALTER TABLE controls ADD COLUMN framework_id INTEGER REFERENCES frameworks(id)"))
        conn.execute(text("UPDATE controls SET framework_id = :f WHERE framework_id IS NULL"), {"f": fid})
        conn.execute(text("ALTER TABLE controls ALTER COLUMN framework_id SET NOT NULL"))
        conn.execute(text("ALTER TABLE controls ALTER COLUMN theme TYPE VARCHAR(80)"))
        conn.execute(text("ALTER TABLE framework_items ALTER COLUMN \"group\" TYPE VARCHAR(80)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_controls_framework_id ON controls (framework_id)"))
        conn.execute(text("ALTER TABLE controls DROP CONSTRAINT IF EXISTS uq_controls_org_ref"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_controls_org_fw_ref "
                          "ON controls (organization_id, framework_id, ref)"))
        conn.execute(text(
            "INSERT INTO org_frameworks (organization_id, framework_id, enabled, enabled_at) "
            "SELECT o.id, :f, true, now() FROM organizations o "
            "WHERE NOT EXISTS (SELECT 1 FROM org_frameworks x WHERE x.organization_id = o.id AND x.framework_id = :f)"),
            {"f": fid})
    # Socle commun SMI (3.4) pour chaque organisation
    from app.models import Organization
    from app.services.tenancy import tenant_scope
    for org in Organization.query.all():
        with tenant_scope(org.id):
            ensure_common()
    db.session.commit()
    return fid
