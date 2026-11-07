from datetime import datetime, date, timedelta

import click

from app.extensions import db
from app.models import (
    Organization, User, Setting, Control, Risk, Audit, Finding, CorrectiveAction,
    ManagementReview, ReviewAction, Document, Evidence,
    Asset, Incident, AwarenessAction,
    Role, Theme, ControlStatus, Treatment, RiskStatus,
    AuditStatus, FindingType, ActionStatus, DocStatus, DocType, ReviewStatus,
    AssetCategory, Classification, AssetStatus,
    IncidentCategory, IncidentSeverity, IncidentStatus, AwarenessType, AwarenessStatus,
)

# ---------------------------------------------------------------------------
# Catalogue Annexe A ISO/IEC 27001:2022 - 93 mesures, 4 thèmes.
# (référence + intitulé ; le texte normatif complet reste dans la norme)
# ---------------------------------------------------------------------------
ANNEX_A = {
    Theme.ORGANISATIONNELLE: [
        ("5.1", "Politiques de sécurité de l'information"),
        ("5.2", "Fonctions et responsabilités liées à la sécurité de l'information"),
        ("5.3", "Séparation des tâches"),
        ("5.4", "Responsabilités de la direction"),
        ("5.5", "Relations avec les autorités"),
        ("5.6", "Relations avec des groupes de travail spécialisés"),
        ("5.7", "Renseignement sur les menaces"),
        ("5.8", "Sécurité de l'information dans la gestion de projet"),
        ("5.9", "Inventaire des informations et autres actifs associés"),
        ("5.10", "Utilisation correcte des informations et autres actifs associés"),
        ("5.11", "Restitution des actifs"),
        ("5.12", "Classification des informations"),
        ("5.13", "Marquage des informations"),
        ("5.14", "Transfert des informations"),
        ("5.15", "Contrôle d'accès"),
        ("5.16", "Gestion des identités"),
        ("5.17", "Informations d'authentification"),
        ("5.18", "Droits d'accès"),
        ("5.19", "Sécurité de l'information dans les relations avec les fournisseurs"),
        ("5.20", "La sécurité de l'information dans les accords conclus avec les fournisseurs"),
        ("5.21", "Gestion de la sécurité de l'information dans la chaîne d'approvisionnement TIC"),
        ("5.22", "Surveillance, revue et gestion des changements des services fournisseurs"),
        ("5.23", "Sécurité de l'information pour l'utilisation de services en nuage"),
        ("5.24", "Planification et préparation de la gestion des incidents"),
        ("5.25", "Évaluation et décision concernant les événements de sécurité"),
        ("5.26", "Réponse aux incidents de sécurité de l'information"),
        ("5.27", "Tirer des enseignements des incidents de sécurité"),
        ("5.28", "Recueil de preuves"),
        ("5.29", "Sécurité de l'information durant une perturbation"),
        ("5.30", "Préparation des TIC pour la continuité d'activité"),
        ("5.31", "Exigences légales, statutaires, réglementaires et contractuelles"),
        ("5.32", "Droits de propriété intellectuelle"),
        ("5.33", "Protection des enregistrements"),
        ("5.34", "Protection de la vie privée et des données à caractère personnel"),
        ("5.35", "Revue indépendante de la sécurité de l'information"),
        ("5.36", "Conformité aux politiques, règles et normes de sécurité"),
        ("5.37", "Procédures d'exploitation documentées"),
    ],
    Theme.HUMAINE: [
        ("6.1", "Sélection des candidats"),
        ("6.2", "Conditions d'embauche"),
        ("6.3", "Sensibilisation, apprentissage et formation à la sécurité"),
        ("6.4", "Processus disciplinaire"),
        ("6.5", "Responsabilités après la fin ou le changement d'un emploi"),
        ("6.6", "Engagements de confidentialité ou de non-divulgation"),
        ("6.7", "Travail à distance"),
        ("6.8", "Signalement des événements de sécurité de l'information"),
    ],
    Theme.PHYSIQUE: [
        ("7.1", "Périmètres de sécurité physique"),
        ("7.2", "Entrées physiques"),
        ("7.3", "Sécurisation des bureaux, des salles et des équipements"),
        ("7.4", "Surveillance de la sécurité physique"),
        ("7.5", "Protection contre les menaces physiques et environnementales"),
        ("7.6", "Travail dans les zones sécurisées"),
        ("7.7", "Bureau propre et écran verrouillé"),
        ("7.8", "Emplacement et protection du matériel"),
        ("7.9", "Sécurité des actifs hors des locaux"),
        ("7.10", "Supports de stockage"),
        ("7.11", "Services supports"),
        ("7.12", "Sécurité du câblage"),
        ("7.13", "Maintenance du matériel"),
        ("7.14", "Mise au rebut ou réutilisation sécurisée du matériel"),
    ],
    Theme.TECHNOLOGIQUE: [
        ("8.1", "Terminaux finaux des utilisateurs"),
        ("8.2", "Privilèges d'accès"),
        ("8.3", "Restriction d'accès à l'information"),
        ("8.4", "Accès au code source"),
        ("8.5", "Authentification sécurisée"),
        ("8.6", "Dimensionnement"),
        ("8.7", "Protection contre les programmes malveillants"),
        ("8.8", "Gestion des vulnérabilités techniques"),
        ("8.9", "Gestion de la configuration"),
        ("8.10", "Suppression des informations"),
        ("8.11", "Masquage des données"),
        ("8.12", "Prévention de la fuite de données"),
        ("8.13", "Sauvegarde des informations"),
        ("8.14", "Redondance des moyens de traitement de l'information"),
        ("8.15", "Journalisation"),
        ("8.16", "Activités de surveillance"),
        ("8.17", "Synchronisation des horloges"),
        ("8.18", "Utilisation de programmes utilitaires à privilèges"),
        ("8.19", "Installation de logiciels sur des systèmes en exploitation"),
        ("8.20", "Sécurité des réseaux"),
        ("8.21", "Sécurité des services réseau"),
        ("8.22", "Cloisonnement des réseaux"),
        ("8.23", "Filtrage web"),
        ("8.24", "Utilisation de la cryptographie"),
        ("8.25", "Cycle de vie de développement sécurisé"),
        ("8.26", "Exigences de sécurité des applications"),
        ("8.27", "Principes d'ingénierie et d'architecture des systèmes sécurisés"),
        ("8.28", "Codage sécurisé"),
        ("8.29", "Tests de sécurité dans le développement et l'acceptation"),
        ("8.30", "Développement externalisé"),
        ("8.31", "Séparation des environnements de développement, test et production"),
        ("8.32", "Gestion des changements"),
        ("8.33", "Informations de test"),
        ("8.34", "Protection des systèmes d'information pendant les tests d'audit"),
    ],
}


# Évolutions de schéma idempotentes (flask upgrade-db) ; les nouvelles tables
# (activity_logs, document_versions...) sont créées par db.create_all().
UPGRADE_DDL = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_logins INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_readonly BOOLEAN NOT NULL DEFAULT false",
    # P1 : double authentification et politique de mot de passe
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64) NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_last_step BIGINT NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_codes TEXT NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP NULL",
    # P1 : acceptation formelle des risques résiduels
    "ALTER TABLE risks ADD COLUMN IF NOT EXISTS accepted_by_id INTEGER NULL REFERENCES users(id)",
    "ALTER TABLE risks ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMP NULL",
    "ALTER TABLE risks ADD COLUMN IF NOT EXISTS accepted_score INTEGER NULL",
    "ALTER TABLE risks ADD COLUMN IF NOT EXISTS acceptance_note TEXT NULL",
    "ALTER TABLE risks ADD COLUMN IF NOT EXISTS acceptance_until DATE NULL",
    # P1 : circuit d'approbation des documents
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS change_summary TEXT NULL",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS submitted_by_id INTEGER NULL REFERENCES users(id)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP NULL",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS approved_by_id INTEGER NULL REFERENCES users(id)",
    # P2 : actions correctives rattachables à une non-conformité (10.2)
    "ALTER TABLE corrective_actions ALTER COLUMN finding_id DROP NOT NULL",
    "ALTER TABLE corrective_actions ADD COLUMN IF NOT EXISTS nonconformity_id INTEGER NULL "
    "REFERENCES nonconformities(id) ON DELETE CASCADE",
    "CREATE INDEX IF NOT EXISTS ix_corrective_actions_nonconformity_id ON corrective_actions (nonconformity_id)",
    # P3 : récapitulatif des échéances par e-mail
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS digest_frequency VARCHAR(12) NOT NULL DEFAULT 'HEBDO'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_digest_at TIMESTAMP NULL",
    # ISO 9001 (3.3) : risques qualité et opportunités, produits et services non conformes
    "ALTER TABLE risks ADD COLUMN IF NOT EXISTS risk_domain VARCHAR(16) NULL",
    "ALTER TABLE risks ADD COLUMN IF NOT EXISTS nature VARCHAR(12) NULL",
    "CREATE INDEX IF NOT EXISTS ix_risks_risk_domain ON risks (risk_domain)",
    "ALTER TABLE nonconformities ADD COLUMN IF NOT EXISTS nc_kind VARCHAR(12) NULL",
    "ALTER TABLE nonconformities ADD COLUMN IF NOT EXISTS product VARCHAR(300) NULL",
    "ALTER TABLE nonconformities ADD COLUMN IF NOT EXISTS disposition VARCHAR(16) NULL",
]

# Tables rattachées à une organisation (voir TenantMixin)
TENANT_TABLES = ["users", "controls", "risks", "audits", "findings", "corrective_actions",
                 "management_reviews", "review_actions", "documents", "evidence",
                 "attachments", "assets", "incidents", "awareness_actions"]
REF_TABLES = ["controls", "risks", "audits", "management_reviews", "documents", "evidence",
              "assets", "incidents", "awareness_actions"]


def register_seed_command(app):
    @app.cli.command("upgrade-db")
    def upgrade_db():
        """Applique les évolutions de schéma SANS effacer les données :
        cree les nouvelles tables manquantes et ajoute les colonnes de verrouillage."""
        from sqlalchemy import text
        db.create_all()  # cree uniquement les tables absentes (attachments, assets, incidents, awareness_actions...)
        with db.engine.begin() as conn:
            for ddl in UPGRADE_DDL:
                conn.execute(text(ddl))
        # Référentiels (3.0) : catalogues à jour, mesures existantes rattachées à l'ISO 27001
        from app.services import frameworks
        frameworks.migrate()
        click.echo("Schéma mis à jour (tables manquantes créées, colonnes ajoutées).")


    @app.cli.command("migrate-multitenant")
    @click.option("--org-name", default=None, help="Nom de l'organisation existante (défaut : paramètre org_name).")
    @click.option("--slug", default="default", show_default=True)
    @click.option("--superadmin", "superadmins", multiple=True, help="E-mail(s) à promouvoir super-admin.")
    def migrate_multitenant(org_name, slug, superadmins):
        """Passe une base mono-organisation en multi-organisation, SANS perte :
        toutes les données existantes sont rattachées à une organisation par défaut.
        Idempotent : peut être relancé sans effet de bord."""
        from flask import current_app
        from sqlalchemy import text, inspect

        Organization.__table__.create(db.engine, checkfirst=True)
        insp = inspect(db.engine)
        settings_cols = {c["name"] for c in insp.get_columns("settings")}

        with db.engine.begin() as conn:
            org_id = conn.execute(text("SELECT id FROM organizations ORDER BY id LIMIT 1")).scalar()
            if org_id is None:
                if not org_name:
                    q = ("SELECT value FROM settings WHERE key='org_name'"
                         + (" AND organization_id IS NULL" if "organization_id" in settings_cols else ""))
                    org_name = conn.execute(text(q)).scalar() or "Mon entreprise"
                # les Docs existants restent à la racine actuelle
                docs = (current_app.config.get("NEXTCLOUD_DOCS_FOLDER") or "Documents").strip("/")
                org_id = conn.execute(text(
                    "INSERT INTO organizations (name, slug, docs_folder, is_active, created_at) "
                    "VALUES (:n, :s, :d, true, now()) RETURNING id"),
                    {"n": org_name, "s": slug, "d": docs}).scalar()
                click.echo(f"Organisation par défaut créée : {org_name} (id {org_id}).")

            for table in TENANT_TABLES:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS organization_id "
                                  f"INTEGER REFERENCES organizations(id)"))
                n = conn.execute(text(f"UPDATE {table} SET organization_id = :o "
                                      f"WHERE organization_id IS NULL"), {"o": org_id}).rowcount
                conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN organization_id SET NOT NULL"))
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_organization_id "
                                  f"ON {table} (organization_id)"))
                if n:
                    click.echo(f"  {table} : {n} ligne(s) rattachée(s).")

            # Références (R-2026-0001, 5.1...) uniques par organisation, plus globalement
            for table in REF_TABLES:
                exists = conn.execute(text("SELECT 1 FROM pg_constraint WHERE conname = :c"),
                                      {"c": f"uq_{table}_org_ref"}).scalar()
                if not exists:
                    conn.execute(text(f"DROP INDEX IF EXISTS ix_{table}_ref"))
                    conn.execute(text(f"CREATE INDEX ix_{table}_ref ON {table} (ref)"))
                    conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT uq_{table}_org_ref "
                                      f"UNIQUE (organization_id, ref)"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superadmin "
                              "BOOLEAN NOT NULL DEFAULT false"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_readonly "
                              "BOOLEAN NOT NULL DEFAULT false"))

            # Paramètres : globaux (organization_id NULL) sauf le nom de l'organisation
            if "organization_id" not in settings_cols:
                conn.execute(text("ALTER TABLE settings DROP CONSTRAINT settings_pkey"))
                conn.execute(text("ALTER TABLE settings ADD COLUMN id SERIAL PRIMARY KEY"))
                conn.execute(text("ALTER TABLE settings ADD COLUMN organization_id "
                                  "INTEGER REFERENCES organizations(id)"))
                conn.execute(text("CREATE INDEX ix_settings_organization_id ON settings (organization_id)"))
                conn.execute(text("CREATE UNIQUE INDEX uq_settings_org_key "
                                  "ON settings (COALESCE(organization_id, 0), key)"))
                conn.execute(text("UPDATE settings SET organization_id = :o WHERE key = 'org_name'"),
                             {"o": org_id})

            for email in superadmins:
                n = conn.execute(text("UPDATE users SET is_superadmin = true WHERE email = :e"),
                                 {"e": email.strip().lower()}).rowcount
                click.echo(f"  super-admin {email} : {'OK' if n else 'INTROUVABLE'}")

        click.echo("Migration multi-organisation terminée.")

    @app.cli.command("create-org")
    @click.argument("name")
    @click.option("--slug", default=None)
    @click.option("--admin-email", default=None, help="Crée le premier RSSI de l'organisation.")
    @click.option("--admin-name", default=None)
    @click.option("--admin-password", default=None, help="Défaut : mot de passe temporaire généré.")
    def create_org(name, slug, admin_email, admin_name, admin_password):
        """Crée une organisation avec son catalogue Annexe A."""
        from app.services.organizations import create_organization
        org, user = create_organization(name, slug=slug, admin_email=admin_email,
                                        admin_name=admin_name, admin_password=admin_password)
        click.echo(f"Organisation {org.name} créée (id {org.id}, slug {org.slug}).")
        if user:
            click.echo(f"RSSI : {user.email} - mot de passe temporaire : {user.temp_password} (à changer à la 1re connexion)")

    def _org(slug):
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            raise click.ClickException(f"Organisation « {slug} » introuvable (voir create-org).")
        return org

    def _finish(dry_run):
        if dry_run:
            db.session.rollback()
            click.echo("Simulation (--dry-run) : rien n'a été modifié.")
        else:
            db.session.commit()
            click.echo("Terminé.")

    @app.cli.command("move-user")
    @click.argument("emails", nargs=-1, required=True)
    @click.option("--to", "to_slug", required=True, help="Slug de l'organisation cible.")
    @click.option("--dry-run", is_flag=True, help="Affiche ce qui serait fait sans rien modifier.")
    def move_user(emails, to_slug, dry_run):
        """Déplace un ou plusieurs comptes vers une autre organisation.
        Déplacez d'abord leurs objets (move-records) : ceux restés dans l'origine
        perdent leur référence au compte (propriétaire, responsable...)."""
        from app.services.organizations import move_users
        target = _org(to_slug)
        users = []
        for e in emails:
            u = User.query.filter_by(email=e.strip().lower()).first()
            if not u:
                raise click.ClickException(f"Utilisateur {e} introuvable.")
            users.append(u)
        move_users(users, target, click.echo)
        _finish(dry_run)

    @app.cli.command("move-records")
    @click.argument("kind", type=click.Choice(["risk", "document", "evidence", "asset", "incident",
                                               "awareness", "audit", "review"]))
    @click.argument("refs", nargs=-1, required=True)
    @click.option("--from", "from_slug", required=True, help="Slug de l'organisation d'origine.")
    @click.option("--to", "to_slug", required=True, help="Slug de l'organisation cible.")
    @click.option("--dry-run", is_flag=True, help="Affiche ce qui serait fait sans rien modifier.")
    def move_records_cmd(kind, refs, from_slug, to_slug, dry_run):
        """Déplace des objets (par référence, ex. SENS-2026-0001) vers une autre
        organisation, avec pièces jointes, constats et actions. Les liens vers les
        mesures sont repris par référence dans la cible."""
        from app.services.organizations import move_records
        source, target = _org(from_slug), _org(to_slug)
        if source.id == target.id:
            raise click.ClickException("Origine et cible identiques.")
        try:
            move_records(kind, refs, source, target, click.echo)
        except ValueError as e:
            db.session.rollback()
            raise click.ClickException(str(e))
        _finish(dry_run)

    @app.cli.command("demo-org")
    def demo_org_cmd():
        """Crée l'organisation de démonstration, ou la réinitialise entièrement
        (données, pièces jointes, fichiers Docs). Sans effet sur les autres organisations."""
        from app import demo_content
        from app.services import demo
        try:
            org = demo.load(click.echo)
        except RuntimeError as e:
            raise click.ClickException(str(e))
        click.echo(f"Organisation de démo prête : {org.name} (slug {org.slug}).")
        click.echo(f"Comptes : <rôle>@{demo_content.DOMAIN} - mot de passe : {demo_content.DEMO_PASSWORD}")
        for key, (name, role, job) in demo_content.USERS.items():
            click.echo(f"  {key + '@' + demo_content.DOMAIN:<22} {role:<13} {name} - {job}")
        click.echo(f"Compte prospects (lecture seule) : {demo_content.PROSPECT[0]}@{demo_content.DOMAIN} "
                   f"- mot de passe : {demo_content.PROSPECT_PASSWORD}")
        click.echo(f"Administrateur démo (lecture seule) : {demo_content.DEMO_ADMIN[0]}@{demo_content.DOMAIN} "
                   f"- mot de passe : {demo_content.DEMO_ADMIN_PASSWORD}")

    @app.cli.command("send-reminders")
    @click.option("--dry-run", is_flag=True, help="Liste ce qui serait envoyé, sans envoyer.")
    @click.option("--org", "org_slug", default=None, help="Limiter à une organisation (slug).")
    @click.option("--force", is_flag=True, help="Ignorer la fréquence choisie (envoi à tous ceux qui ont des échéances).")
    def send_reminders(dry_run, org_slug, force):
        """Récapitulatif des échéances par e-mail (à lancer chaque jour par cron)."""
        from flask import current_app
        from app.services import reminders
        base = current_app.config.get("APP_BASE_URL") or "http://localhost"
        with current_app.test_request_context("/", base_url=base):
            stats = reminders.run(dry_run=dry_run, org_slug=org_slug, force=force, log=click.echo)
        click.echo(f"{datetime.utcnow():%Y-%m-%d %H:%M} UTC - " + ", ".join(f"{k} : {v}" for k, v in stats.items()))

    @app.cli.command("make-superadmin")
    @click.argument("email")
    def make_superadmin(email):
        """Donne les droits de super-administrateur de la plateforme."""
        u = User.query.filter_by(email=email.strip().lower()).first()
        if not u:
            raise click.ClickException("Utilisateur introuvable.")
        u.is_superadmin = True
        db.session.commit()
        click.echo(f"{u.email} est super-admin.")

    @app.cli.command("reset-password")
    @click.argument("email")
    @click.option("--keep-mfa", is_flag=True, help="Conserver la double authentification du compte.")
    def reset_password(email, keep_mfa):
        """Secours : mot de passe temporaire pour un compte (ex. seul RSSI ayant perdu son accès).
        Déverrouille le compte, réactive le compte s'il était désactivé, et supprime la double
        authentification (sauf --keep-mfa). Le mot de passe est à changer à la connexion suivante."""
        from app.services import totp
        from app.services.audit_trail import log_event
        from app.services.tenancy import tenant_scope
        u = (User.query.execution_options(all_tenants=True)
             .filter_by(email=email.strip().lower()).first())
        if not u:
            raise click.ClickException(f"Aucun compte « {email} ». Liste des comptes : "
                                       "docker compose exec db psql -U smsi -d smsi -c 'select email from users'")
        with tenant_scope(u.organization_id):
            temp = totp.temporary_password()
            u.set_password(temp)
            u.must_change_password = True
            u.is_active_flag = True
            if not keep_mfa:
                u.totp_secret = u.totp_last_step = u.recovery_codes = None
            u.reset_failures()
            db.session.commit()
            log_event("mfa", "Accès réinitialisé en ligne de commande (mot de passe temporaire"
                      + ("" if keep_mfa else ", double authentification à reconfigurer") + ")", entity=u)
        click.echo(f"Compte {u.email} : mot de passe temporaire {temp}")
        click.echo("À changer à la prochaine connexion" + ("." if keep_mfa else " ; double authentification supprimée."))

    @app.cli.command("init-platform")
    @click.option("--org-name", default=None, help="Nom de l'organisation du client.")
    @click.option("--admin-email", default=None, help="E-mail du premier RSSI (super-administrateur).")
    @click.option("--admin-name", default="Responsable SMSI", show_default=True)
    def init_platform(org_name, admin_email, admin_name):
        """Installation : crée le schéma, l'organisation et son RSSI (mot de passe saisi).
        Refuse de s'exécuter si la base contient déjà des utilisateurs."""
        from sqlalchemy import inspect
        from app.services import totp
        from app.services.organizations import create_organization

        if inspect(db.engine).has_table("users") and \
                db.session.query(User).execution_options(all_tenants=True).count() > 0:
            raise click.ClickException("La base contient déjà des utilisateurs : rien n'a été modifié. "
                                       "Pour mettre le schéma à jour : flask upgrade-db")
        org_name = (org_name or click.prompt("Nom de l'organisation")).strip()
        admin_email = (admin_email or click.prompt("E-mail du compte RSSI")).strip().lower()
        while True:
            password = click.prompt("Mot de passe du compte RSSI", hide_input=True,
                                    confirmation_prompt="Confirmation")
            err = totp.password_problem(password, admin_email)
            if not err:
                break
            click.secho(err, fg="yellow")

        db.create_all()
        from app.services import frameworks
        frameworks.sync_catalogues()
        for k, v in [("smtp_from_name", "Integra"), ("smtp_port", "587"),
                     ("smtp_use_tls", "1"), ("notifications_enabled", "1")]:
            db.session.add(Setting(key=k, value=v))
        db.session.commit()
        org, user = create_organization(org_name, admin_email=admin_email, admin_name=admin_name,
                                        admin_password=password)
        user.must_change_password = False      # choisi à l'instant par le RSSI
        user.is_superadmin = True
        db.session.commit()
        click.echo(f"Organisation « {org.name} » créée ({Control.query.execution_options(all_tenants=True).filter_by(organization_id=org.id).count()} mesures de l'Annexe A).")
        click.echo(f"Compte RSSI (super-administrateur) : {user.email}")

    @app.cli.command("init-db")
    @click.option("--demo/--no-demo", default=True, help="Injecter un jeu de démonstration.")
    @click.option("--yes", is_flag=True, help="Ne pas demander confirmation si la base contient des données.")
    def init_db(demo, yes):
        """DÉVELOPPEMENT : EFFACE la base, recrée le schéma et des comptes de test (mot de passe smsi123).
        Pour une installation réelle : flask init-platform."""
        from sqlalchemy import inspect
        if inspect(db.engine).has_table("users") and \
                db.session.query(User).execution_options(all_tenants=True).count() > 0 and not yes:
            click.secho("ATTENTION : init-db va EFFACER toutes les données de toutes les organisations.",
                        fg="red", bold=True)
            click.confirm("Tapez y pour effacer définitivement la base", abort=True)
        db.drop_all()
        db.create_all()
        from app.services import frameworks
        frameworks.sync_catalogues()

        # Réglages par défaut (globaux : hérités par toutes les organisations)
        for k, v in [("smtp_from_name", "Integra"), ("smtp_port", "587"),
                     ("smtp_use_tls", "1"), ("notifications_enabled", "1")]:
            db.session.add(Setting(key=k, value=v))
        db.session.commit()

        # Organisation par défaut + catalogue Annexe A (93 mesures)
        from app.services.organizations import create_organization
        from app.services.tenancy import tenant_scope
        org, _ = create_organization("Mon entreprise", slug="default")

        with tenant_scope(org.id):
            # Utilisateurs
            rssi = _u("rssi@smsi.local", "Responsable SMSI", Role.RSSI, "RSSI")
            rssi.is_superadmin = True
            contrib = _u("contrib@smsi.local", "Contributeur SMSI", Role.CONTRIBUTEUR, "Correspondant sécurité")
            auditor = _u("auditeur@smsi.local", "Auditeur Interne", Role.AUDITEUR, "Auditeur interne")
            reader = _u("lecteur@smsi.local", "Lecteur Direction", Role.LECTEUR, "Direction")
            db.session.commit()

            if demo:
                _seed_demo(rssi, contrib, auditor)

        click.echo("Base SMSI initialisée.")
        click.echo(f"Catalogue Annexe A : {Control.query.filter_by(organization_id=org.id).count()} mesures.")
        click.echo("Connexions (mot de passe : smsi123) :")
        click.echo("  rssi@smsi.local      - RSSI (accès complet, super-admin)")
        click.echo("  contrib@smsi.local   - Contributeur")
        click.echo("  auditeur@smsi.local  - Auditeur interne")
        click.echo("  lecteur@smsi.local   - Lecteur")


def _u(email, name, role, job):
    u = User(email=email, name=name, role=role, job_title=job)
    u.set_password("smsi123")
    db.session.add(u)
    db.session.flush()
    return u


def _seed_demo(rssi, contrib, auditor):
    def ctrl(ref):
        return Control.of().filter_by(ref=ref).first()

    # Rendre applicables/implémentées quelques mesures + affecter des responsables
    applied = {
        "5.1": ControlStatus.IMPLEMENTE, "5.15": ControlStatus.IMPLEMENTE,
        "5.17": ControlStatus.EN_COURS, "6.3": ControlStatus.IMPLEMENTE,
        "8.7": ControlStatus.IMPLEMENTE, "8.13": ControlStatus.IMPLEMENTE,
        "8.8": ControlStatus.EN_COURS, "8.16": ControlStatus.EN_COURS,
        "8.24": ControlStatus.IMPLEMENTE, "7.2": ControlStatus.EN_COURS,
    }
    for ref, st in applied.items():
        c = ctrl(ref)
        c.status = st
        c.owner_id = contrib.id
        c.justification = "Retenue au regard des risques identifiés et des exigences applicables."
        c.implementation = "Mise en œuvre documentée et exploitée."
    # Une exclusion motivée (exemple)
    c = ctrl("8.30")
    c.applicable = False
    c.status = ControlStatus.NON_APPLICABLE
    c.justification = "Aucun développement externalisé dans le périmètre du SMSI."
    db.session.commit()

    # Risques maillés aux mesures
    demo_risks = [
        ("Compromission de comptes à privilèges", "Systèmes d'administration",
         "Attaquant externe", "MFA absente sur certains accès admin", 4, 5,
         Treatment.REDUIRE, 2, 4, ["8.2", "8.5", "5.17"]),
        ("Perte de données par absence de sauvegarde testée", "Données métier",
         "Panne / rançongiciel", "Restauration non testée", 3, 5,
         Treatment.REDUIRE, 2, 3, ["8.13", "8.7"]),
        ("Fuite d'informations via prestataire cloud", "Données clients",
         "Prestataire", "Contrat sans clause sécurité", 3, 4,
         Treatment.PARTAGER, 2, 3, ["5.23", "5.20"]),
        ("Accès physique non autorisé au local serveurs", "Salle serveurs",
         "Intrusion", "Contrôle d'accès physique partiel", 2, 4,
         Treatment.REDUIRE, 1, 4, ["7.2", "7.1"]),
    ]
    for i, (title, asset, threat, vuln, l, imp, tr, rl, ri, refs) in enumerate(demo_risks, 1):
        r = Risk(ref=f"R-2026-{i:04d}", title=title, asset=asset, threat=threat,
                 vulnerability=vuln, likelihood=l, impact=imp, treatment=tr,
                 residual_likelihood=rl, residual_impact=ri,
                 status=RiskStatus.EN_TRAITEMENT, owner_id=rssi.id,
                 review_date=date.today() + timedelta(days=120))
        r.controls = [ctrl(x) for x in refs if ctrl(x)]
        db.session.add(r)
    db.session.commit()

    # Audit interne + constats + actions correctives
    aud = Audit(ref="AUD-2026-01", title="Audit interne annuel du SMSI",
                scope="Périmètre complet du SMSI - clauses 4 à 10 et Annexe A",
                planned_date=date.today() - timedelta(days=10),
                status=AuditStatus.TERMINE, lead_auditor_id=auditor.id,
                summary="Deux non-conformités mineures, plusieurs observations.")
    db.session.add(aud)
    db.session.flush()
    f1 = Finding(audit_id=aud.id, ref="C-01", type=FindingType.NC_MINEURE,
                 title="Revue des droits d'accès non tracée",
                 description="La revue périodique des accès n'est pas enregistrée.",
                 control_id=ctrl("5.18").id, clause="A.5.18")
    f2 = Finding(audit_id=aud.id, ref="C-02", type=FindingType.NC_MINEURE,
                 title="Tests de restauration non planifiés",
                 control_id=ctrl("8.13").id, clause="A.8.13")
    f3 = Finding(audit_id=aud.id, ref="C-03", type=FindingType.OBSERVATION,
                 title="Sensibilisation à renforcer sur le phishing",
                 control_id=ctrl("6.3").id)
    db.session.add_all([f1, f2, f3])
    db.session.flush()
    db.session.add_all([
        CorrectiveAction(finding_id=f1.id, description="Formaliser et tracer la revue trimestrielle des accès.",
                         owner_id=contrib.id, due_date=date.today() + timedelta(days=30),
                         status=ActionStatus.EN_COURS),
        CorrectiveAction(finding_id=f2.id, description="Planifier un test de restauration semestriel.",
                         owner_id=contrib.id, due_date=date.today() - timedelta(days=5),
                         status=ActionStatus.OUVERTE),
    ])
    db.session.commit()

    # Revue de direction
    rev = ManagementReview(
        ref="RD-2026-01", title="Revue de direction - 1er semestre 2026",
        review_date=date.today() - timedelta(days=3), status=ReviewStatus.TENUE,
        participants="Direction générale, RSSI, DSI",
        inputs="État des actions des revues précédentes ; évolution du contexte et des "
               "parties intéressées ; performance du SMSI (indicateurs, non-conformités, "
               "résultats d'audit) ; retour sur les risques et opportunités.",
        decisions="Renforcement du budget sensibilisation ; validation du plan de "
                  "traitement des risques ; maintien du périmètre de certification.")
    db.session.add(rev)
    db.session.flush()
    db.session.add(ReviewAction(review_id=rev.id,
                   description="Allouer un budget pour une campagne de phishing simulé.",
                   owner_id=rssi.id, due_date=date.today() + timedelta(days=60),
                   status=ActionStatus.OUVERTE))
    db.session.commit()

    # Documents du SMSI
    docs = [
        ("DOC-001", "Politique de sécurité de l'information", DocType.POLITIQUE, "2.0", DocStatus.APPROUVE, -60, 305),
        ("DOC-002", "Procédure de gestion des accès", DocType.PROCEDURE, "1.3", DocStatus.APPROUVE, -40, -5),
        ("DOC-003", "Procédure de sauvegarde et restauration", DocType.PROCEDURE, "1.0", DocStatus.EN_REVUE, None, 20),
        ("DOC-004", "Plan de traitement des risques", DocType.ENREGISTREMENT, "1.1", DocStatus.APPROUVE, -20, 160),
    ]
    for ref, title, typ, ver, st, appr, nxt in docs:
        db.session.add(Document(
            ref=ref, title=title, doc_type=typ, version=ver, status=st,
            owner_id=rssi.id,
            approved_at=(date.today() + timedelta(days=appr)) if appr is not None else None,
            next_review_at=(date.today() + timedelta(days=nxt)) if nxt is not None else None))
    db.session.commit()

    # Preuves maillées aux mesures
    evid = [
        ("PRV-0001", "Export de la configuration MFA", ["8.5", "8.2"]),
        ("PRV-0002", "Journal du dernier test de restauration", ["8.13"]),
        ("PRV-0003", "Attestation de campagne de sensibilisation", ["6.3"]),
        ("PRV-0004", "Registre des revues d'accès", ["5.18", "5.15"]),
    ]
    for ref, title, refs in evid:
        e = Evidence(ref=ref, title=title, collected_at=date.today() - timedelta(days=15),
                     owner_id=contrib.id, location="Coffre documentaire interne")
        e.controls = [Control.of().filter_by(ref=x).first() for x in refs]
        db.session.add(e)
    db.session.commit()

    # Inventaire des actifs
    from datetime import date as _date2
    assets = [
        ("Serveur de production applicatif", AssetCategory.MATERIEL, Classification.CONFIDENTIEL, "Datacenter A"),
        ("Base de données clients", AssetCategory.INFORMATION, Classification.SECRET, "Cloud UE"),
        ("Application de facturation", AssetCategory.LOGICIEL, Classification.CONFIDENTIEL, "SaaS"),
        ("Poste de travail RSSI", AssetCategory.MATERIEL, Classification.INTERNE, "Siège"),
    ]
    for i, (name, cat, cls, loc) in enumerate(assets, 1):
        db.session.add(Asset(ref=f"ACT-2026-{i:04d}", name=name, category=cat,
                             classification=cls, location=loc, status=AssetStatus.ACTIF,
                             owner_id=rssi.id))
    # Incidents
    db.session.add(Incident(ref="INC-2026-0001", title="Tentative de phishing ciblée",
                   description="Courriel frauduleux reçu par plusieurs collaborateurs.",
                   category=IncidentCategory.MALVEILLANCE, severity=IncidentSeverity.MAJEUR,
                   status=IncidentStatus.EN_COURS, detected_at=date.today() - timedelta(days=2),
                   reporter="Support informatique", assignee_id=rssi.id,
                   control_id=Control.of().filter_by(ref="5.26").first().id,
                   impact="Aucune donnée compromise à ce stade."))
    db.session.add(Incident(ref="INC-2026-0002", title="Indisponibilité du serveur de messagerie",
                   category=IncidentCategory.PANNE, severity=IncidentSeverity.MINEUR,
                   status=IncidentStatus.CLOTURE, detected_at=date.today() - timedelta(days=20),
                   assignee_id=contrib.id, resolution="Redémarrage et supervision renforcée.",
                   closed_at=datetime.utcnow() - timedelta(days=19)))
    # Sensibilisation
    db.session.add(AwarenessAction(ref="SENS-2026-0001", title="Formation annuelle sécurité de l'information",
                   atype=AwarenessType.FORMATION, status=AwarenessStatus.TERMINEE,
                   action_date=date.today() - timedelta(days=30), audience="Tout le personnel",
                   participants=48, completion_rate=92))
    db.session.add(AwarenessAction(ref="SENS-2026-0002", title="Campagne de phishing simulé Q3",
                   atype=AwarenessType.CAMPAGNE_PHISHING, status=AwarenessStatus.PLANIFIEE,
                   action_date=date.today() + timedelta(days=25), audience="Tout le personnel"))
    db.session.commit()
