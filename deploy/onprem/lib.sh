# Fonctions communes aux scripts d'exploitation (sourcé, ne pas exécuter).
set -eu
cd "$(dirname "$0")"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
fatal() { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fatal "Docker n'est pas installé."
docker compose version >/dev/null 2>&1 || fatal "Le plugin « docker compose » est requis."

compose() { docker compose "$@"; }

env_get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }

env_set() {  # env_set CLE valeur : remplace ou ajoute dans .env
    if grep -qE "^$1=" .env; then
        tmp=$(mktemp); awk -v k="$1" -v v="$2" 'BEGIN{FS=OFS="="} $1==k{print k"="v; next} {print}' .env > "$tmp"
        cat "$tmp" > .env; rm -f "$tmp"
    else
        printf '%s=%s\n' "$1" "$2" >> .env
    fi
}

gen_secret() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }

load_images() {  # charge les images livrées hors ligne (images/*.tar)
    if ls images/*.tar >/dev/null 2>&1; then
        for f in images/*.tar; do info "Chargement de l'image $(basename "$f")"; docker load -q -i "$f"; done
    fi
}

wait_healthy() {
    info "Attente du démarrage de l'application..."
    i=0
    until compose exec -T web curl -fsS http://127.0.0.1:5000/healthz >/dev/null 2>&1; do
        i=$((i + 1)); [ "$i" -ge 60 ] && fatal "L'application ne répond pas. Voir : docker compose logs web"
        sleep 2
    done
}

db_initialized() {
    [ "$(compose exec -T db psql -U smsi -d smsi -tAc \
        "select count(*) from information_schema.tables where table_name='users'" 2>/dev/null | tr -d '[:space:]')" = "1" ]
}
