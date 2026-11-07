# SMSI — Système de management de la sécurité (ISO/IEC 27001)

Application de pilotage d'un **SMSI** pour une entreprise. Six modules reliés
entre eux, pensés pour l'audit de certification : la valeur n'est pas dans six
listes séparées mais dans le **maillage** entre elles.

## Ce dépôt

Dépôt **principal** de l'application (il remplace `jarmouz/SMSI`, archivé).

| Chemin | Rôle |
|---|---|
| `app/` | code de l'application (multi-organisation) |
| `docker-compose.yml` | **production** `smsi.kaizen-intelligence.tn` (nginx → `127.0.0.1:5001`) |
| `deploy/onprem/` | kit d'installation **chez un client** (voir son README) |
| `scripts/build-release.sh` | construit le paquet de livraison `dist/smsi-<VERSION>.tar.gz` |
| `VERSION` | version livrée par le kit |

Mise en production (serveur Kaizen, dossier `/opt/smsi-prod`) :

```bash
docker compose build web && docker compose up -d --no-deps web   # jamais la base
git commit -am "…" && git push
```

Au démarrage, le conteneur met à jour le schéma (`flask upgrade-db`, sans perte).

Depuis la 3.0, l'application est **multi-référentiels** : les normes et leurs
catalogues sont décrits dans `app/services/frameworks.py` (`CATALOGUES`), chaque
organisation active les siennes (Administration › Référentiels) et les éléments
communs (audits, revues, documents, objectifs, non-conformités) peuvent être
rattachés à une ou plusieurs normes. Les écrans historiques restent limités à
l'ISO 27001 (`Control.of()`).
Une base neuve s'initialise avec `flask init-platform` (organisation + RSSI) ;
`flask init-db` est réservé au développement (il efface tout).

## Modules

1. **Déclaration d'applicabilité (DdA / SoA)** — catalogue complet de l'**Annexe A
   ISO/IEC 27001:2022 (93 mesures, 4 thèmes)** pré-chargé. Pour chaque mesure :
   applicabilité, justification d'inclusion/exclusion, statut de mise en œuvre,
   responsable, preuves et risques rattachés.
2. **Gestion des risques** — registre type ISO 27005 : actif, menace,
   vulnérabilité, cotation **vraisemblance × impact** (inhérent puis résiduel),
   option de traitement, et **rattachement aux mesures de l'Annexe A** qui traitent
   le risque. Matrice 5×5.
3. **Audit interne** (clause 9.2) — audits, constats (NC majeure/mineure,
   observation, amélioration) référençant une mesure/clause, et **actions
   correctives** suivies (clause 10.1).
4. **Revue de direction** (clause 9.3) — données d'entrée (9.3.2) et
   décisions/sorties (9.3.3) structurées, décisions/actions suivies, avec une
   **synthèse SMSI automatique** pour préparer la revue.
5. **Gestion documentaire** (clause 7.5) — politiques, procédures et
   enregistrements versionnés, cycle d'approbation, alertes de **revue à échéance**.
6. **Gestion des preuves** — éléments d'auditabilité **rattachés aux mesures**
   qu'ils attestent : ce qu'un auditeur demande pour vérifier la mise en œuvre.

Le **tableau de bord** agrège le tout : taux de mise en œuvre de la DdA, matrice
des risques résiduels, couverture par thème, non-conformités ouvertes, actions en
retard, documents à revoir, prochaine revue de direction.

## Le maillage (ce qui fait la différence)

- Risque → *traité par* → Mesures (Annexe A)
- Mesure → *déclarée dans* la DdA, *prouvée par* → Preuves
- Constat d'audit → *référence* une mesure/clause → *génère* → Actions correctives
- Revue de direction → *consomme* tout ce qui précède comme données d'entrée

## Rôles

| Rôle | Droits |
|------|--------|
| **RSSI** | Accès complet, administration comprise |
| **Contributeur** | Création/édition des objets opérationnels |
| **Auditeur** | Gestion des audits et constats |
| **Lecteur** | Lecture seule (ex. direction) |

## Démarrage (Docker)

```bash
cp .env.example .env          # renseignez SECRET_KEY
docker compose up -d --build
docker compose exec web flask init-db --demo      # avec jeu de démonstration
# ou, pour partir sur une base propre (catalogue Annexe A seul, sans démo) :
docker compose exec web flask init-db --no-demo
```

L'application écoute sur `http://localhost:5000`. Placez un reverse-proxy
(Caddy, Nginx, Traefik) devant pour le HTTPS.

### Comptes de démonstration — mot de passe `smsi123`

| E-mail | Rôle |
|--------|------|
| rssi@smsi.local | RSSI (accès complet) |
| contrib@smsi.local | Contributeur |
| auditeur@smsi.local | Auditeur interne |
| lecteur@smsi.local | Lecteur |

> ⚠️ En production : connectez-vous en RSSI, changez les mots de passe,
> configurez le SMTP et l'URL publique dans **Administration → Paramètres**,
> puis videz la démo via **Administration → Maintenance**.

## Mise en route « à blanc »

1. `flask init-db --no-demo` — la base ne contient alors que le catalogue des
   93 mesures et les comptes.
2. Parcourez la **DdA** : marquez les mesures retenues/exclues (avec
   justification) et leur statut.
3. Alimentez le **registre des risques** et rattachez les mesures de traitement.
4. Planifiez un **audit**, saisissez les constats et les actions correctives.
5. Référencez vos **documents** et **preuves**.
6. Préparez la **revue de direction** à partir de la synthèse automatique.

## Configuration SMTP

Renseignée dans l'interface (**Administration → Paramètres**) : serveur, port,
identifiants, expéditeur, STARTTLS/SSL. Un bouton de **test d'envoi** permet de
valider la configuration.

## Pile technique

Flask 3 · SQLAlchemy 2 · PostgreSQL 16 · Flask-Login · Gunicorn · Docker.
Architecture modulaire (application factory + blueprints), design system commun.

## Périmètre & limites (v0)

Base fonctionnelle destinée à être enrichie itérativement. Les intitulés des
mesures de l'Annexe A sont fournis à titre de **référence** ; le texte normatif
complet reste dans la norme ISO/IEC 27001:2022, dont la possession est requise
pour l'exploitation d'un SMSI certifié.
