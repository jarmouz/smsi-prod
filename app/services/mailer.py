import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from flask import current_app

from app.services import settings as settings_svc


def _open_smtp(cfg):
    if cfg["use_ssl"]:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
        if cfg["use_tls"]:
            server.starttls()
    if cfg["username"]:
        server.login(cfg["username"], cfg["password"])
    return server


def _deliver(app, cfg, to_email, subject, html):
    with app.app_context():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = formataddr((cfg["from_name"], cfg["from_address"]))
            msg["To"] = to_email
            msg.attach(MIMEText(html, "html", "utf-8"))
            server = _open_smtp(cfg)
            server.sendmail(cfg["from_address"], [to_email], msg.as_string())
            server.quit()
            app.logger.info("E-mail envoyé à %s (%s)", to_email, subject)
        except Exception as exc:
            app.logger.warning("E-mail non envoyé à %s : %s", to_email, exc)


def send_email(to_email, subject, html):
    """Envoi non bloquant. Ignoré silencieusement si SMTP non configuré."""
    if not to_email:
        return
    cfg = settings_svc.get_smtp_config()
    if not cfg:
        current_app.logger.info("SMTP non configuré - e-mail ignoré (%s)", subject)
        return
    app = current_app._get_current_object()
    threading.Thread(target=_deliver, args=(app, cfg, to_email, subject, html),
                     daemon=True).start()


def send_test(to_email, html):
    """Envoi synchrone pour le bouton « e-mail de test ». Retourne (ok, message)."""
    cfg = settings_svc.get_smtp_config()
    if not cfg:
        return False, "Renseignez d'abord le serveur SMTP."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Test - Suivi des demandes"
        msg["From"] = formataddr((cfg["from_name"], cfg["from_address"]))
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html", "utf-8"))
        server = _open_smtp(cfg)
        server.sendmail(cfg["from_address"], [to_email], msg.as_string())
        server.quit()
        return True, f"E-mail de test envoyé à {to_email}."
    except Exception as exc:
        return False, f"Échec de l'envoi : {exc}"


def send_now(to_email, subject, html, cfg=None):
    """Envoi synchrone (tâches planifiées). Retourne (ok, message)."""
    cfg = cfg or settings_svc.get_smtp_config()
    if not cfg:
        return False, "SMTP non configuré."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((cfg["from_name"], cfg["from_address"]))
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html", "utf-8"))
        server = _open_smtp(cfg)
        server.sendmail(cfg["from_address"], [to_email], msg.as_string())
        server.quit()
        return True, "envoyé"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
