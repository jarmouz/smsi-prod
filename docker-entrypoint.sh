#!/bin/sh
# Point d'entrée du conteneur web :
#  1. prépare le dossier des pièces jointes (volume) pour l'utilisateur « app » ;
#  2. attend la base, met le schéma à jour si elle est déjà initialisée ;
#  3. lance la commande demandée SANS droits root.
set -e

UPLOAD_DIR="${UPLOAD_DIR:-/data/uploads}"
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$UPLOAD_DIR"
    chown -R app:app "$UPLOAD_DIR"
    RUN_AS="setpriv --reuid=app --regid=app --init-groups"
else
    RUN_AS=""
fi

if [ "$1" = "gunicorn" ] && [ "${AUTO_MIGRATE:-1}" = "1" ]; then
    echo "Attente de la base de données..."
    i=0
    until $RUN_AS python -c "
from app import create_app
from app.extensions import db
from sqlalchemy import text
with create_app().app_context():
    db.session.execute(text('SELECT 1'))
" >/dev/null 2>&1; do
        i=$((i + 1))
        if [ "$i" -ge 30 ]; then echo "Base injoignable après 60 s." >&2; exit 1; fi
        sleep 2
    done
    # Base déjà initialisée : mise à jour du schéma (idempotente, sans perte).
    # Base vide : rien ici, l'installation lance « flask init-platform ».
    if $RUN_AS python -c "
from app import create_app
from app.extensions import db
from sqlalchemy import inspect
with create_app().app_context():
    raise SystemExit(0 if inspect(db.engine).has_table('users') else 1)
" >/dev/null 2>&1; then
        $RUN_AS flask upgrade-db || { echo "Échec de la mise à jour du schéma." >&2; exit 1; }
    else
        echo "Base vide : lancez « flask init-platform » (install.sh le fait)."
    fi
fi

exec $RUN_AS "$@"
