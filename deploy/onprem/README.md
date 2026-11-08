# Integra — Guide d'installation sur site

Ce paquet installe **Integra** (Integrated Management System Platform) sur un serveur du client, **sans accès
internet** : les images Docker sont fournies dans `images/`.

## 1. Avant l'intervention : à obtenir du client

| Élément | Détail |
|---|---|
| VM | Linux 64 bits (Ubuntu 24.04+, Debian 12, RHEL 9…), 2 vCPU, 4 Go de RAM, 40 Go de disque |
| Docker | Docker Engine 24+ avec le plugin `docker compose`, et `openssl`. **Le paquet ne contient pas Docker** : si la VM n'a pas accès à internet, le client l'installe à l'avance |
| Nom d'accès | Un nom DNS interne (ex. `smsi.entreprise.local`) pointant vers l'IP de la VM |
| Certificat | Idéalement émis par l'autorité interne du client pour ce nom (`smsi.crt` + `smsi.key`, PEM). À défaut, certificat auto-signé (avertissement du navigateur) |
| Réseau | Ports 80 et 443 ouverts depuis les postes des utilisateurs vers la VM |
| Accès | Un compte avec `sudo` sur la VM |
| Informations | Nom de l'organisation, e-mail du RSSI (le RSSI saisit lui-même son mot de passe) |

## 2. Installation (sur place)

**Copier et vérifier le paquet** (clé USB ou `scp`) :

```bash
sha256sum -c smsi-<version>.tar.gz.sha256
sudo tar xzf smsi-<version>.tar.gz -C /opt && sudo mv /opt/smsi-<version> /opt/smsi
```

**Déposer le certificat du client** (recommandé) :

```bash
sudo cp smsi.crt smsi.key /opt/smsi/certs/
#   smsi.crt : certificat + chaîne intermédiaire (PEM) ; smsi.key : clé privée (PEM)
```

**Lancer l'installation**, depuis un terminal (saisies interactives) :

```bash
cd /opt/smsi && sudo ./install.sh
```

Questions posées : le **nom d'accès** (ex. `smsi.entreprise.local`), le **nom de
l'organisation**, puis l'**e-mail et le mot de passe du RSSI** (12 caractères
minimum, 3 types de caractères). Le script :

1. charge les images Docker livrées (aucun accès internet requis) ;
2. crée `.env` et **génère des secrets uniques** (clé de l'application, mot de
   passe de la base) ;
3. propose un certificat auto-signé provisoire si aucun certificat n'est fourni ;
4. démarre les services (base, application, reverse proxy HTTPS) ;
5. crée **l'organisation du client** (catalogue des 93 mesures de l'Annexe A)
   et son **compte RSSI**, super-administrateur de la plateforme.

> `.env` contient les secrets de l'installation : il est créé en `600`, ne le
> transmettez pas et incluez-le dans vos sauvegardes protégées.

**Premier compte** : c'est le RSSI saisi pendant l'installation (e-mail et mot
de passe tapés au clavier, rappelés en fin de script). Le mot de passe n'est
conservé nulle part en clair : notez-le, ou faites-le saisir par le RSSI.

## 3. Vérification depuis un poste utilisateur

- `https://<nom d'accès>` s'ouvre (sans avertissement si le certificat du client est utilisé) ;
- le RSSI se connecte et voit le tableau de bord de son organisation ;
- `https://<nom d'accès>/healthz` répond `{"status":"ok"}`.

## 4. Planifier les sauvegardes

Dans la crontab de root (`sudo crontab -e`) :

```
30 2 * * * /opt/smsi/backup.sh >> /opt/smsi/backups/backup.log 2>&1
```

Le client copie régulièrement `/opt/smsi/backups/` **hors de la VM**, dans un
emplacement protégé (les sauvegardes contiennent les secrets). Détails dans la
section « Sauvegardes » ci-dessous.

## 5. Options selon le client

- **Nextcloud / OnlyOffice internes** : voir la section dédiée ci-dessous.
- **Rappels par e-mail** : le RSSI configure le SMTP dans l'application
  (Administration › Paramètres), puis planifiez chaque matin (crontab de root) :
  ```
  0 6 * * * cd /opt/smsi && docker compose exec -T web flask send-reminders >> backups/reminders.log 2>&1
  ```
- **Connecteurs d'inventaire** (GLPI, Intune, Entra ID, Azure, AWS) : le RSSI les
  configure dans Administration › Connecteurs. Pour un GLPI du réseau local, ajoutez
  `CONNECTORS_ALLOW_PRIVATE=1` dans `.env`. Pour la synchronisation automatique :
  ```
  15 3 * * * cd /opt/smsi && docker compose exec -T web flask sync-connectors >> backups/connectors.log 2>&1
  ```
- **Autres normes** : le RSSI peut activer l'**ISO/IEC 27701** (vie privée :
  registre des traitements, demandes des personnes, annexes A et B) et
  l'**ISO/IEC 42001** (intelligence artificielle : inventaire des systèmes d'IA,
  études d'impact, annexe A) dans Administration › Référentiels. Chaque norme
  ajoute sa déclaration d'applicabilité et ses écrans ; rien ne change tant
  qu'elle n'est pas activée. Également disponibles : l'**ISO 22301**
  (continuité : plans de continuité et de reprise) et l'**ISO/IEC 20000-1**
  (services informatiques : catalogue et niveaux de service, problèmes, mises
  en production) et l'**ISO 9001** (qualité : cartographie des processus,
  satisfaction client, réclamations, risques et opportunités, produits non
  conformes), évaluées exigence par exigence.
- **Assistant IA** : facultatif, il n'est utilisable que si la VM peut joindre
  `api.anthropic.com` ; il reste désactivé tant que la clé d'API n'est pas
  renseignée (Plateforme) puis activée par le RSSI.

## 6. Avant de quitter le site

- [ ] Sauvegarde manuelle (`sudo ./backup.sh`) présente dans `backups/`
- [ ] Tâche de sauvegarde planifiée (et rappels si SMTP configuré)
- [ ] Ce guide remis au client (mise à jour, restauration, exploitation)
- [ ] Version installée (`cat VERSION`) et date notées dans la fiche client

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

> **Passage de 2.x à 3.0** : la base est convertie au modèle multi-référentiels
> (les mesures existantes sont rattachées à l'ISO/IEC 27001:2022, activée pour
> chaque organisation). Rien ne change pour les utilisateurs ; le RSSI trouve une
> nouvelle page **Administration › Référentiels** (périmètre et certification
> par norme).

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

## Certificat public Let's Encrypt (serveur exposé sur internet)

Le kit n'obtient pas de certificat lui-même : il utilise `certs/smsi.crt` et
`certs/smsi.key`. Sur un serveur public, obtenez-le **avant** `install.sh`
(le port 80 est encore libre) :

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone -d <nom d'accès>
sudo cp -L /etc/letsencrypt/live/<nom d'accès>/fullchain.pem /opt/smsi/certs/smsi.crt
sudo cp -L /etc/letsencrypt/live/<nom d'accès>/privkey.pem   /opt/smsi/certs/smsi.key
```

Le renouvellement automatique de certbot a besoin du port 80, occupé par le
proxy du kit : ajoutez ces deux scripts (rendus exécutables avec `chmod +x`),
qui arrêtent le proxy, puis recopient le certificat et le relancent :

`/etc/letsencrypt/renewal-hooks/pre/smsi.sh`
```sh
#!/bin/sh
cd /opt/smsi && docker compose stop proxy
```

`/etc/letsencrypt/renewal-hooks/post/smsi.sh`
```sh
#!/bin/sh
D=$(ls -d /etc/letsencrypt/live/*/ | head -1)
cp -L "$D/fullchain.pem" /opt/smsi/certs/smsi.crt
cp -L "$D/privkey.pem" /opt/smsi/certs/smsi.key
chmod 644 /opt/smsi/certs/smsi.crt; chmod 640 /opt/smsi/certs/smsi.key
cd /opt/smsi && docker compose start proxy
```

Vérification : `sudo certbot renew --dry-run` (quelques secondes de coupure).

## Exploitation courante

| Action | Commande |
|---|---|
| État des services | `docker compose ps` |
| Journaux | `docker compose logs -f web` |
| Redémarrer | `docker compose restart` |
| Arrêter | `docker compose down` (les données sont conservées) |
| Contrôle de santé | `curl -k https://<nom d'accès>/healthz` |
| Liste des comptes | `docker compose exec db psql -U smsi -d smsi -c "select email, role, is_superadmin, is_active from users"` |
| Accès perdu (mot de passe oublié, compte verrouillé ou téléphone perdu) | `docker compose exec web flask reset-password <e-mail>` |

### Accès perdu

Un autre administrateur peut utiliser **Administration › Utilisateurs ›
Réinitialiser l'accès**. Si c'est le seul RSSI qui a perdu son accès, depuis la VM :

```bash
cd /opt/smsi && sudo docker compose exec web flask reset-password rssi@entreprise.tn
```

La commande affiche un **mot de passe temporaire** (à changer à la connexion
suivante), déverrouille et réactive le compte, et supprime la double
authentification (`--keep-mfa` pour la conserver). L'opération est inscrite au
journal d'activité.

> ⚠️ Ne lancez **jamais** `flask init-db` : c'est un outil de développement qui
> efface toute la base. L'installation utilise `flask init-platform`, qui refuse
> de s'exécuter si des utilisateurs existent déjà.
