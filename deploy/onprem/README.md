# SMSI — Guide d'installation sur site

Ce paquet installe l'application SMSI sur un serveur du client, **sans accès
internet** : les images Docker sont fournies dans `images/`.

## Prérequis

| Élément | Minimum |
|---|---|
| Système | Linux 64 bits (Debian 12, Ubuntu 22.04+, RHEL 9…) |
| Ressources | 2 vCPU, 4 Go de RAM, 20 Go de disque (+ volume des pièces jointes) |
| Logiciels | Docker Engine 24+ avec le plugin `docker compose`, `openssl` |
| Réseau | Un nom DNS interne (ex. `smsi.entreprise.local`) pointant vers le serveur ; ports 80 et 443 ouverts aux utilisateurs |
| Certificat | Idéalement un certificat émis par l'autorité interne du client pour ce nom |

## Installation

```bash
tar xzf smsi-<version>.tar.gz
cd smsi-<version>
# (recommandé) déposer le certificat du client :
#   certs/smsi.crt  (certificat + chaîne intermédiaire, format PEM)
#   certs/smsi.key  (clé privée, format PEM)
sudo ./install.sh
```

Le script :
1. charge les images Docker livrées ;
2. crée `.env` et **génère des secrets uniques** (clé de l'application, mot de
   passe de la base) ;
3. propose un certificat auto-signé provisoire si aucun certificat n'est fourni ;
4. démarre les services (base, application, reverse proxy HTTPS) ;
5. initialise la base : crée **l'organisation du client** (avec le catalogue
   des 93 mesures de l'Annexe A) et son **compte RSSI**, super-administrateur de
   la plateforme (mot de passe demandé : 12 caractères minimum, 3 types de
   caractères).

L'application est ensuite accessible sur `https://<nom d'accès>`.

> `.env` contient les secrets de l'installation : il est créé en `600`, ne le
> transmettez pas et incluez-le dans vos sauvegardes protégées.

## Sauvegardes

```bash
./backup.sh
```

Crée `backups/AAAAMMJJ-HHMMSS/` : base (`smsi.dump`), pièces jointes,
configuration, empreintes SHA-256. Rétention : `BACKUP_KEEP_DAYS` (30 jours).

À planifier chaque nuit (crontab de root) :

```
30 2 * * * /opt/smsi/backup.sh >> /opt/smsi/backups/backup.log 2>&1
```

**Copiez le dossier `backups/` hors du serveur** (règle 3-2-1) et testez une
restauration au moins une fois par an (ISO 27001, mesure 8.13).

## Restauration

```bash
./restore.sh backups/AAAAMMJJ-HHMMSS
```

Vérifie l'intégrité, demande une confirmation explicite, remplace la base et
les pièces jointes, puis redémarre l'application.

## Mise à jour

1. Décompressez le nouveau paquet **par-dessus** le dossier d'installation
   (`.env`, `certs/`, `backups/` sont conservés) :
   ```bash
   tar xzf smsi-<nouvelle-version>.tar.gz --strip-components=1 -C /opt/smsi
   ```
2. Lancez :
   ```bash
   cd /opt/smsi && sudo ./update.sh
   ```

Une sauvegarde est faite automatiquement avant la mise à jour ; les évolutions
de la base sont appliquées au démarrage, sans perte de données.

## Nextcloud / OnlyOffice (facultatif)

Renseignez dans `.env` :

```
STORAGE_BACKEND=webdav
NEXTCLOUD_URL=https://nextcloud.entreprise.local
NEXTCLOUD_USER=smsi-svc
NEXTCLOUD_PASSWORD=<mot de passe d'application Nextcloud>
```

Si Nextcloud utilise un certificat de l'**autorité interne** du client, déposez
le certificat racine (PEM) dans `ca/ca-entreprise.pem` et ajoutez :

```
REQUESTS_CA_BUNDLE=/ca/ca-entreprise.pem
```

Puis `docker compose up -d` et testez dans **Administration → Paramètres →
Tester Nextcloud**.

## Exploitation courante

| Action | Commande |
|---|---|
| État des services | `docker compose ps` |
| Journaux | `docker compose logs -f web` |
| Redémarrer | `docker compose restart` |
| Arrêter | `docker compose down` (les données sont conservées) |
| Contrôle de santé | `curl -k https://<nom d'accès>/healthz` |

> ⚠️ Ne lancez **jamais** `flask init-db` : c'est un outil de développement qui
> efface toute la base. L'installation utilise `flask init-platform`, qui refuse
> de s'exécuter si des utilisateurs existent déjà.
