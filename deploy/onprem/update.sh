#!/bin/sh
# Mise à jour vers la version livrée dans ce dossier (images/ + VERSION).
# Une sauvegarde est faite AVANT la mise à jour.
. "$(dirname "$0")/lib.sh"

[ -f .env ] || fatal "Aucune installation trouvée ici (.env absent). Utilisez install.sh."
NEW=$(cat VERSION)
OLD=$(env_get SMSI_VERSION)

load_images
docker image inspect "smsi-web:$NEW" >/dev/null 2>&1 || fatal "Image smsi-web:$NEW introuvable."

info "Mise à jour $OLD -> $NEW"
info "Sauvegarde préalable"
./backup.sh

env_set SMSI_VERSION "$NEW"
compose up -d
wait_healthy
info "Mise à jour terminée (version $NEW). En cas de problème : ./restore.sh <dernière sauvegarde>"
