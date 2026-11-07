#!/bin/sh
# Restauration d'une sauvegarde créée par backup.sh.
# Usage : ./restore.sh backups/AAAAMMJJ-HHMMSS
. "$(dirname "$0")/lib.sh"

SRC=${1:-}
[ -n "$SRC" ] && [ -f "$SRC/smsi.dump" ] || fatal "Usage : ./restore.sh backups/AAAAMMJJ-HHMMSS"
if [ -f "$SRC/SHA256SUMS" ]; then
    ( cd "$SRC" && sha256sum -c --quiet SHA256SUMS ) || fatal "Sauvegarde corrompue (empreintes SHA-256 différentes)."
fi

warn "La base et les pièces jointes ACTUELLES vont être remplacées par $SRC."
printf "Tapez RESTAURER pour confirmer : "
read -r ans
[ "$ans" = "RESTAURER" ] || fatal "Restauration annulée."

info "Arrêt de l'application"
compose stop web proxy

info "Restauration de la base"
compose up -d db
until compose exec -T db pg_isready -U smsi -d smsi -q; do sleep 1; done
compose exec -T db psql -U smsi -d postgres -qc "DROP DATABASE IF EXISTS smsi WITH (FORCE)"
compose exec -T db psql -U smsi -d postgres -qc "CREATE DATABASE smsi OWNER smsi"
compose exec -T db pg_restore -U smsi -d smsi --no-owner < "$SRC/smsi.dump"

if [ -f "$SRC/uploads.tar.gz" ]; then
    info "Restauration des pièces jointes"
    compose run --rm -T --no-deps --entrypoint sh web \
        -c 'rm -rf /data/uploads && tar xzf - -C /data && chown -R app:app /data/uploads' < "$SRC/uploads.tar.gz"
fi

info "Redémarrage (les migrations sont appliquées automatiquement)"
compose up -d
wait_healthy
info "Restauration terminée."
