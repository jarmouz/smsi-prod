import io

from flask import (Blueprint, render_template, request, redirect, url_for,
                   abort, send_file, jsonify, current_app)
from flask_login import login_required, current_user

from app.services import webdav, onlyoffice as oo
from app.services.tenancy import set_current_org

bp = Blueprint("onlyoffice", __name__, url_prefix="/office")


def _require_enabled():
    if not oo.enabled():
        abort(404)


@bp.route("/edit/<path:rel>")
@login_required
def edit(rel):
    _require_enabled()
    try:
        rel = webdav.safe_rel(rel)
    except ValueError:
        abort(404)
    if not oo.is_editable(rel.split("/")[-1]):
        abort(400)
    can_edit = current_user.can_edit
    config = oo.build_config(rel, current_user, can_edit)
    api_js = current_app.config["ONLYOFFICE_URL"].rstrip("/") + "/web-apps/apps/api/documents/api.js"
    parent = "/".join(rel.split("/")[:-1])
    back = url_for("docs.browse", rel=parent) if parent else url_for("docs.browse")
    return render_template("onlyoffice/editor.html", config=config, api_js=api_js,
                           title=rel.split("/")[-1], back=back)


@bp.route("/fichier/<token>")
def serve_file(token):
    """Sert le fichier au Document Server (authentifié par jeton signé)."""
    _require_enabled()
    rel, org_id = oo.read_token(token, "dl")
    if not rel:
        abort(403)
    set_current_org(org_id)
    try:
        data = webdav.download(rel)
    except Exception:  # noqa: BLE001
        abort(404)
    return send_file(io.BytesIO(data), download_name=rel.split("/")[-1])


@bp.route("/temp/<token>")
def serve_temp(token):
    """Fichier temporaire à convertir, servi au Document Server (jeton signé, usage unique)."""
    data = oo.read_temp(token)
    if data is None:
        abort(403)
    return send_file(io.BytesIO(data), download_name="export.bin", mimetype="application/octet-stream")


@bp.route("/callback/<token>", methods=["POST"])
def callback(token):
    """Callback de sauvegarde du Document Server."""
    _require_enabled()
    rel, org_id = oo.read_token(token, "cb")
    if not rel:
        return jsonify({"error": 1}), 403
    set_current_org(org_id)

    body = request.get_json(force=True, silent=True) or {}

    # Vérification JWT OnlyOffice si un secret est configuré
    secret = current_app.config.get("ONLYOFFICE_JWT_SECRET")
    if secret:
        raw = body.get("token")
        if not raw:
            auth = request.headers.get("Authorization", "")
            raw = auth[7:] if auth.startswith("Bearer ") else ""
        try:
            decoded = oo.verify(raw)
            if decoded:
                body = decoded
        except Exception:  # noqa: BLE001
            return jsonify({"error": 1}), 403

    status = body.get("status")
    # 2 = prêt à sauvegarder, 6 = sauvegarde forcée (forcesave)
    if status in (2, 6):
        file_url = body.get("url")
        if file_url:
            try:
                import requests
                data = requests.get(file_url, timeout=60).content
                parent = "/".join(rel.split("/")[:-1])
                webdav.upload(parent, rel.split("/")[-1], data)
            except Exception as e:  # noqa: BLE001
                current_app.logger.warning("OnlyOffice save KO: %s", e)
                return jsonify({"error": 1})
    return jsonify({"error": 0})
