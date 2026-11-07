import os


class Config:
    """Configuration de base, surchargée par les variables d'environnement."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-a-changer")

    # Sécurité des cookies de session (SECURE=1 en prod HTTPS ; 0 en dev HTTP local)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
    WTF_CSRF_TIME_LIMIT = None      # jeton CSRF valable le temps de la session
    # Anti-force-brute au login
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://smsi:smsi@localhost:5432/smsi",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Africa/Tunis")

    # URL publique par défaut pour les liens des e-mails (surchargée en admin).
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "")

    # Pièces jointes - backend de stockage : "local" ou "webdav" (Nextcloud)
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").lower()
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/data/uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "15")) * 1024 * 1024

    # Nextcloud (WebDAV) - compte de service, transparent pour l'utilisateur
    NEXTCLOUD_URL = os.environ.get("NEXTCLOUD_URL", "")            # https://docs.kaizen-intelligence.tn
    NEXTCLOUD_USER = os.environ.get("NEXTCLOUD_USER", "")          # compte de service, ex. smsi-svc
    NEXTCLOUD_PASSWORD = os.environ.get("NEXTCLOUD_PASSWORD", "")  # mot de passe d'application Nextcloud
    NEXTCLOUD_FOLDER = os.environ.get("NEXTCLOUD_FOLDER", "SMSI")  # ancien dossier des pièces jointes (avant multi-organisation)
    NEXTCLOUD_ATTACHMENTS_FOLDER = os.environ.get("NEXTCLOUD_ATTACHMENTS_FOLDER", "SMSI-PJ")  # pièces jointes : <dossier>/<slug>
    NEXTCLOUD_DOCS_FOLDER = os.environ.get("NEXTCLOUD_DOCS_FOLDER", "Documents")  # espace Docs historique (1re organisation)
    NEXTCLOUD_ORGS_FOLDER = os.environ.get("NEXTCLOUD_ORGS_FOLDER", "SMSI-Organisations")  # Docs des autres organisations
    NEXTCLOUD_TIMEOUT = int(os.environ.get("NEXTCLOUD_TIMEOUT", "20"))

    # OnlyOffice Document Server (édition en ligne des fichiers du module Docs)
    ONLYOFFICE_URL = os.environ.get("ONLYOFFICE_URL", "")                 # https://office.kaizen-intelligence.tn
    ONLYOFFICE_JWT_SECRET = os.environ.get("ONLYOFFICE_JWT_SECRET", "")   # secret partagé avec le Document Server
    # URL publique du SMSI joignable par le Document Server (défaut : APP_BASE_URL)
    ONLYOFFICE_CALLBACK_BASE = os.environ.get("ONLYOFFICE_CALLBACK_BASE", "")

    # Récapitulatifs par e-mail : domaines jamais destinataires (comptes de démonstration, tests)
    NOTIFY_SKIP_DOMAINS = os.environ.get("NOTIFY_SKIP_DOMAINS", ".demo,.local,.test,.example,example.com")

    APP_NAME = "Information Security"
