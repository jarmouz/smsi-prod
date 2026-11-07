"""Reprise de l'existant : import guidé (fichier -> correspondance -> aperçu -> import)."""
from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort, Response, jsonify,
                   current_app)
from flask_login import current_user

from app.extensions import db
from app.services import importer
from app.services.access import editor_required
from app.services.tenancy import current_org_id

bp = Blueprint("imports", __name__, url_prefix="/import")


def _spec(kind):
    spec = importer.SPECS.get(kind)
    if spec is None:
        abort(404)
    return spec


def _load(kind, token):
    try:
        return importer.load(token, current_org_id(), current_user.id, kind)
    except importer.ImportError_ as e:
        flash(str(e), "danger")
        return None


@bp.route("/<kind>", methods=["GET", "POST"])
@editor_required
def upload(kind):
    spec = _spec(kind)
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename:
            flash("Sélectionnez un fichier Excel (.xlsx) ou CSV.", "danger")
            return redirect(url_for("imports.upload", kind=kind))
        from app.services import ai, docimport
        if docimport.ext_of(f.filename) in ai.EXTRACT_EXT:
            if not ai.enabled():
                flash("Fichier Word ou PDF : enregistrez le tableau au format Excel (.xlsx), ou demandez au RSSI "
                      "d'activer l'assistance IA, qui sait en extraire les lignes.", "warning")
                return redirect(url_for("imports.upload", kind=kind))
            token = _start_extraction(kind, f.filename, f.read())
            return redirect(url_for("imports.extraction", kind=kind, token=token))
        try:
            sheets = importer.read_file(f)
        except importer.ImportError_ as e:
            flash(str(e), "danger")
            return redirect(url_for("imports.upload", kind=kind))
        # feuille par défaut : celle dont les en-têtes ressemblent le plus aux champs attendus
        best = max(sheets, key=lambda s: len(importer.auto_map(
            sheets[s][importer.detect_header(sheets[s], spec)], spec)))
        st = {"kind": kind, "org": current_org_id(), "user": current_user.id, "filename": f.filename[:200],
              "sheets": sheets, "sheet": best}
        _reset_sheet(st, spec)
        token = importer.save(st)
        return redirect(url_for("imports.mapping", kind=kind, token=token))
    from app.services import ai
    return render_template("imports/upload.html", kind=kind, spec=spec, ai_on=ai.enabled())


def _reset_sheet(st, spec, header_row=None):
    rows = st["sheets"][st["sheet"]]
    st["header_row"] = importer.detect_header(rows, spec) if header_row is None else header_row
    headers, _ = importer.table(st)
    st["mapping"] = importer.auto_map(headers, spec)


@bp.route("/<kind>/<token>/correspondance", methods=["GET", "POST"])
@editor_required
def mapping(kind, token):
    spec = _spec(kind)
    st = _load(kind, token)
    if st is None:
        return redirect(url_for("imports.upload", kind=kind))
    if st.get("job", {}).get("status") == "running":
        return redirect(url_for("imports.extraction", kind=kind, token=token))
    if request.method == "POST":
        if request.form.get("action") == "ai":
            from app.services import ai
            headers, _ = importer.table(st)
            try:
                mp, note = ai.suggest_mapping(spec, headers, importer.samples(st, limit=5))
                st["mapping"], st["ai_mapped"] = mp, sorted(mp)
                importer.save(st)
                flash("Correspondance proposée par l'IA : vérifiez chaque champ avant de continuer."
                      + (f" Remarque : {note}" if note else ""), "success")
            except ai.AIError as e:
                flash(str(e), "danger")
            return redirect(url_for("imports.mapping", kind=kind, token=token))
        if request.form.get("action") == "reload":
            # autre feuille ou autre ligne d'en-têtes : nouvelle proposition de correspondance
            sheet = request.form.get("sheet")
            hr = request.form.get("header_row", type=int)
            if sheet in st["sheets"] and sheet != st["sheet"]:
                st["sheet"] = sheet
                _reset_sheet(st, spec)
            elif hr:
                _reset_sheet(st, spec, max(0, min(hr - 1, len(st["sheets"][st["sheet"]]) - 1)))
            importer.save(st)
            return redirect(url_for("imports.mapping", kind=kind, token=token))
        headers, _ = importer.table(st)
        mp, used = {}, {}
        for fdef in spec["fields"]:
            v = request.form.get("f_" + fdef["key"], "")
            if v.isdigit() and int(v) < len(headers):
                if int(v) in used:
                    flash(f"La colonne {importer.col_letter(int(v))} est associée à deux champs "
                          f"({used[int(v)]} et {fdef['label']}).", "danger")
                    return redirect(url_for("imports.mapping", kind=kind, token=token))
                mp[fdef["key"]] = int(v)
                used[int(v)] = fdef["label"]
        missing = [f["label"] for f in spec["fields"] if f["required"] and f["key"] not in mp]
        if missing or not any(k in mp for k in spec["needs_one_of"]):
            need = missing or [next(f["label"] for f in spec["fields"] if f["key"] == k) for k in spec["needs_one_of"]]
            flash("Associez au moins : " + " ou ".join(need) + ".", "danger")
            st["mapping"] = mp
            importer.save(st)
            return redirect(url_for("imports.mapping", kind=kind, token=token))
        st["mapping"] = mp
        importer.save(st)
        return redirect(url_for("imports.preview", kind=kind, token=token))
    from app.services import ai
    headers, data = importer.table(st)
    return render_template("imports/mapping.html", kind=kind, spec=spec, st=st, token=token, ai_on=ai.enabled(),
                           headers=headers, nrows=len(data), samples=importer.samples(st),
                           col_letter=importer.col_letter)


@bp.route("/<kind>/<token>/apercu", methods=["GET", "POST"])
@editor_required
def preview(kind, token):
    spec = _spec(kind)
    st = _load(kind, token)
    if st is None:
        return redirect(url_for("imports.upload", kind=kind))
    if st.get("job", {}).get("status") == "running":
        return redirect(url_for("imports.extraction", kind=kind, token=token))
    if request.method == "POST" and request.form.get("action") == "options":
        # échelles de cotation du fichier (import des risques)
        opts = {}
        for axis in ("likelihood", "impact"):
            n = request.form.get("scale_" + axis, type=int)
            if n and 2 <= n <= 10:
                opts["scale_" + axis] = n
        st["options"] = opts
        importer.save(st)
        return redirect(url_for("imports.preview", kind=kind, token=token))
    if request.method == "POST":
        from app.services.audit_trail import log_event
        stats, counts = importer.apply(st)
        db.session.commit()
        done = ", ".join(f"{n} {lbl}" for lbl, n in (("créé(s)", stats.get("create", 0)),
                                                       ("mis à jour", stats.get("update", 0))) if n) or "aucune modification"
        log_event("import", f"Import {spec['title']} depuis « {st['filename']} » : {done}"
                  + (f", {counts['error']} ligne(s) en erreur ignorée(s)" if counts["error"] else ""))
        importer.discard(token)
        flash(f"Import terminé : {done}." + (f" {counts['error']} ligne(s) en erreur ignorée(s)." if counts["error"] else ""),
              "success")
        return redirect(url_for(spec["back"]))
    plan, counts, ctx = importer.plan(st)
    db.session.rollback()
    labels = {f["key"]: f["label"] for f in spec["fields"]}
    headers, _ = importer.table(st)
    used = [(labels[k], headers[c] or importer.col_letter(c)) for k, c in st["mapping"].items() if k in labels]
    return render_template("imports/preview.html", kind=kind, spec=spec, st=st, token=token,
                           plan=plan, counts=counts, used=used, notice=ctx.get("notice"))


@bp.route("/<kind>/<token>/annuler", methods=["POST"])
@editor_required
def cancel(kind, token):
    spec = _spec(kind)
    importer.discard(token)
    flash("Import annulé : aucune donnée modifiée.", "warning")
    return redirect(url_for(spec["back"]))


@bp.route("/<kind>/modele.xlsx")
@editor_required
def template(kind):
    _spec(kind)
    name = {"dda": "dda_actuelle_modele_import.xlsx", "actifs": "modele_import_actifs.xlsx",
            "risques": "modele_import_risques.xlsx", "fournisseurs": "modele_import_fournisseurs.xlsx"}[kind]
    return Response(importer.template_xlsx(kind),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={name}"})


# --- Dépôt en masse de documents --------------------------------------------
def _doc_ctx(token):
    from app.services import docimport
    return docimport.locked(token, current_org_id(), current_user.id)


@bp.route("/documents")
@editor_required
def docs_start():
    from app.services import docimport
    token = docimport.create(current_org_id(), current_user.id)
    return redirect(url_for("imports.docs_upload", token=token))


@bp.route("/documents/<token>")
@editor_required
def docs_upload(token):
    from app.services import docimport
    try:
        st = docimport.load(token, current_org_id(), current_user.id)
    except importer.ImportError_ as e:
        flash(str(e), "danger")
        return redirect(url_for("documents.index"))
    return render_template("imports/docs_upload.html", token=token, items=st["items"],
                           exts=sorted(docimport.DOC_EXT), max_mb=current_app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024))


@bp.route("/documents/<token>/fichiers", methods=["POST"])
@editor_required
def docs_add(token):
    """Reçoit un ou plusieurs fichiers (le navigateur les envoie un par un)."""
    from app.services import docimport
    added, errors = 0, []
    try:
        with _doc_ctx(token) as st:
            for f in request.files.getlist("files"):
                if f and f.filename:
                    n, errs = docimport.add_upload(st, token, f.filename, f.read())
                    added += n
                    errors += errs
            total = len(st["items"])
    except importer.ImportError_ as e:
        if request.accept_mimetypes.best == "application/json":
            return jsonify(ok=False, errors=[str(e)]), 400
        flash(str(e), "danger")
        return redirect(url_for("documents.index"))
    if request.accept_mimetypes.best == "application/json":
        return jsonify(ok=True, added=added, errors=errors, total=total)
    if added:
        flash(f"{added} fichier(s) ajouté(s).", "success")
    for e in errors[:20]:
        flash(e, "warning")
    return redirect(url_for("imports.docs_upload", token=token))


@bp.route("/documents/<token>/retirer/<int:item_id>", methods=["POST"])
@editor_required
def docs_remove(token, item_id):
    import os
    from app.services import docimport
    try:
        with _doc_ctx(token) as st:
            for it in [i for i in st["items"] if i["id"] == item_id]:
                st["items"].remove(it)
                try:
                    os.remove(os.path.join(docimport._dir(token), it["stored"]))
                except OSError:
                    pass
    except importer.ImportError_ as e:
        flash(str(e), "danger")
    return redirect(request.form.get("next") or url_for("imports.docs_upload", token=token))


@bp.route("/documents/<token>/apercu", methods=["GET", "POST"])
@editor_required
def docs_preview(token):
    from app.services import docimport
    from app.models import Document, User, DocType, Role
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    can_approve = current_user.role == Role.RSSI
    try:
        st = docimport.load(token, current_org_id(), current_user.id)
    except importer.ImportError_ as e:
        flash(str(e), "danger")
        return redirect(url_for("documents.index"))
    if not st["items"]:
        flash("Déposez au moins un fichier.", "warning")
        return redirect(url_for("imports.docs_upload", token=token))
    if request.method == "POST":
        edits = {}
        for it in st["items"]:
            k = str(it["id"])
            dt = request.form.get(f"type_{k}", "AUTRE")
            edits[k] = {"include": bool(request.form.get(f"inc_{k}")),
                        "title": (request.form.get(f"title_{k}") or "").strip()[:300],
                        "ref": (request.form.get(f"ref_{k}") or "").strip()[:32],
                        "doc_type": dt if dt in DocType.__members__ else "AUTRE",
                        "version": (request.form.get(f"version_{k}") or "1.0").strip()[:16] or "1.0",
                        "owner_id": request.form.get(f"owner_{k}", type=int),
                        "approved": (request.form.get(f"approved_{k}") or "").strip()[:10],
                        "controls": (request.form.get(f"controls_{k}") or "").strip()[:300],
                        "summary": (request.form.get(f"summary_{k}") or "").strip()[:400]}
        opts = {"mode": request.form.get("mode", "BROUILLON"),
                "review_months": max(1, min(60, request.form.get("review_months", 12, type=int) or 12))}
        if opts["mode"] == "APPROUVE" and not can_approve:
            opts["mode"] = "BROUILLON"
        with _doc_ctx(token) as stl:
            stl["edits"], stl["options"] = edits, opts
        missing = [e for e in edits.values() if e["include"] and not e["title"]]
        if missing:
            flash("Chaque document retenu doit avoir un titre.", "danger")
            return redirect(url_for("imports.docs_preview", token=token))
        if request.form.get("action") != "create":
            return redirect(url_for("imports.docs_preview", token=token))
        st = docimport.load(token, current_org_id(), current_user.id)
        _, _, remaining = docimport.create_documents(st, token, current_user)
        if remaining:       # lot suivant : la page se renvoie automatiquement
            return redirect(url_for("imports.docs_preview", token=token, suite=1))
        st = docimport.load(token, current_org_id(), current_user.id)
        created, errors = st.get("created", []), st.get("failed", [])
        from app.services.audit_trail import log_event
        if created:
            log_event("import", f"Dépôt en masse : {len(created)} document(s) créé(s) "
                      + ("approuvés (reprise de l'existant)" if opts["mode"] == "APPROUVE" else "en brouillon"))
            flash(f"{len(created)} document(s) créé(s) : {created[0]}"
                  + (f" à {created[-1]}" if len(created) > 1 else "") + ".", "success")
        for e in errors[:20]:
            flash(e + " Déposez-le à nouveau si besoin.", "danger")
        docimport.discard(token)              # les fichiers non retenus sont abandonnés
        return redirect(url_for("documents.index"))
    rows = docimport.proposal(st, users, Document.query.all())
    return render_template("imports/docs_preview.html", token=token, rows=rows, users=users, DocType=DocType,
                           can_approve=can_approve, opts=st.get("options", {}),
                           progress=(len(st.get("created", [])) if request.args.get("suite") else None),
                           ai_on=_ai_on())


@bp.route("/documents/<token>/annuler", methods=["POST"])
@editor_required
def docs_cancel(token):
    from app.services import docimport
    try:
        docimport.load(token, current_org_id(), current_user.id)
        docimport.discard(token)
    except importer.ImportError_:
        pass
    flash("Dépôt annulé : aucun document créé.", "warning")
    return redirect(url_for("documents.index"))


# --- Extraction d'un registre depuis un Word / PDF (assistance IA) ------------
def _start_extraction(kind, filename, data):
    import threading
    st = {"kind": kind, "org": current_org_id(), "user": current_user.id, "filename": filename[:200],
          "sheets": {}, "sheet": "", "header_row": 0, "mapping": {},
          "job": {"status": "running", "started": __import__("time").time()}}
    token = importer.save(st)
    args = (current_app._get_current_object(), kind, token, current_org_id(), current_user.id, filename, data)
    if current_app.config.get("AI_SYNC_JOBS"):
        _run_extraction(*args)
    else:
        threading.Thread(target=_run_extraction, args=args, daemon=True).start()
    return token


def _run_extraction(app, kind, token, org_id, user_id, filename, data):
    from flask import g
    from app.models import User
    from app.services import ai
    with app.app_context():
        g.org_id = org_id
        spec = importer.SPECS[kind]
        st = importer.load(token, org_id, user_id, kind)
        try:
            user = db.session.get(User, user_id)
            headers, rows, note = ai.extract_table(spec, filename, data, user=user)
            if not rows:
                raise ai.AIError("Aucune ligne de registre trouvée dans ce document.")
            st["sheets"] = {"Extrait par l'IA": [headers] + rows}
            st["sheet"], st["header_row"] = "Extrait par l'IA", 0
            st["mapping"] = importer.auto_map(headers, spec)
            st["job"] = {"status": "done", "note": note, "rows": len(rows)}
        except ai.AIError as e:
            st["job"] = {"status": "error", "message": str(e)}
        except Exception as e:  # noqa: BLE001
            app.logger.exception("Extraction IA")
            st["job"] = {"status": "error", "message": f"Erreur inattendue ({e.__class__.__name__})."}
        importer.save(st)


@bp.route("/<kind>/<token>/extraction")
@editor_required
def extraction(kind, token):
    import time
    spec = _spec(kind)
    st = _load(kind, token)
    if st is None:
        return redirect(url_for("imports.upload", kind=kind))
    job = st.get("job") or {"status": "done"}
    if job["status"] == "running" and time.time() - job.get("started", 0) > 900:
        job = {"status": "error", "message": "L'extraction n'a pas abouti (délai dépassé) : réessayez."}
    if job["status"] == "error":
        importer.discard(token)
        flash(job["message"], "danger")
        return redirect(url_for("imports.upload", kind=kind))
    if job["status"] == "done":
        flash(f"L'IA a extrait {job.get('rows', 0)} ligne(s) de « {st['filename']} ». Vérifiez la correspondance "
              "puis l'aperçu : les valeurs sont reprises telles qu'écrites dans le document."
              + (f" Remarque : {job['note']}" if job.get("note") else ""), "success")
        return redirect(url_for("imports.mapping", kind=kind, token=token))
    return render_template("imports/extraction.html", kind=kind, spec=spec, st=st, token=token,
                           elapsed=int(time.time() - job.get("started", time.time())))


def _ai_on():
    from app.services import ai
    return ai.enabled()


@bp.route("/documents/<token>/ia/<int:item_id>", methods=["POST"])
@editor_required
def docs_ai(token, item_id):
    """Analyse d'un document par l'IA (appelé ligne par ligne depuis la page de vérification)."""
    from app.services import ai, docimport
    from app.models import User
    try:
        st = docimport.load(token, current_org_id(), current_user.id)
        it = next((i for i in st["items"] if i["id"] == item_id), None)
        if it is None:
            return jsonify(ok=False, error="Fichier introuvable."), 404
        if docimport.ext_of(it["name"]) not in ai.EXTRACT_EXT | {"xlsx", "xlsm", "pptx", "ods", "odp"}:
            return jsonify(ok=False, error="Format non analysable par l'IA."), 400
        res = ai.analyze_document(it["name"], docimport.read_file(token, it), it["path"])
    except (ai.AIError, importer.ImportError_) as e:
        return jsonify(ok=False, error=str(e)), 400
    with _doc_ctx(token) as stl:
        for i in stl["items"]:
            if i["id"] == item_id:
                i["ai"] = res
        stl.setdefault("edits", {}).pop(str(item_id), None)     # la proposition IA remplace les saisies
    users = User.query.filter_by(is_active_flag=True).all()
    from app.services.importer import match_user
    owner = match_user(res["owner_hint"], users) if res["owner_hint"] else None
    return jsonify(ok=True, **res, owner_id=owner.id if owner else None)
