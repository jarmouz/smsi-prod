#!/bin/sh
# Installation initiale du SMSI sur le serveur du client.
. "$(dirname "$0")/lib.sh"

[ "$(id -u)" = "0" ] || groups | grep -qw docker || fatal "Lancez ce script en root ou avec un utilisateur du groupe docker."

# 1. Images (hors ligne si le paquet les contient)
load_images
[ -f VERSION ] && VERSION=$(cat VERSION) || fatal "Fichier VERSION absent du paquet."
docker image inspect "smsi-web:$VERSION" >/dev/null 2>&1 || fatal "Image smsi-web:$VERSION introuvable."

# 2. Configuration et secrets
if [ ! -f .env ]; then
    info "Création de la configuration (.env)"
    cp .env.example .env
    chmod 600 .env
    printf "Nom d'accès de l'application (ex. smsi.entreprise.local) : "
    read -r DOMAIN
    [ -n "$DOMAIN" ] || fatal "Nom d'accès obligatoire."
    env_set SMSI_DOMAIN "$DOMAIN"
    env_set APP_BASE_URL "https://$DOMAIN"
    env_set SECRET_KEY "$(gen_secret)"
    env_set POSTGRES_PASSWORD "$(gen_secret)"
else
    info "Configuration existante conservée (.env)"
fi
env_set SMSI_VERSION "$VERSION"
DOMAIN=$(env_get SMSI_DOMAIN)

# 3. Certificat HTTPS
if [ ! -f certs/smsi.crt ] || [ ! -f certs/smsi.key ]; then
    warn "Aucun certificat dans certs/ (smsi.crt + smsi.key)."
    echo "  Recommandé : un certificat émis par l'autorité interne du client pour $DOMAIN."
    printf "Générer un certificat auto-signé provisoire ? [o/N] "
    read -r ans
    case "$ans" in
        o|O|y|Y)
            command -v openssl >/dev/null 2>&1 || fatal "openssl est requis pour générer le certificat."
            openssl req -x509 -newkey rsa:3072 -sha256 -days 825 -nodes \
                -keyout certs/smsi.key -out certs/smsi.crt \
                -subj "/CN=$DOMAIN" -addext "subjectAltName=DNS:$DOMAIN" 2>/dev/null
            chmod 600 certs/smsi.key
            warn "Certificat auto-signé créé : les navigateurs afficheront un avertissement."
            ;;
        *) fatal "Déposez certs/smsi.crt et certs/smsi.key puis relancez install.sh." ;;
    esac
fi
# Caddy (utilisateur non root) doit pouvoir lire la clé montée en lecture seule
chmod 644 certs/smsi.crt; chmod 640 certs/smsi.key 2>/dev/null || true

# 4. Démarrage
info "Démarrage des services"
compose up -d
wait_healthy

# 5. Initialisation de la base (première installation uniquement)
if db_initialized; then
    info "Base déjà initialisée : migrations appliquées au démarrage."
else
    info "Initialisation de la base : organisation et compte RSSI"
    # Le mot de passe RSSI est saisi de façon interactive : un terminal est indispensable
    [ -t 0 ] || fatal "Initialisation interactive : relancez install.sh depuis un terminal (pas via un pipe)."
    ORG="${SMSI_ORG_NAME:-}"
    if [ -z "$ORG" ]; then
        printf "Nom de l'organisation (ex. raison sociale du client) : "
        read -r ORG
    fi
    [ -n "$ORG" ] || fatal "Nom de l'organisation obligatoire."
    ADMIN="${SMSI_ADMIN_EMAIL:-}"
    if [ -z "$ADMIN" ]; then
        printf "E-mail du compte RSSI : "
        read -r ADMIN
    fi
    [ -n "$ADMIN" ] || fatal "E-mail du compte RSSI obligatoire."
    compose exec web flask init-platform --org-name "$ORG" --admin-email "$ADMIN" \
        || fatal "Échec de l'initialisation de la base. Corrigez puis relancez install.sh."
    db_initialized || fatal "La base n'est toujours pas initialisée. Relancez install.sh."
fi

info "Installation terminée : https://$DOMAIN"
echo "  Pensez à planifier les sauvegardes, par exemple dans la crontab de root :"
echo "  30 2 * * * $(pwd)/backup.sh >> $(pwd)/backups/backup.log 2>&1"
