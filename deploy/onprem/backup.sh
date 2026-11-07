#!/bin/sh
# Sauvegarde complète : base PostgreSQL + pièces jointes + configuration.
# Usage : ./backup.sh            (à planifier en cron)
. "$(dirname "$0")/lib.sh"

STAMP=$(date +%Y%m%d-%H%M%S)
DEST="backups/$STAMP"
KEEP=$(env_get BACKUP_KEEP_DAYS); KEEP=${KEEP:-30}
umask 077
mkdir -p "$DEST"

info "Sauvegarde de la base"
compose exec -T db pg_dump -U smsi -Fc smsi > "$DEST/smsi.dump"

info "Sauvegarde des pièces jointes"
compose exec -T web tar czf - -C /data uploads > "$DEST/uploads.tar.gz"

# La configuration contient les secrets : la sauvegarde doit être protégée
cp .env "$DEST/env.backup"
cp VERSION "$DEST/VERSION" 2>/dev/null || true

[ -s "$DEST/smsi.dump" ] || fatal "Sauvegarde de la base vide : vérifiez « docker compose ps »."
( cd "$DEST" && sha256sum smsi.dump uploads.tar.gz > SHA256SUMS )

info "Sauvegarde terminée : $DEST ($(du -sh "$DEST" | cut -f1))"

# Rétention
find backups -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP" -exec rm -rf {} + 2>/dev/null || true
warn "Copiez régulièrement le dossier backups/ hors de ce serveur (règle 3-2-1)."
