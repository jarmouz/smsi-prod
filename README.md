# Integra — Integrated Management System Platform

Plateforme de pilotage de **systèmes de management** ISO, éditée par Kaizen
Intelligence : sécurité de l'information (ISO/IEC 27001, socle historique de
l'application), vie privée (ISO/IEC 27701), intelligence artificielle
(ISO/IEC 42001), d'autres normes à venir. Les modules sont reliés entre eux,
pensés pour l'audit de certification : la valeur n'est pas dans des listes
séparées mais dans le **maillage** entre elles.

> Noms techniques conservés pour la compatibilité des installations existantes :
> image Docker `smsi-web`, paquet `smsi-<version>.tar.gz`, dossier `/opt/smsi`,
> base `smsi`.

## Ce dépôt

Dépôt **principal** de l'application (il remplace `jarmouz/SMSI`, archivé).

| Chemin | Rôle |
|---|---|
| `app/` | code de l'application (multi-organisation) |
| `docker-compose.yml` | **production** `smsi.kaizen-intelligence.tn` (nginx → `127.0.0.1:5001`) |
| `deploy/onprem/` | kit d'installation **chez un client** (voir son README) |
| `scripts/build-release.sh` | construit le paquet de livraison `dist/smsi-<VERSION>.tar.gz` |
| `VERSION` | version livrée par le kit |

### Organisation du travail

| Branche | Rôle | Où elle tourne |
|---|---|---|
| `main` | reflet exact de la **production** | `smsi.kaizen-intelligence.tn` (serveur Kaizen, `/opt/smsi-prod`) |
| `develop` | versions validées en **recette**, pas encore en production | VPS de démonstration `ims.kaizen-intelligence.tn` |
| `<sujet>` (ex. `phase2-22301-20000`) | travail en cours, parti de `develop`, fusionné dans `develop` une fois testé | copie locale de la base de production |
| `hotfix-<sujet>` | correctif urgent de production, parti de `main`, puis reporté dans `develop` | production |
| `version-base-iso27001` | version de base mono-norme, conservée telle quelle | - |

Cycle d'une version : développement sur une branche de sujet (dossier de
travail `/opt/smsi-dev`) → tests sur une copie de la base de production →
fusion dans `develop`, tag `vX.Y.Z`, paquet `scripts/build-release.sh` →
installation sur le VPS avec `update.sh` → validation par Kaizen. La
production n'est mise à jour que sur décision explicite : fusion de `develop`
dans `main`, migration répétée sur une copie de la base, sauvegarde, image
précédente conservée, déploiement ci-dessous.

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

Normes disponibles (3.2) :

| Norme | Type | Module propre |
|---|---|---|
| ISO/IEC 27001:2022 (socle) | 93 mesures (Annexe A) + DdA | toute l'application historique |
| ISO/IEC 27701:2019 | 49 mesures (Annexes A et B) | Vie privée : registre des traitements, demandes des personnes |
| ISO/IEC 42001:2023 | 38 mesures (Annexe A) | Intelligence artificielle : systèmes d'IA, études d'impact |
| ISO 22301:2019 | 46 exigences (chapitres 4 à 10) | Plans de continuité (en plus de la BIA et des exercices) |
| ISO/IEC 20000-1:2018 | 45 exigences (chapitres 4 à 10) | Services IT : catalogue et niveaux de service, mesures mensuelles, problèmes, mises en production |
| ISO 9001:2015 | 63 exigences (chapitres 4 à 10) | Qualité : cartographie des processus, satisfaction client, réclamations ; risques qualité et opportunités, produits non conformes (dans les registres communs) |

Catalogues et correspondances (96) : `app/services/catalogue_data.py`.

### Socle commun SMI (3.4) : pas de double évaluation

Les chapitres 4 à 10 des normes ISO de systèmes de management suivent la même
**structure harmonisée** (annexe SL) : contexte, parties intéressées, politique,
rôles, risques et opportunités, objectifs, ressources, compétences,
sensibilisation, communication, informations documentées, audit interne, revue
de direction, non-conformités, amélioration. Ces 26 exigences communes forment le
**socle commun** (onglet « Socle commun SMI » de la DdA), présent pour chaque
organisation et évalué **une seule fois**.

Chaque exigence de l'ISO 9001, de l'ISO 22301 et de l'ISO/IEC 20000-1 est rattachée
au socle (`COMMON` dans `catalogue_data.py`) :

| Relation | Sens | Dans l'application |
|---|---|---|
| commune | texte de la structure harmonisée, couvert par le socle | **héritée** : statut, applicabilité et responsable recopiés du socle, preuves du socle visibles ; seule une précision propre à la norme se saisit |
| complément | le socle couvre la partie commune, la norme ajoute des exigences | évaluée dans la norme, le socle sert de base |
| (aucune) | exigence propre à la norme (chapitre 8 métier, orientation client...) | évaluée dans la norme |

Pour l'ISO/IEC 27001, 27701 et 42001, seules les annexes de mesures sont
cataloguées : le socle tient lieu de leurs chapitres 4 à 10. Une exigence
« commune » déjà évaluée avant la 3.4 n'est pas écrasée : elle reste « évaluée
séparément » et peut être rattachée au socle (bouton « Évaluer via le socle
commun » ; si le socle est encore vide, l'évaluation y est reprise avec ses
preuves). Les registres communs (audits, revues, documents, objectifs,
non-conformités) étaient déjà partagés entre normes.
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
