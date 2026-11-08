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

Normes disponibles (3.18) :

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

### Cohérence SMI et tableau de bord (3.9)

**Tableau de bord** (`app/services/readiness.py`), inspiré des plateformes de
conformité continue :
- **Préparation par norme** : une carte par norme active (socle commun en tête),
  avec la part des mesures et des exigences retenues qui sont mises en œuvre,
  la part qui dispose d'une preuve, les risques concernés et la date de
  certification visée. Le taux global est la moyenne des normes.
- **Points à traiter** : une seule liste pour tous les modules, triée par
  gravité, chaque ligne avec son lien. Elle couvre l'acceptation et la
  réévaluation des risques, les actions en retard (traitement, correctives,
  revue), les NC, les preuves manquantes, les documents, les fournisseurs, les
  exigences légales, ainsi que les modules des normes actives (demandes de
  personnes, AIPD, systèmes d'IA, plans de continuité, services IT,
  réclamations, satisfaction, processus).
- **Risques** : matrice, acceptations, réévaluations, plan de traitement
  (actions ouvertes ou en retard, avancement) et opportunités.
- **Mes tâches** : les relances de l'utilisateur connecté.
- **Pilotage** : indicateurs, objectifs, fournisseurs, exigences légales.

**Risques**
- Description structurée en cause (« menace ou cause »), événement redouté et
  conséquences (`consequence`).
- **Impact par dimension** (`impact_details`) : financier, clients, juridique,
  personnes concernées, continuité, image. L'organisation choisit ses
  dimensions dans les critères de risque. L'impact retenu est le maximum des
  dimensions cotées. Les cotations sont converties quand l'échelle change.
- Les enjeux du contexte (4.1) et les processus qualité (4.4) liés au risque
  sont affichés sur sa fiche.
- Import : domaine, nature, conséquences, traitements des opportunités (avec
  contrôle de cohérence).

**Multi-normes partout**
- Sélecteurs de mesures et d'exigences pour toutes les normes actives, socle
  compris (`frameworks.picker_groups`, macros `control_options` et
  `control_checklist`) : preuves, incidents, NC, indicateurs, exigences
  légales, constats d'audit.
- Revue de direction : conformité et preuves par norme, points des modules
  des normes, libellés « système de management ».
- Exports : DdA ou conformité de la norme affichée (`?norme=`, `?vue=`) ;
  références de clauses génériques pour les registres communs.
- Menu « Risques et opportunités » et « Conformité et DdA » ; plus de libellé
  « SMSI » dans les écrans multi-normes.

**Corrections**
- Réinitialisation de la démo : les données des modules des normes et les
  rattachements sont effacés avant les comptes. Avant, l'effacement échouait
  dès qu'un compte de démo était responsable d'un élément de ces modules.
- Purge de maintenance : rattachements et liens supprimés, et les actions
  correctives des NC (conservées) ne sont plus effacées ; le texte décrit
  exactement ce qui est supprimé.
- `move-records` : les rattachements aux normes suivent le risque. Les liens
  vers les autres modules et les actifs restés dans l'origine sont retirés,
  et les mesures non reprises sont signalées.
- Page plateforme : les opportunités ne sont plus comptées comme des risques.
- Migration : colonnes `risks.consequence` et `risks.impact_details`.

### Lecture et acceptation des politiques (3.10)

Un document peut exiger que les personnes concernées le lisent et l'acceptent.
Exigences couvertes : chapitres 5.2 et 7.3 des normes (politique communiquée,
personnes conscientes de la politique), ISO/IEC 27001 A.5.1 et A.6.3.

- **Réglage du document** : « Lecture et acceptation requises », rôles
  concernés (aucun coché = tous les comptes actifs, sauf ceux en lecture
  seule) et délai en jours après approbation (`documents.ack_*`).
- **Acceptation** (`PolicyAcceptance`) : par personne et par version. Seule la
  version approuvée en vigueur est concernée ; une nouvelle version approuvée
  demande une nouvelle acceptation à tous. La case « J'ai lu ce document et je
  m'engage à le respecter » est obligatoire. L'heure et l'adresse IP sont
  conservées, et l'acceptation est tracée dans la piste d'audit.
- **Pour chaque personne** : un bandeau sur toutes les pages tant qu'une
  politique est en attente ; la page **Documents › Mes politiques à accepter**
  (`/documents/a-accepter`) ; le bouton d'acceptation sur la fiche du
  document ; les relances.
- **Pour le RSSI et l'auditeur** : la page **Documents › Suivi des
  acceptations** (taux, personnes en attente, hors délai) et le suivi sur la
  fiche ; l'export « Registre des acceptations des politiques » ; les points à
  traiter du tableau de bord ; les preuves des exigences 5.2 et 7.3 du socle
  commun.
- `move-records` d'un document : les acceptations des personnes restées dans
  l'organisation d'origine sont retirées.
- **Démo** : la PSSI, le contrôle d'accès, la cryptographie (équipes
  techniques) et le télétravail sont soumis à acceptation, avec des
  acceptations partielles, dont une hors délai.
- **Migration** : table `policy_acceptances` et colonnes `documents.ack_*`.

### Page de confiance publique (3.11)

Une page publique, sans connexion, à l'adresse `/confiance/<slug>`, sur le
modèle des « Trust Centers ». Elle se règle dans **Administration › Page de
confiance** (`app/blueprints/trust`, `app/services/trust.py`). Rien n'est
publié sans un choix explicite du RSSI.

- **Présentation** : titre, texte, bouton de contact sécurité, option de
  non-référencement (activée par défaut).
- **Certifications** des normes choisies : « Certifiée » (date et organisme)
  ou « Mise en conformité en cours » (mois visé), d'après les référentiels.
  Aucun pourcentage interne n'est affiché.
- **Mesures en place** (option) : les mesures d'annexe retenues et
  implémentées, par thème.
- **Documents approuvés** : chaque document est soit *public*
  (téléchargeable), soit *sur demande*. Le visiteur envoie une demande (nom,
  e-mail, société, motif, consentement ; champ piège anti-robot ; 3 demandes
  par jour et par e-mail au maximum). Le contact est notifié. Le RSSI accorde
  l'accès pour N jours, et un lien personnel signé est envoyé par e-mail et
  affiché dans la gestion. Le RSSI peut aussi refuser ou révoquer. Les
  téléchargements sont comptés.
- **Sous-traitants** choisis : fournisseurs actifs seulement (nom, catégorie,
  service, certifications).
- **Isolation** : sans connexion, il n'y a pas d'organisation courante, donc
  chaque page publique fixe explicitement l'organisation. Les documents et
  les pièces jointes servis sont contrôlés : organisation, statut approuvé,
  visibilité. Un lien d'accès est lié à sa demande et à son organisation.
- Les demandes en attente apparaissent dans les points à traiter du tableau
  de bord. La page non publiée reste visible en aperçu pour le RSSI.
- **Démo** : la page est publiée, avec la PSSI publique, deux politiques sur
  demande, quatre sous-traitants et deux demandes (une accordée, une en
  attente).
- **Migration** : table `trust_requests`, colonnes `documents.trust_visibility`
  et `suppliers.trust_public`.

### Bibliothèque de scénarios de risques (3.12)

**Risques et opportunités › Bibliothèque de scénarios** (`/risques/bibliotheque`)
propose **347 scénarios prêts à l'emploi**, dont 41 opportunités, rédigés
selon ISO 31000, ISO/IEC 27005 et EBIOS RM :

| Domaine | Scénarios | Fichier (`app/services/risk_library/`) |
|---|---|---|
| Sécurité de l'information - menaces externes | 60 | `securite_externe.py` (SEC-) |
| Sécurité de l'information - menaces internes, organisation, physique | 60 | `securite_interne.py` (SEI-) |
| Vie privée (RGPD, loi organique tunisienne n° 2004-63) | 45 | `vie_privee.py` (PRV-) |
| Intelligence artificielle (ISO/IEC 42001, AI Act) | 46 | `ia.py` (IA-) |
| Continuité d'activité (ISO 22301) | 45 | `continuite.py` (CON-) |
| Services informatiques (ISO/IEC 20000-1) | 40 | `services_it.py` (SRV-) |
| Qualité (ISO 9001), tous secteurs | 51 | `qualite.py` (QUA-) |

Chaque scénario comporte :
- une famille, un événement redouté, une cause, une vulnérabilité et des
  conséquences ;
- une vraisemblance et des impacts par dimension, sur 5 niveaux ;
- une option de traitement ;
- des mesures d'annexe (27001, 27701, 42001) et des exigences de référence
  (22301, 20000-1, 9001) ;
- 2 à 4 actions de traitement ;
- les secteurs concernés et, le cas échéant, des références réglementaires.

**Recherche et filtres** : par domaine, nature, famille et secteur, avec une
recherche plein texte qui ne tient compte ni des accents ni des majuscules.

**Import** (sélection multiple) : un risque est créé par scénario, avec :
- la cotation convertie aux échelles de l'organisation ;
- les impacts limités aux dimensions activées ;
- le rattachement des seules mesures des normes actives ;
- les actions proposées (option) et le propriétaire choisi ;
- l'origine notée dans la description.

Un scénario déjà présent (même intitulé) est ignoré. Importer un seul scénario
ouvre directement sa fiche. La bibliothèque est aussi proposée depuis
« Nouveau risque » et depuis le registre vide.

**Ajouter des scénarios** : il suffit de compléter un module du paquet. Toutes
les références sont contrôlées par les tests contre les catalogues de
l'application.

### Listes et actions en masse (3.18)

- **Sur 28 listes** : cases à cocher (Maj + clic pour une plage), export CSV de la
  sélection, attribution d'un responsable (contributeurs et RSSI), changement de
  statut (actifs, fournisseurs).
- **Suppression en masse** (RSSI) : écran de confirmation, mot SUPPRIMER à saisir.
  Bloqués : éléments encore utilisés, actifs suivis par un connecteur. Protégés sauf
  décision explicite : enregistrements clos (ISO 7.5.3), risques acceptés, documents
  approuvés. Copie de chaque fiche au journal d'activité (`app/services/bulk.py`).
- **Partout** : tri par colonne, Ctrl + clic ou clic molette pour ouvrir une ligne
  dans un nouvel onglet.

### Écrans denses (3.17)

- **Page de confiance** : onglets Demandes, Publication, Documents, Sous-traitants ;
  les demandes en attente arrivent en premier ; filtre des documents.
- **Formulaire de risque** : score et niveau calculés en direct, actifs et mesures
  en listes à cocher avec recherche et compteur.
- **Bibliothèque** : affichage par tranches de 40 ; filtres et sélection portent
  sur tous les scénarios.

### Ergonomie (3.16)

- **Référentiels** : cartes compactes, activation en un clic sur un seul écran.
- **Densité** : champs et lignes de tableau resserrés, dates et nombres à largeur
  utile, filtres sur une ligne.
- **Navigation** : recherche de page dans le menu (Ctrl K).
- **Formulaires** : bouton d'enregistrement toujours visible sur les formulaires
  longs, alerte avant de quitter avec des modifications non enregistrées, envoi
  protégé contre le double clic.
- **Accessibilité** : libellés des filtres pour les lecteurs d'écran, contrastes
  corrigés. **Téléphone** : plus de débordement horizontal.

### Connecteurs d'inventaire (3.15)

Administration > Connecteurs (RSSI) : GLPI, Microsoft Intune, Entra ID (applications
SaaS), Azure et AWS (`app/services/connectors/`). Tout autre outil peut pousser ses
actifs avec `POST /api/v1/actifs/synchronisation` (portée `actifs:ecriture`).

- **Règles** : la source actualise nom, localisation, statut, détenteur et dates.
  Besoins DIC+T, classification, propriétaire et dépendances ne sont jamais modifiés.
  Un actif retiré dans Integra le reste. Un actif disparu de la source est signalé
  (`source_missing_since`, filtre « Absents de leur outil source »), jamais supprimé.
- **Rapprochement** : identifiant externe, puis nom unique parmi les actifs sans source.
  Un nom déjà suivi par un autre connecteur n'est pas dupliqué.
- **Parcours** : tester, aperçu sans écriture, puis synchroniser. Mode automatique :
  planifier `flask sync-connectors` chaque nuit.
- **Sécurité** : secrets chiffrés (Fernet, clé dérivée de `SECRET_KEY`) ; changer
  l'adresse GLPI impose de ressaisir les secrets ; adresses internes refusées et
  redirections bloquées, sauf `CONNECTORS_ALLOW_PRIVATE=1` dans `.env` pour un GLPI
  du réseau local (installation sur site à organisation unique).

### Export de l'inventaire et API (3.14)

- **Export** depuis l'inventaire, aux filtres de l'écran : Excel, CSV (`;`, UTF-8
  avec BOM), Word, et PDF si OnlyOffice est configuré. Les 15 premières colonnes
  reprennent le modèle d'import : un fichier exporté se réimporte sans changement.
  Les formules présentes dans les données sont neutralisées.
- **API REST en lecture seule** : `GET /api/v1/actifs` (filtres de l'inventaire,
  `reference`, `modifie_depuis`, pagination) et `GET /api/v1/actifs/<id>`, décrites
  dans `/api/v1/openapi.json`. Seul l'en-tête `Authorization: Bearer <jeton>` donne
  accès, un cookie de session ne suffit pas.
- **Jetons** (Administration > API et intégrations, RSSI) : par organisation, durée
  de 30 jours à 1 an, révocables. Seule l'empreinte SHA-256 est stockée (`api_tokens`).
- **Maîtrise** : 120 appels par minute et par jeton (429 et `Retry-After`), chaque
  appel authentifié inscrit au journal (action `api`), `Cache-Control: no-store`.
- Filtres communs à l'écran, aux exports et à l'API : `app/services/inventory.py`.

### Actifs : valeurs métier, besoins DIC+T, cycle de vie (3.13)

Inventaire selon ISO/IEC 27005 et EBIOS RM (`app/models/asset.py`) :
- **Valeurs métier** (catégories Information et Processus, ce dernier étant
  nouveau) et **biens supports** (logiciels, matériels, services, sites,
  personnel). Les dépendances sont gérées dans la table `asset_dependencies` :
  une valeur métier choisit ses biens supports, et un bien support choisit
  les valeurs métier qu'il porte.
- **Besoins de sécurité** C, I, D, T de 1 (faible) à 4 (critique) : ceux de la
  valeur métier ; un bien support retient le **maximum** de ses propres
  besoins et de ceux des valeurs métier portées (`Asset.needs()`, avec la
  source affichée). La criticité est le besoin le plus élevé. La fiche d'un
  risque affiche la sensibilité de ses actifs.
- **Cycle de vie** : mise en service ; fin de support (alerte 180 jours, A.8.8) ;
  détenteur (restitution quand son compte est désactivé, A.5.11) ;
  élimination avec méthode et preuve (A.7.14).
- **Inventaire** : indicateurs (valeurs métier, biens supports, critiques, fin
  de support) et filtres par rôle, criticité et cycle de vie (fin de support,
  à restituer, élimination à prouver, sans cotation, sans propriétaire).
- **Points à traiter**, **relances** des propriétaires, **alerte** à la
  désactivation d'un compte qui détient du matériel.
- **Import** : besoins C, I, D, T (chiffres sur l'échelle du fichier, ou
  libellés faible… critique), dates de mise en service et de fin de support,
  catégorie Processus.
- **Démo** : trois valeurs métier ajoutées, besoins cotés, dépendances, un
  pare-feu hors support, des portables en fin de garantie, un ancien serveur
  sans certificat d'effacement.
- **Migration** : colonnes `assets.need_*`, colonnes de cycle de vie, table
  `asset_dependencies`.

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
