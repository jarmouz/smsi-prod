import io

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, send_file)
from flask_login import login_required

from app.services import webdav
from app.services.access import editor_required

bp = Blueprint("docs", __name__, url_prefix="/docs")


def _require_enabled():
    if not webdav.enabled():
        abort(404)


def _breadcrumb(rel):
    crumbs = [{"name": "Docs", "rel": ""}]
    acc = []
    for seg in (rel or "").split("/"):
        if not seg:
            continue
        acc.append(seg)
        crumbs.append({"name": seg, "rel": "/".join(acc)})
    return crumbs


@bp.route("/")
@bp.route("/b/<path:rel>")
@login_required
def browse(rel=""):
    _require_enabled()
    try:
        rel = webdav.safe_rel(rel)
    except ValueError:
        abort(404)
    error = None
    entries = []
    try:
        entries = webdav.list_dir(rel)
    except Exception as e:  # noqa: BLE001
        error = f"Impossible d'accéder à Nextcloud : {e}"
    return render_template("docs/index.html", entries=entries, rel=rel,
                           crumbs=_breadcrumb(rel), error=error,
                           human_size=webdav.human_size)


@bp.route("/dl/<path:rel>")
@login_required
def download(rel):
    _require_enabled()
    try:
        data = webdav.download(rel)
    except Exception:  # noqa: BLE001
        abort(404)
    name = rel.rstrip("/").split("/")[-1]
    return send_file(io.BytesIO(data), as_attachment=True, download_name=name)


@bp.route("/upload", methods=["POST"])
@editor_required
def upload():
    _require_enabled()
    rel = webdav.safe_rel(request.form.get("rel", ""))
    files = request.files.getlist("files")
    n = 0
    for f in files:
        if f and f.filename:
            try:
                webdav.upload(rel, f.filename, f.read())
                n += 1
            except Exception as e:  # noqa: BLE001
                flash(f"Échec pour {f.filename} : {e}", "danger")
    if n:
        flash(f"{n} fichier(s) téléversé(s).", "success")
    return redirect(url_for("docs.browse", rel=rel) if rel else url_for("docs.browse"))


@bp.route("/mkdir", methods=["POST"])
@editor_required
def mkdir():
    _require_enabled()
    rel = webdav.safe_rel(request.form.get("rel", ""))
    name = (request.form.get("name") or "").strip()
    if name:
        try:
            webdav.mkdir(rel, name)
            flash("Dossier créé.", "success")
        except Exception as e:  # noqa: BLE001
            flash(f"Création impossible : {e}", "danger")
    return redirect(url_for("docs.browse", rel=rel) if rel else url_for("docs.browse"))


@bp.route("/delete", methods=["POST"])
@editor_required
def delete():
    _require_enabled()
    target = webdav.safe_rel(request.form.get("target", ""))
    parent = "/".join(target.split("/")[:-1])
    if target:
        try:
            webdav.delete(target)
            flash("Élément supprimé.", "success")
        except Exception as e:  # noqa: BLE001
            flash(f"Suppression impossible : {e}", "danger")
    return redirect(url_for("docs.browse", rel=parent) if parent else url_for("docs.browse"))
