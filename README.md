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

Normes disponibles (3.8) :

| Norme | Type | Module propre |
|---|---|---|
| ISO/IEC 27001:2022 (socle) | 93 mesures (Annexe A) + DdA, 30 exigences (chapitres 4 à 10, 3.5) | toute l'application historique |
| ISO/IEC 27701:2019 | 49 mesures (Annexes A et B) | Vie privée : registre des traitements, demandes des personnes |
| ISO/IEC 42001:2023 | 38 mesures (Annexe A), 32 exigences (chapitres 4 à 10, 3.5) | Intelligence artificielle : systèmes d'IA, études d'impact |
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

Pour l'ISO/IEC 27701, seule l'annexe de mesures est cataloguée : ce n'est pas
une norme de système de management autonome (ses chapitres prolongent ceux de
l'ISO/IEC 27001), le socle et les exigences 27001 en tiennent lieu. Une exigence
« commune » déjà évaluée avant la 3.4 n'est pas écrasée : elle reste « évaluée
séparément » et peut être rattachée au socle (bouton « Évaluer via le socle
commun » ; si le socle est encore vide, l'évaluation y est reprise avec ses
preuves). Les registres communs (audits, revues, documents, objectifs,
non-conformités) étaient déjà partagés entre normes.
Une base neuve s'initialise avec `flask init-platform` (organisation + RSSI) ;
`flask init-db` est réservé au développement (il efface tout).

### Exigences des chapitres 4 à 10 de l'ISO/IEC 27001 et de l'ISO/IEC 42001 (3.5)

Ces deux normes ont à la fois des **mesures** (annexe A) et des **exigences**
(chapitres 4 à 10). Les deux sont dans la table `controls`, distinguées par la
colonne `kind` (`control` / `clause`), présente dans la clé unique
`(organization_id, framework_id, kind, ref)` : la mesure A.5.1 et l'exigence §5.1
de la 27001 coexistent. `Control.of(code)` ne renvoie que les mesures pour une
norme à mesures (DdA, tableau de bord, revue de direction, exports : toujours
93 mesures) ; `Control.of(code, "clause")` renvoie ses exigences. `annex_ref`
affiche « §6.1.2 » pour une exigence, « A.5.1 » pour une mesure.

- DdA › ISO/IEC 27001 (ou 42001) : sous-onglets **Mesures** (DdA inchangée) et
  **Exigences** (`/dda/?vue=exigences`, `/dda/?norme=ISO42001&vue=exigences`).
- Rattachement au socle (`COMMON` dans `catalogue_data.py`) : communes héritées,
  compléments (27001 §4.3, §6.2, §8.1, §9.3.2 ; 42001 §4.1, §6.1.1, §8.1),
  exigences propres (6.1.2, 6.1.3, 8.2, 8.3, et 6.1.4, 8.4 pour la 42001).
- Amendement 1:2024 (changement climatique, §4.1/§4.2) : texte harmonisé, donc
  couvert par le socle ; repère affiché sur les fiches §4.1 et §4.2 du socle.
- Fiche d'une exigence propre : panneau « Preuve dans l'application »
  (`app/services/proofs.py`) avec liens et indicateurs : critères de risque,
  registre des risques, plan de traitement, acceptation des risques résiduels,
  DdA 27001 ou 42001 (6.1.3 d), inventaire des systèmes d'IA, études d'impact.
- Migration (`flask upgrade-db`, idempotente) : colonne `kind`, nouvelle clé
  unique, exigences ajoutées aux normes actives de chaque organisation (héritées
  du socle si communes), sans toucher aux mesures existantes. Une norme
  désactivée les reçoit à sa réactivation.

### Registre des risques SMI (3.6)

Le registre des risques (clause 6.1, commune à toutes les normes) n'est plus
limité à la sécurité de l'information (`app/models/risk.py`) :

- **Domaine** (`risk_domain`) : sécurité de l'information (NULL, valeur
  historique), vie privée, IA, continuité, services IT, qualité. Le domaine
  donne les normes concernées par défaut (`DOMAINS`) ; la vie privée concerne
  aussi la 27001, qu'elle prolonge. Seuls les domaines des normes actives sont
  proposés.
- **Normes concernées** = normes du domaine + normes cochées en plus, stockées
  dans `FrameworkLink` (`set_links(..., collapse=False)` : pour un risque,
  l'absence de lien veut dire « la norme du domaine » et non « toutes les
  normes »). `Risk.framework_codes` et `Risk.concerns(code)` ; filtre « norme »
  du registre ; preuves des exigences 6.1.2 / 6.1.3 / 8.2 / 8.3 comptées par
  norme (`proofs.py`).
- **Mesures de traitement** : mesures d'annexe de toutes les normes actives
  (27001, 27701, 42001), regroupées par norme. Les mesures d'une norme
  désactivée restent rattachées.
- **Opportunités** (`nature = OPPORTUNITE`) : traitements propres (exploiter,
  renforcer, partager, ne pas donner suite) ; pas d'acceptation formelle
  (`acceptance_state = "not_applicable"`) ; exclues des risques élevés
  (`Risk.is_high`), de la matrice du tableau de bord et des « risques ouverts /
  élevés » de la revue de direction, comptées à part ; niveau affiché
  « Opportunité » (`display_level`).
- Exports registre et plan de traitement : nature, domaine, normes, mesures
  préfixées par leur norme hors 27001.
- Migration (`flask upgrade-db`) : `risks.treatment` passe de VARCHAR(8) à
  VARCHAR(16). Les risques existants gardent le domaine sécurité ; les risques
  IA, vie privée, etc. sont à reclasser pour apparaître dans les preuves de
  leur norme.

### Plan de traitement des risques (3.7)

Chaque risque porte des **actions datées** (`RiskAction`, table `risk_actions`) :
intitulé, mesure mise en œuvre (parmi les mesures du risque), responsable,
échéance, ressources, statut (prévue, en cours, réalisée, abandonnée),
avancement en %, résultat ou preuve. Exigences couvertes : 6.1.3 e) et 8.3 de
l'ISO/IEC 27001 et de l'ISO/IEC 42001, 6.1 des autres normes (pour une
opportunité : plan d'action pour la saisir).

- Fiche du risque, panneau **Plan de traitement** : ajout rapide, statut en un
  clic, retards signalés ; quand toutes les actions sont terminées, invitation
  à réévaluer le risque résiduel. Une première action fait passer le risque de
  « Identifié » à « En traitement ».
- **Gestion des risques › Plan de traitement** (`/risques/plan-de-traitement`) :
  toutes les actions, compteurs (ouvertes, en retard, échéance sous 30 jours,
  réalisées), filtres par état, responsable et norme.
- Exports : le plan de traitement liste les actions, ressources et avancement
  par risque ; nouvel export **Suivi des actions de traitement**
  (`actions-traitement`, une ligne par action). Colonnes du PDF choisies par
  `pdf_keep` (corrige le décalage du registre PDF introduit en 3.6).
- Relances : actions à échéance sous 7 jours ou en retard, au responsable.
- Revue de direction : actions de traitement ouvertes et en retard.
- Preuves des exigences 6.1.3 et 8.3 : actions datées, ouvertes, en retard et
  risques à traiter sans action.
- Démo : 9 actions sur les risques de Fictivia.
- Migration : table créée par `flask upgrade-db` (`db.create_all()`).

### Maillage SMI des risques (3.8)

Un risque se lie aux éléments des autres modules (`RiskLink`, table `risk_links`,
registre des types dans `app/services/risk_links.py`) : incidents,
non-conformités, changements, fournisseurs, activités de la BIA, et selon les
normes actives plans de continuité (22301), services IT (20000-1), traitements
de données (27701), systèmes d'IA et études d'impact (42001).

- Fiche du risque : panneau **Liens avec les autres modules** (liste par type,
  ajout, retrait).
- Fiches des 9 modules : panneau **Risques liés** (`partials/linked_risks.html`),
  avec ajout depuis l'élément.
- **Réévaluation (8.2)** : lier un incident, une non-conformité ou un
  changement à un risque ouvert demande sa réévaluation (`reassess_at`,
  `reassess_reason`, motifs cumulés). Bannière sur la fiche ; la demande est
  levée en enregistrant la fiche ou par « Cotation inchangée » (tracé dans la
  piste d'audit). Filtre « À réévaluer » du registre, relance du propriétaire,
  revue de direction, preuve de l'exigence 8.2 (27001, 42001).
- Export du registre : colonnes « Éléments liés » et « Réévaluation demandée »
  (en fin de tableau : colonnes du PDF inchangées).
- Suppression d'un élément lié : ses liens sont supprimés (`after_delete`).
- Démo : 18 liens, un risque à réévaluer (incident lié).
- Correctif démo : la réinitialisation recopie le catalogue des normes restées
  actives (auparavant seule la 27001 était rechargée).
- Migration : table créée par `flask upgrade-db`, colonnes `reassess_*` ajoutées.

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
