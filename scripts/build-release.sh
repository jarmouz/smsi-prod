#!/bin/sh
# Construit le paquet de livraison sur site : dist/smsi-<version>.tar.gz
# Contenu : kit deploy/onprem + images Docker (installation sans internet).
set -eu
cd "$(dirname "$0")/.."

VERSION=$(cat VERSION)
NAME="smsi-$VERSION"
OUT="dist/$NAME"
PG_IMAGE=postgres:16-alpine
CADDY_IMAGE=caddy:2.8.4-alpine

git diff --quiet HEAD -- || { echo "Modifications non commitées : commitez avant de livrer." >&2; exit 1; }

echo "==> Construction de smsi-web:$VERSION"
docker build -t "smsi-web:$VERSION" .

echo "==> Récupération des images tierces"
docker pull -q "$PG_IMAGE"
docker pull -q "$CADDY_IMAGE"

rm -rf "$OUT" && mkdir -p "$OUT/images"
cp -r deploy/onprem/. "$OUT/"
rm -f "$OUT/ca/.gitkeep" "$OUT/certs/.gitkeep"
echo "$VERSION" > "$OUT/VERSION"

echo "==> Export des images"
docker save "smsi-web:$VERSION" -o "$OUT/images/smsi-web.tar"
docker save "$PG_IMAGE" -o "$OUT/images/postgres.tar"
docker save "$CADDY_IMAGE" -o "$OUT/images/caddy.tar"

( cd dist && tar czf "$NAME.tar.gz" "$NAME" && sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256" )
rm -rf "$OUT"
echo "==> Paquet prêt : dist/$NAME.tar.gz ($(du -h "dist/$NAME.tar.gz" | cut -f1))"
echo "    Commit : $(git rev-parse --short HEAD)"
