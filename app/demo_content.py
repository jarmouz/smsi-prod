"""Contenu de l'organisation de démonstration « Fictivia » (entreprise fictive).

Scénario : éditeur SaaS de gestion de la paie et des RH, ~180 collaborateurs,
siège à Tunis + agence à Sfax, plateforme hébergée chez un fournisseur IaaS
certifié ISO/IEC 27001. Le SMSI est déployé depuis ~10 mois ; l'audit de
certification (étape 1) est prévu dans ~2 mois. Le jeu de données montre donc
un SMSI crédible mais encore perfectible : mesures en cours, non-conformités
ouvertes, actions en retard, risques résiduels à arbitrer.

Les dates sont exprimées en jours relatifs à la date du chargement (J+n / J-n)
pour que la démo reste toujours d'actualité.
"""

ORG_NAME = "Fictivia SaaS (DÉMO)"
ORG_SLUG = "demo"
DEMO_PASSWORD = "Demo-ISO27001!"
DOMAIN = "fictivia.demo"   # domaine non délégué : aucun e-mail ne peut partir

# clé -> (prénom nom, rôle, fonction)
USERS = {
    "rssi":  ("Leïla Ben Salah", "RSSI", "RSSI - Responsable SMSI"),
    "dg":    ("Nabil Mansour", "LECTEUR", "Directeur général"),
    "dsi":   ("Karim Trabelsi", "CONTRIBUTEUR", "Directeur des systèmes d'information"),
    "infra": ("Youssef Haddad", "CONTRIBUTEUR", "Responsable infrastructure & cloud"),
    "dev":   ("Mehdi Chaabane", "CONTRIBUTEUR", "Responsable développement (CTO adjoint)"),
    "dpo":   ("Sonia Gharbi", "CONTRIBUTEUR", "DPO - Juriste conformité"),
    "rh":    ("Ines Khelifi", "CONTRIBUTEUR", "Responsable ressources humaines"),
    "audit": ("Amel Jaziri", "AUDITEUR", "Auditrice interne (certifiée ISO 27001 LA)"),
}

# Compte à remettre aux prospects : lecture seule, mot de passe distinct de celui
# des comptes de l'équipe de démo (qui peuvent tout modifier).
PROSPECT = ("prospect", "Visiteur (démonstration)", "Compte de démonstration - lecture seule")
PROSPECT_PASSWORD = "Visite-SMSI-2026"

# Administrateur en lecture seule : voit tout Fictivia comme un RSSI (administration,
# console Plateforme limitée à Fictivia) sans pouvoir rien modifier.
DEMO_ADMIN = ("demo", "Administrateur démo", "Super-administrateur Fictivia - lecture seule")
DEMO_ADMIN_PASSWORD = "Admin-Demo-2026"

SCOPE = ("Conception, développement, hébergement et support de la plateforme SaaS "
         "« Fictivia Paie & RH », sites de Tunis (siège) et Sfax, infrastructure hébergée "
         "chez le fournisseur IaaS (région UE).")

# ---------------------------------------------------------------------------
# Déclaration d'applicabilité : ref -> (statut, responsable, mise en œuvre)
# statut : I = implémentée, E = en cours, N = non démarrée, X = exclue
# ---------------------------------------------------------------------------
_R = "Retenue : réponse à des risques identifiés dans l'appréciation des risques."
_L = "Retenue : exigence légale et réglementaire (loi organique n° 2004-63 sur les données personnelles, RGPD pour les clients UE)."
_C = "Retenue : exigence contractuelle des clients (annexe sécurité des contrats SaaS)."
_B = "Retenue : exigence du référentiel et bonne pratique indispensable au périmètre SaaS."

SOA = {
    # --- A.5 Mesures organisationnelles ---
    "5.1": ("I", "rssi", _B, "PSSI v2.1 approuvée par la direction générale, publiée sur l'intranet et déclinée en 12 politiques thématiques. Revue annuelle."),
    "5.2": ("I", "rssi", _B, "Fiche de fonction RSSI, comité sécurité mensuel, matrice RACI du SMSI annexée au manuel SMSI."),
    "5.3": ("E", "dsi", _R, "Séparation développement / mise en production effective ; séparation des rôles comptables dans l'ERP en cours de revue."),
    "5.4": ("I", "dg", _B, "Engagement signé de la direction, objectifs sécurité intégrés aux objectifs annuels des managers."),
    "5.5": ("I", "dpo", _L, "Contacts formalisés : INPDP, ANCS / tunCERT, police judiciaire. Procédure de notification de violation."),
    "5.6": ("I", "rssi", _B, "Adhésion au CLUSIF et aux alertes tunCERT ; participation à un groupe d'échange RSSI SaaS."),
    "5.7": ("E", "infra", _R, "Flux de renseignement (tunCERT, CERT-FR, éditeur EDR) reçus ; analyse et capitalisation à formaliser."),
    "5.8": ("E", "dev", _R, "Fiche « sécurité projet » intégrée au cadrage ; appliquée à 60 % des projets du semestre."),
    "5.9": ("I", "dsi", _B, "Inventaire des actifs tenu dans le SMSI (module Actifs), revu trimestriellement, propriétaires désignés."),
    "5.10": ("I", "rssi", _B, "Charte informatique signée par 100 % des collaborateurs, règles d'usage acceptable des actifs."),
    "5.11": ("I", "rh", _B, "Check-list de départ RH/IT : restitution du matériel et des badges tracée dans l'outil RH."),
    "5.12": ("I", "dpo", _R, "Politique de classification à 4 niveaux (Public, Interne, Confidentiel, Secret)."),
    "5.13": ("E", "dpo", _R, "Marquage automatique des documents Office déployé à 50 % ; marquage des exports clients à faire."),
    "5.14": ("I", "infra", _C, "Transferts chiffrés (TLS 1.2+, SFTP), clauses de transfert dans les contrats, partage externe encadré."),
    "5.15": ("I", "dsi", _R, "Politique de contrôle d'accès basée sur les rôles (RBAC), principe du moindre privilège."),
    "5.16": ("I", "infra", _R, "Annuaire centralisé (SSO), cycle de vie des identités relié au SIRH."),
    "5.17": ("I", "infra", _R, "MFA obligatoire pour tous les accès distants et l'administration ; politique de mots de passe conforme."),
    "5.18": ("E", "dsi", _R, "Revue trimestrielle des droits mise en place après la NC majeure de l'audit interne ; 2e campagne en cours."),
    "5.19": ("I", "rssi", _C, "Politique fournisseurs : classification des fournisseurs par criticité et exigences sécurité associées."),
    "5.20": ("I", "dpo", _C, "Clauses sécurité et protection des données (DPA) dans les contrats des fournisseurs critiques."),
    "5.21": ("E", "dsi", _R, "Cartographie de la chaîne d'approvisionnement TIC réalisée ; exigences sur les sous-traitants de rang 2 à formaliser."),
    "5.22": ("E", "rssi", _R, "Évaluation annuelle des fournisseurs critiques : 9 sur 12 réalisées (NC mineure audit interne)."),
    "5.23": ("I", "infra", _R, "Fournisseur IaaS certifié ISO 27001/27017/27018, matrice de responsabilité partagée, revue des rapports d'audit."),
    "5.24": ("I", "rssi", _B, "Procédure de gestion des incidents PR-INC-01, astreinte 24/7, outil de ticketing dédié."),
    "5.25": ("I", "rssi", _B, "Grille de qualification des événements (gravité / impact) intégrée à la procédure."),
    "5.26": ("I", "infra", _B, "Playbooks de réponse (phishing, rançongiciel, fuite de données, indisponibilité)."),
    "5.27": ("I", "rssi", _B, "Retour d'expérience systématique pour les incidents majeurs, actions suivies dans le SMSI."),
    "5.28": ("E", "rssi", _L, "Procédure de recueil de preuves rédigée ; formation de l'équipe d'astreinte prévue."),
    "5.29": ("E", "dsi", _R, "Exigences de sécurité en mode dégradé intégrées au PCA ; à valider lors du prochain exercice."),
    "5.30": ("E", "infra", _C, "PRA documenté (RTO 4 h / RPO 1 h) ; test de bascule complet non encore réalisé (NC mineure)."),
    "5.31": ("I", "dpo", _L, "Registre des exigences légales, réglementaires et contractuelles tenu par la DPO, revu semestriellement."),
    "5.32": ("I", "dsi", _L, "Gestion des licences logicielles et revue des composants open source (SCA) dans la CI."),
    "5.33": ("I", "dpo", _L, "Durées de conservation définies, archivage sécurisé des enregistrements de paie (10 ans)."),
    "5.34": ("I", "dpo", _L, "Registre des traitements, AIPD sur la plateforme, DPO désigné, procédure d'exercice des droits."),
    "5.35": ("N", "dg", _B, "Revue indépendante : audit de certification planifié ; aucun audit externe réalisé à ce jour."),
    "5.36": ("I", "rssi", _B, "Contrôles de conformité trimestriels (indicateurs SMSI) et audit interne annuel."),
    "5.37": ("I", "infra", _B, "Procédures d'exploitation documentées dans le wiki (runbooks) et revues à chaque changement majeur."),
    # --- A.6 Mesures liées aux personnes ---
    "6.1": ("I", "rh", _L, "Vérification des antécédents proportionnée au poste (diplômes, références, B3 pour les postes sensibles)."),
    "6.2": ("I", "rh", _B, "Clauses de sécurité et de confidentialité dans les contrats de travail."),
    "6.3": ("I", "rssi", _R, "Programme annuel : e-learning d'intégration, campagnes de phishing trimestrielles, formation développeurs."),
    "6.4": ("I", "rh", _B, "Processus disciplinaire référencé dans le règlement intérieur et la charte informatique."),
    "6.5": ("I", "rh", _B, "Obligations de confidentialité post-contractuelles rappelées lors de l'entretien de départ."),
    "6.6": ("I", "dpo", _C, "Accords de confidentialité signés par les collaborateurs, stagiaires et prestataires."),
    "6.7": ("I", "dsi", _R, "Politique de télétravail : poste chiffré, VPN + MFA, interdiction des réseaux publics non protégés."),
    "6.8": ("I", "rssi", _B, "Bouton « signaler un phishing » et adresse securite@ ; 94 signalements sur le dernier trimestre."),
    # --- A.7 Mesures physiques ---
    "7.1": ("I", "infra", _R, "Périmètres définis pour les sites de Tunis et Sfax (zones publique / bureaux / local technique)."),
    "7.2": ("E", "infra", _R, "Contrôle d'accès par badge au siège ; déploiement à l'agence de Sfax prévu au prochain trimestre."),
    "7.3": ("I", "infra", _R, "Bureaux fermés à clé hors présence, armoires sécurisées pour les dossiers RH."),
    "7.4": ("I", "infra", _R, "Vidéoprotection des accès et du local technique, conservation 30 jours."),
    "7.5": ("I", "infra", _R, "Détection incendie, onduleur, climatisation redondée du local technique."),
    "7.6": ("X", "infra", "Exclue : aucune zone sécurisée (salle informatique) sous la responsabilité de l'organisme ; la production est hébergée chez le fournisseur IaaS certifié, dont les zones sécurisées sont couvertes par A.5.19 à A.5.23.", ""),
    "7.7": ("E", "rssi", _R, "Verrouillage automatique des sessions (5 min) déployé ; contrôles « bureau propre » à généraliser."),
    "7.8": ("I", "infra", _R, "Équipements réseau du siège dans une baie fermée, local technique à accès restreint."),
    "7.9": ("I", "dsi", _R, "Portables chiffrés (BitLocker), localisation et effacement à distance via MDM."),
    "7.10": ("I", "infra", _R, "Ports USB de stockage bloqués par défaut ; supports amovibles chiffrés sur dérogation."),
    "7.11": ("I", "infra", _B, "Onduleur, double fournisseur d'accès Internet au siège, contrats de maintenance."),
    "7.12": ("I", "infra", _B, "Câblage en goulottes fermées, baie verrouillée, plan de câblage à jour."),
    "7.13": ("I", "infra", _B, "Maintenance préventive des équipements selon les préconisations constructeur."),
    "7.14": ("I", "infra", _R, "Effacement certifié (NIST 800-88) ou destruction physique avec certificat du prestataire."),
    # --- A.8 Mesures technologiques ---
    "8.1": ("I", "dsi", _R, "Postes gérés (MDM), durcissement CIS, chiffrement, EDR et mises à jour automatiques."),
    "8.2": ("I", "infra", _R, "Comptes à privilèges nominatifs, bastion d'administration avec enregistrement des sessions, MFA."),
    "8.3": ("I", "dev", _R, "Cloisonnement multi-tenant applicatif, contrôles d'autorisation testés à chaque version."),
    "8.4": ("I", "dev", _R, "Dépôts de code privés, accès par équipe, branches protégées, revue de code obligatoire."),
    "8.5": ("I", "infra", _R, "SSO + MFA pour les applications internes, MFA proposé aux clients, verrouillage anti-force-brute."),
    "8.6": ("I", "infra", _C, "Supervision de la capacité, mise à l'échelle automatique, revue mensuelle des tendances."),
    "8.7": ("I", "infra", _R, "EDR sur 100 % des postes et serveurs, filtrage des pièces jointes, sandboxing."),
    "8.8": ("E", "infra", _R, "Scans de vulnérabilités hebdomadaires ; délai de correction des critiques à 15 j non tenu sur 2 cas."),
    "8.9": ("E", "infra", _R, "Infrastructure as Code (Terraform) pour la production ; référentiel de configuration des postes en cours."),
    "8.10": ("I", "dpo", _L, "Suppression des données clients en fin de contrat (J+90) avec attestation."),
    "8.11": ("E", "dev", _L, "Pseudonymisation des jeux de données de recette en cours de déploiement."),
    "8.12": ("N", "rssi", _R, "Solution DLP en cours de sélection (budget validé en revue de direction)."),
    "8.13": ("I", "infra", _R, "Sauvegardes chiffrées quotidiennes, copie immuable hors région, tests de restauration mensuels."),
    "8.14": ("I", "infra", _C, "Architecture multi-zones de disponibilité, base de données répliquée."),
    "8.15": ("I", "infra", _R, "Journalisation centralisée (SIEM), conservation 12 mois, horodatage synchronisé."),
    "8.16": ("E", "infra", _R, "SOC externalisé en phase de déploiement ; règles de détection couvrant 70 % des cas d'usage."),
    "8.17": ("I", "infra", _B, "Synchronisation NTP sur des sources de référence pour l'ensemble des systèmes."),
    "8.18": ("I", "infra", _R, "Outils utilitaires à privilèges restreints aux administrateurs, usage journalisé."),
    "8.19": ("I", "dsi", _R, "Installation de logiciels réservée à la DSI, catalogue d'applications autorisées."),
    "8.20": ("I", "infra", _R, "Pare-feu nouvelle génération, segmentation, accès d'administration via bastion uniquement."),
    "8.21": ("I", "infra", _C, "Exigences de sécurité dans les contrats des opérateurs, WAF et anti-DDoS devant la plateforme."),
    "8.22": ("I", "infra", _R, "VLAN séparés (bureautique, invités, administration), environnements cloud isolés par VPC."),
    "8.23": ("I", "dsi", _R, "Filtrage web par catégories et réputation, y compris pour les postes en télétravail."),
    "8.24": ("I", "infra", _R, "Politique cryptographique : TLS 1.2+, AES-256 au repos, gestion des clés via KMS."),
    "8.25": ("E", "dev", _R, "Cycle de développement sécurisé défini (Secure SDLC) ; menaces modélisées pour 2 modules sur 6."),
    "8.26": ("I", "dev", _C, "Exigences de sécurité applicative (OWASP ASVS niveau 2) intégrées aux spécifications."),
    "8.27": ("I", "dev", _B, "Principes d'architecture sécurisée documentés (défense en profondeur, zero trust)."),
    "8.28": ("I", "dev", _R, "Règles de codage sécurisé, analyse statique (SAST) et des dépendances (SCA) bloquantes dans la CI."),
    "8.29": ("E", "dev", _C, "Tests de sécurité en CI ; test d'intrusion annuel réalisé, retest des vulnérabilités élevées en attente."),
    "8.30": ("X", "dev", "Exclue : aucun développement n'est externalisé ; l'ensemble du code est produit par les équipes internes (à réévaluer en cas de recours à un prestataire).", ""),
    "8.31": ("I", "infra", _R, "Environnements de développement, recette et production séparés (comptes cloud distincts)."),
    "8.32": ("I", "dsi", _B, "Processus de gestion des changements (CAB hebdomadaire), changements standards pré-approuvés."),
    "8.33": ("E", "dev", _L, "Interdiction des données de production en recette ; outil d'anonymisation en cours (voir A.8.11)."),
    "8.34": ("I", "rssi", _B, "Tests d'audit planifiés hors production ou en lecture seule, accord préalable de la DSI."),
}

# ---------------------------------------------------------------------------
# Actifs : (nom, catégorie, classification, responsable, dépositaire, emplacement, statut, description)
# ---------------------------------------------------------------------------
ASSETS = [
    ("Plateforme SaaS « Fictivia Paie & RH »", "LOGICIEL", "CONFIDENTIEL", "dev", "Équipe produit", "Cloud IaaS - région UE", "ACTIF", "Application multi-tenant de paie et de gestion RH utilisée par 240 clients."),
    ("Base de données de production (données de paie clients)", "INFORMATION", "SECRET", "infra", "Équipe infrastructure", "Cloud IaaS - région UE", "ACTIF", "Données personnelles et salariales de ~95 000 salariés des clients."),
    ("Sauvegardes de production", "INFORMATION", "SECRET", "infra", "Équipe infrastructure", "Stockage objet immuable - région secondaire", "ACTIF", "Sauvegardes chiffrées quotidiennes, rétention 35 jours."),
    ("Code source de la plateforme", "INFORMATION", "CONFIDENTIEL", "dev", "Équipe développement", "Forge Git SaaS", "ACTIF", "Dépôts applicatifs et Infrastructure as Code."),
    ("Annuaire et SSO", "SERVICE", "CONFIDENTIEL", "infra", "Équipe infrastructure", "SaaS", "ACTIF", "Référentiel des identités, authentification unique et MFA."),
    ("Messagerie et suite collaborative", "SERVICE", "INTERNE", "dsi", "Support IT", "SaaS", "ACTIF", "Messagerie, agenda, stockage bureautique."),
    ("SIRH interne (dossiers du personnel)", "LOGICIEL", "CONFIDENTIEL", "rh", "Ressources humaines", "SaaS", "ACTIF", "Dossiers des 180 collaborateurs de Fictivia."),
    ("ERP finance et facturation", "LOGICIEL", "CONFIDENTIEL", "dg", "Direction financière", "SaaS", "ACTIF", "Comptabilité, facturation des abonnements clients."),
    ("SIEM / journalisation centralisée", "SERVICE", "CONFIDENTIEL", "infra", "SOC externalisé", "Cloud IaaS - région UE", "ACTIF", "Collecte et corrélation des journaux de sécurité."),
    ("Bastion d'administration", "LOGICIEL", "SECRET", "infra", "Équipe infrastructure", "Cloud IaaS - région UE", "ACTIF", "Point d'accès unique et enregistré pour l'administration."),
    ("Pare-feu et routeurs du siège", "MATERIEL", "INTERNE", "infra", "Équipe infrastructure", "Siège Tunis - local technique", "ACTIF", "Pare-feu nouvelle génération en cluster."),
    ("Parc de postes portables (190)", "MATERIEL", "INTERNE", "dsi", "Support IT", "Sites et télétravail", "ACTIF", "Postes chiffrés, gérés par MDM, protégés par EDR."),
    ("Ancien serveur de fichiers", "MATERIEL", "INTERNE", "dsi", "Support IT", "Siège Tunis - local technique", "RETIRE", "Retiré après migration vers la suite collaborative ; disques détruits avec certificat."),
    ("Serveur d'intégration continue", "LOGICIEL", "CONFIDENTIEL", "dev", "Équipe développement", "Cloud IaaS - région UE", "MAINTENANCE", "Migration vers des agents éphémères en cours."),
    ("Équipe d'administration système (4 personnes)", "PERSONNEL", "CONFIDENTIEL", "infra", "", "Siège Tunis", "ACTIF", "Compétences critiques : astreinte, cloud, bastion."),
    ("Siège social - Tunis", "SITE", "INTERNE", "dg", "Services généraux", "Tunis, Les Berges du Lac", "ACTIF", "140 collaborateurs, local technique."),
    ("Agence - Sfax", "SITE", "INTERNE", "dg", "Services généraux", "Sfax", "ACTIF", "40 collaborateurs (support et développement)."),
    ("Site vitrine et documentation publique", "INFORMATION", "PUBLIC", "dsi", "Marketing", "Hébergement web", "ACTIF", "Contenus publics, aucune donnée client."),
]

# ---------------------------------------------------------------------------
# Risques (ISO/IEC 27005) :
# (titre, actif, menace, vulnérabilité, V, I, traitement, V rés., I rés., statut, propriétaire, mesures, description)
# ---------------------------------------------------------------------------
RISKS = [
    ("Rançongiciel sur l'infrastructure de production", "Plateforme SaaS et base de production",
     "Groupe cybercriminel", "Comptes d'administration exposés, détection tardive", 4, 5, "REDUIRE", 2, 5,
     "EN_TRAITEMENT", "infra", ["8.7", "8.13", "8.16", "8.2", "5.26"],
     "Chiffrement des données de production et des sauvegardes, interruption du service pour 240 clients."),
    ("Fuite de données de paie suite à une faille applicative", "Plateforme SaaS",
     "Attaquant externe", "Défaut de cloisonnement multi-tenant ou injection", 3, 5, "REDUIRE", 2, 4,
     "EN_TRAITEMENT", "dev", ["8.25", "8.26", "8.28", "8.29", "8.3"],
     "Accès aux données d'un client par un autre client ou par un tiers : violation de données à notifier."),
    ("Compromission de compte par hameçonnage", "Messagerie, SSO",
     "Hameçonnage ciblé", "MFA contournable par fatigue de notifications", 4, 4, "REDUIRE", 2, 3,
     "TRAITE", "rssi", ["6.3", "5.17", "8.5", "8.23"],
     "Usurpation d'identité d'un collaborateur, rebond vers les outils internes."),
    ("Indisponibilité prolongée du fournisseur IaaS", "Plateforme SaaS",
     "Panne majeure chez le fournisseur", "Dépendance à une seule région", 2, 5, "REDUIRE", 2, 5,
     "EN_TRAITEMENT", "infra", ["5.30", "8.14", "5.23"],
     "Non-respect des SLA (99,9 %) et pénalités contractuelles."),
    ("Abus de privilèges par un administrateur", "Bastion, base de production",
     "Administrateur malveillant ou négligent", "Droits étendus, revue des accès irrégulière", 2, 5, "REDUIRE", 1, 5,
     "EN_TRAITEMENT", "dsi", ["8.2", "5.18", "8.15", "5.3"],
     "Extraction ou altération de données clients sans détection."),
    ("Utilisation de données de production en recette", "Environnements de recette",
     "Erreur interne", "Absence d'outil d'anonymisation", 3, 4, "REDUIRE", 1, 4,
     "EN_TRAITEMENT", "dev", ["8.11", "8.33", "8.31"],
     "Exposition de données personnelles dans des environnements moins protégés."),
    ("Défaillance d'un fournisseur critique non évalué", "Services SaaS tiers",
     "Fournisseur compromis", "Évaluation sécurité incomplète des fournisseurs", 3, 4, "REDUIRE", 2, 3,
     "EN_TRAITEMENT", "rssi", ["5.19", "5.20", "5.21", "5.22"],
     "Compromission par la chaîne d'approvisionnement (attaque par rebond)."),
    ("Vol ou perte d'un poste portable", "Parc de postes portables",
     "Vol, oubli", "Mobilité, télétravail", 4, 2, "REDUIRE", 4, 1,
     "TRAITE", "dsi", ["7.9", "8.1", "6.7"],
     "Impact limité grâce au chiffrement intégral et à l'effacement à distance."),
    ("Vulnérabilité critique non corrigée dans les délais", "Serveurs et composants applicatifs",
     "Exploitation de vulnérabilité connue", "Processus de correctifs non tenu", 3, 4, "REDUIRE", 2, 3,
     "EN_TRAITEMENT", "infra", ["8.8", "8.9", "8.32"],
     "Exploitation d'une CVE publique avant application du correctif."),
    ("Départ d'un administrateur clé (perte de compétences)", "Équipe d'administration système",
     "Départ, absence prolongée", "Connaissances peu documentées", 3, 3, "REDUIRE", 2, 2,
     "TRAITE", "rh", ["5.37", "6.5", "5.2"],
     "Allongement des délais de reprise en cas d'incident."),
    ("Non-conformité au RGPD / à la loi tunisienne sur les données personnelles", "Données de paie",
     "Contrôle de l'autorité, plainte", "Registre ou AIPD incomplets", 2, 4, "REDUIRE", 1, 3,
     "TRAITE", "dpo", ["5.34", "5.31", "8.10"],
     "Sanctions administratives et atteinte à l'image."),
    ("Dommages financiers suite à une cyberattaque majeure", "Activité de l'entreprise",
     "Cyberattaque", "Coût élevé de remédiation et de notification", 2, 5, "PARTAGER", 2, 3,
     "TRAITE", "dg", ["5.26"],
     "Risque financier résiduel transféré via une police d'assurance cyber (plafond 2 M€)."),
    ("Accès physique non autorisé à l'agence de Sfax", "Agence - Sfax",
     "Intrusion", "Contrôle d'accès par badge non encore déployé", 2, 2, "ACCEPTER", 2, 2,
     "ACCEPTE", "dg", ["7.2"],
     "Risque accepté par la direction jusqu'au déploiement des badges (aucune donnée de production sur site)."),
    ("Stockage de données clients sur des clés USB", "Postes de travail",
     "Fuite de données", "Supports amovibles non maîtrisés", 3, 3, "EVITER", None, None,
     "CLOTURE", "dsi", ["7.10"],
     "Risque supprimé : blocage des supports de stockage USB par stratégie MDM."),
    ("Exfiltration de données sans détection (absence de DLP)", "Données clients",
     "Collaborateur indélicat", "Pas de solution de prévention des fuites", 2, 4, "REDUIRE", None, None,
     "IDENTIFIE", "rssi", ["8.12", "8.16"],
     "Traitement à planifier : sélection d'une solution DLP (budget validé)."),
]

# Plan de traitement (3.7) : (n° du risque, action, mesure, responsable, échéance en jours, statut, avancement,
# ressources, résultat)
RISK_ACTIONS = [
    (1, "Sauvegardes immuables hors ligne de la production", "8.13", "infra", -20, "REALISEE", 100,
     "Stockage objet verrouillé (WORM), 4 000 DT/an", "Restauration complète testée le mois dernier"),
    (1, "EDR sur les serveurs de production et le bastion", "8.7", "infra", 25, "EN_COURS", 60,
     "Licences EDR (60 serveurs), prestataire SOC", None),
    (1, "Exercice de crise rançongiciel avec la direction", "5.26", "rssi", 70, "PREVUE", 0, "Demi-journée, prestataire", None),
    (2, "Tests d'intrusion du cloisonnement multi-tenant", "8.29", "dev", -10, "EN_COURS", 40,
     "Prestataire PASSI, 9 000 DT", "Rapport intermédiaire reçu, 2 vulnérabilités moyennes"),
    (2, "Analyse de code statique dans la chaîne CI", "8.28", "dev", 45, "PREVUE", 0, None, None),
    (4, "Bascule automatique vers une seconde région", "8.14", "infra", 120, "PREVUE", 0,
     "Budget infra +15 %, 2 jours/homme par mois", None),
    (5, "Revue trimestrielle des comptes à privilèges", "5.18", "dsi", -35, "EN_COURS", 50, None,
     "Revue du T3 en retard : extraction des droits à refaire"),
    (6, "Outil d'anonymisation des jeux de recette", "8.33", "dev", 15, "EN_COURS", 70, "Outil open source, 10 j/h", None),
    (9, "Tableau de suivi des correctifs avec délais par criticité", "8.8", "infra", -5, "REALISEE", 100, None,
     "Délai moyen des critiques ramené à 6 jours"),
]

# ---------------------------------------------------------------------------
# Incidents : (titre, catégorie, gravité, statut, J détection, déclarant, responsable,
#              mesure, description, impact, résolution, J clôture)
# ---------------------------------------------------------------------------
INCIDENTS = [
    ("Compromission d'un compte commercial par hameçonnage", "MALVEILLANCE", "MAJEUR", "CLOTURE", -142,
     "Support IT", "rssi", "5.26",
     "Saisie des identifiants sur une fausse page SSO puis acceptation d'une notification MFA frauduleuse.",
     "Accès à la messagerie pendant 40 min ; envoi de 120 courriels frauduleux à des prospects.",
     "Compte bloqué, sessions révoquées, règles de transfert supprimées. Retour d'expérience : MFA avec "
     "correspondance de nombres activé, campagne de sensibilisation ciblée.", -128),
    ("Tentative de rançongiciel bloquée par l'EDR", "MALVEILLANCE", "MINEUR", "CLOTURE", -75,
     "SOC externalisé", "infra", "8.7",
     "Exécution d'une charge malveillante depuis une pièce jointe sur un poste du support.",
     "Aucun chiffrement : processus bloqué et poste isolé automatiquement.",
     "Poste réinstallé, IOC partagés avec tunCERT, règle de filtrage des macros renforcée.", -74),
    ("Perte d'un ordinateur portable dans un taxi", "PERTE_VOL", "MINEUR", "CLOTURE", -51,
     "Collaborateur (ventes)", "dsi", "7.9",
     "Portable professionnel oublié dans un taxi après un rendez-vous client.",
     "Aucun : disque chiffré, effacement à distance déclenché sous 2 h.",
     "Effacement confirmé, poste remplacé, rappel des règles de mobilité.", -50),
    ("Envoi d'un bulletin de paie au mauvais destinataire", "DIVULGATION", "MAJEUR", "RESOLU", -23,
     "Client (service RH)", "dpo", "5.34",
     "Une anomalie de paramétrage a envoyé le bulletin d'un salarié client à un homonyme.",
     "Violation de données personnelles (1 personne). Analyse de notification à l'autorité réalisée.",
     "Correctif déployé, contrôle d'unicité ajouté, notification au client sous 72 h, registre des violations mis à jour.", None),
    ("Dégradation des performances suite à un incident du fournisseur IaaS", "PANNE", "MAJEUR", "CLOTURE", -12,
     "Supervision", "infra", "8.14",
     "Indisponibilité partielle d'une zone de disponibilité du fournisseur pendant 1 h 50.",
     "Temps de réponse dégradés pour 30 % des clients, aucune perte de données.",
     "Bascule automatique sur les autres zones ; demande de rapport d'incident au fournisseur.", -11),
    ("Bucket de stockage de recette exposé publiquement", "ERREUR_HUMAINE", "CRITIQUE", "EN_COURS", -2,
     "Scanner de configuration cloud", "infra", "8.9",
     "Un espace de stockage de recette a été rendu public lors d'un test ; il contient des exports anonymisés à vérifier.",
     "En cours d'évaluation : vérifier l'absence de données personnelles réelles.",
     "", None),
    ("Signalement d'un courriel suspect usurpant la direction", "MALVEILLANCE", "MINEUR", "NOUVEAU", 0,
     "Collaboratrice (comptabilité)", "rssi", "6.8",
     "Demande de virement urgent usurpant l'identité du directeur général (fraude au président).",
     "Aucun virement effectué.", "", None),
]

# ---------------------------------------------------------------------------
# Audits, constats et actions correctives
# ---------------------------------------------------------------------------
AUDITS = [
    {
        "ref": "AUD-{Y}-01", "title": "Audit interne complet du SMSI (clauses 4 à 10 et Annexe A)",
        "scope": SCOPE, "j": -48, "status": "TERMINE", "lead": "audit",
        "summary": "Audit réalisé sur 4 jours, 22 entretiens, échantillonnage des enregistrements des 6 derniers mois. "
                   "Le SMSI est globalement opérationnel et l'engagement de la direction est démontré. "
                   "1 non-conformité majeure, 2 non-conformités mineures, 2 observations et 1 piste d'amélioration.",
        "findings": [
            ("C-01", "NC_MAJEURE", "Revue des droits d'accès non réalisée sur la production",
             "Aucune revue des droits d'accès à la production depuis 9 mois, contrairement à la politique de contrôle d'accès "
             "(revue trimestrielle). 3 comptes de collaborateurs partis restaient actifs sur le bastion.",
             "5.18", "A.5.18", False,
             [("Désactiver les comptes orphelins et réaliser une revue complète des accès à la production.", "dsi", -40, "VERIFIEE", -38),
              ("Automatiser la désactivation des comptes à partir du SIRH (départs).", "infra", 10, "EN_COURS", None),
              ("Planifier les revues trimestrielles dans le calendrier SMSI avec preuve de réalisation.", "rssi", -20, "REALISEE", -21)]),
            ("C-02", "NC_MINEURE", "Plan de reprise d'activité non testé",
             "Le PRA définit un RTO de 4 h mais aucun test de bascule n'a été réalisé ; l'efficacité de la mesure n'est pas démontrée.",
             "5.30", "A.5.30", False,
             [("Réaliser un exercice de bascule complet de la production sur la région secondaire.", "infra", -5, "OUVERTE", None)]),
            ("C-03", "NC_MINEURE", "Évaluation des fournisseurs critiques incomplète",
             "3 fournisseurs critiques sur 12 n'ont pas fait l'objet de l'évaluation sécurité annuelle prévue par la politique fournisseurs.",
             "5.22", "A.5.22", False,
             [("Évaluer les 3 fournisseurs restants (questionnaire + revue des certifications).", "rssi", 15, "EN_COURS", None)]),
            ("C-04", "OBSERVATION", "Indicateurs du SMSI collectés mais peu analysés",
             "Les indicateurs sont produits chaque mois mais leur analyse et les décisions associées ne sont pas tracées (clause 9.1).",
             None, "9.1", False, []),
            ("C-05", "OBSERVATION", "Modélisation des menaces limitée",
             "La modélisation des menaces n'est réalisée que sur 2 modules applicatifs sur 6.",
             "8.25", "A.8.25", False, []),
            ("C-06", "OPPORTUNITE", "Automatiser la collecte des preuves",
             "Une partie des preuves (exports de configuration, rapports de scan) pourrait être collectée automatiquement.",
             None, "10.1", False, []),
        ],
    },
    {
        "ref": "AUD-{Y}-02", "title": "Audit technique de la chaîne CI/CD et du développement sécurisé",
        "scope": "Processus de développement, chaîne d'intégration et de déploiement, gestion des secrets.",
        "j": -6, "status": "EN_COURS", "lead": "audit",
        "summary": "Audit en cours : entretiens réalisés avec l'équipe développement, revue de la CI en cours.",
        "findings": [
            ("C-01", "NC_MINEURE", "Secrets présents dans l'historique d'un dépôt",
             "Deux clés d'API de recette ont été retrouvées dans l'historique Git d'un dépôt interne.",
             "8.4", "A.8.4", False,
             [("Révoquer les clés, purger l'historique et activer la détection de secrets bloquante.", "dev", 7, "EN_COURS", None)]),
        ],
    },
    {
        "ref": "AUD-{Y}-03", "title": "Audit à blanc pré-certification",
        "scope": SCOPE, "j": 30, "status": "PLANIFIE", "lead": "audit",
        "summary": "", "findings": [],
    },
]

# ---------------------------------------------------------------------------
# Revues de direction (clause 9.3)
# ---------------------------------------------------------------------------
REVIEWS = [
    {
        "ref": "RD-{Y}-01", "title": "Revue de direction du SMSI - semestre 1",
        "j": -35, "status": "TENUE",
        "participants": "Nabil Mansour (DG), Leïla Ben Salah (RSSI), Karim Trabelsi (DSI), Sonia Gharbi (DPO), "
                        "Ines Khelifi (RH), Mehdi Chaabane (Développement)",
        "inputs": "a) État des actions des revues précédentes : 7 actions sur 9 soldées.\n"
                  "b) Enjeux externes et internes : croissance de 30 % du portefeuille clients, exigences sécurité "
                  "accrues dans les appels d'offres, évolution du cadre légal sur les données personnelles.\n"
                  "c) Besoins et attentes des parties intéressées : 3 clients grands comptes exigent la certification "
                  "ISO 27001 sous 12 mois.\n"
                  "d) Performance du SMSI : 68 % des mesures applicables implémentées ; 1 NC majeure et 2 NC mineures "
                  "issues de l'audit interne ; taux de clic phishing passé de 18 % à 6 % ; 5 incidents dont 2 majeurs.\n"
                  "e) Retours des parties intéressées : 2 questionnaires sécurité clients traités, aucune réclamation.\n"
                  "f) Résultats de l'appréciation des risques : 15 risques, dont 4 au-dessus du seuil d'acceptation avant traitement.\n"
                  "g) Opportunités d'amélioration : automatisation des preuves, DLP, SOC 24/7.",
        "decisions": "- Objectif confirmé : audit de certification (étape 1) au prochain trimestre.\n"
                     "- Budget sécurité augmenté de 25 % (DLP, SOC externalisé, test d'intrusion).\n"
                     "- Acceptation formelle du risque résiduel « accès physique Sfax » jusqu'au déploiement des badges.\n"
                     "- Maintien du périmètre ; politique de sécurité et objectifs sécurité confirmés sans modification.\n"
                     "- Recrutement d'un ingénieur sécurité supplémentaire validé.",
        "actions": [
            ("Sélectionner et budgéter une solution DLP.", "rssi", 20, "EN_COURS"),
            ("Contractualiser un SOC externalisé 24/7.", "dsi", -10, "REALISEE"),
            ("Recruter un ingénieur sécurité.", "rh", 45, "OUVERTE"),
            ("Mandater l'organisme de certification et fixer les dates d'audit.", "dg", -3, "OUVERTE"),
        ],
    },
    {
        "ref": "RD-{Y}-02", "title": "Revue de direction du SMSI - pré-certification",
        "j": 40, "status": "PLANIFIEE",
        "participants": "Comité de direction, RSSI, DPO",
        "inputs": "", "decisions": "", "actions": [],
    },
]

# ---------------------------------------------------------------------------
# Documents du SMSI : (ref, titre, type, version, statut, propriétaire, J approbation, J prochaine revue, dossier Docs, note)
# ---------------------------------------------------------------------------
DOCUMENTS = [
    ("DOC-001", "Manuel du SMSI (contexte, périmètre, parties intéressées)", "POLITIQUE", "1.2", "APPROUVE", "rssi", -120, 245, "01 Gouvernance", "Clauses 4.1 à 4.4."),
    ("DOC-002", "Politique de sécurité de l'information (PSSI)", "POLITIQUE", "2.1", "APPROUVE", "rssi", -95, 270, "01 Gouvernance", "Approuvée par le directeur général."),
    ("DOC-003", "Objectifs de sécurité et plan de mesure (indicateurs)", "ENREGISTREMENT", "1.1", "APPROUVE", "rssi", -60, 120, "01 Gouvernance", "Clauses 6.2 et 9.1."),
    ("DOC-004", "Méthode d'appréciation et de traitement des risques", "PROCEDURE", "1.0", "APPROUVE", "rssi", -200, -15, "02 Risques", "Revue en retard : à réviser avant l'audit de certification."),
    ("DOC-005", "Déclaration d'applicabilité (DdA)", "ENREGISTREMENT", "1.4", "EN_REVUE", "rssi", None, 20, "03 Déclaration d'applicabilité", "Version 1.4 en revue suite à l'audit interne."),
    ("DOC-006", "Plan de traitement des risques", "ENREGISTREMENT", "1.3", "APPROUVE", "rssi", -35, 150, "02 Risques", "Validé en revue de direction."),
    ("DOC-007", "Politique de contrôle d'accès", "POLITIQUE", "1.2", "APPROUVE", "dsi", -80, 285, "04 Politiques", ""),
    ("DOC-008", "Politique de classification et de manipulation de l'information", "POLITIQUE", "1.0", "APPROUVE", "dpo", -150, 215, "04 Politiques", ""),
    ("DOC-009", "Politique cryptographique", "POLITIQUE", "1.1", "APPROUVE", "infra", -110, 255, "04 Politiques", ""),
    ("DOC-010", "Politique de télétravail et de mobilité", "POLITIQUE", "1.0", "APPROUVE", "dsi", -330, 25, "04 Politiques", "Revue à prévoir dans le mois."),
    ("DOC-011", "Politique de relations avec les fournisseurs", "POLITIQUE", "1.0", "APPROUVE", "rssi", -170, 195, "04 Politiques", ""),
    ("DOC-012", "Procédure de gestion des incidents de sécurité (PR-INC-01)", "PROCEDURE", "2.0", "APPROUVE", "rssi", -90, 275, "05 Procédures", ""),
    ("DOC-013", "Procédure de sauvegarde et de restauration", "PROCEDURE", "1.3", "APPROUVE", "infra", -70, 295, "05 Procédures", ""),
    ("DOC-014", "Plan de continuité et de reprise d'activité (PCA/PRA)", "PROCEDURE", "1.1", "EN_REVUE", "infra", None, 10, "05 Procédures", "Mise à jour suite à la NC C-02 (test de bascule)."),
    ("DOC-015", "Procédure de gestion des changements", "PROCEDURE", "1.2", "APPROUVE", "dsi", -55, 310, "05 Procédures", ""),
    ("DOC-016", "Procédure de gestion des vulnérabilités et des correctifs", "PROCEDURE", "1.0", "BROUILLON", "infra", None, None, "05 Procédures", "Rédaction en cours."),
    ("DOC-017", "Charte d'utilisation des ressources informatiques", "POLITIQUE", "3.0", "APPROUVE", "rh", -140, 225, "04 Politiques", "Signée par 100 % des collaborateurs."),
    ("DOC-018", "Procédure d'audit interne", "PROCEDURE", "1.0", "APPROUVE", "audit", -210, 155, "06 Audit et amélioration", ""),
    ("DOC-019", "Procédure de gestion des non-conformités et actions correctives", "PROCEDURE", "1.0", "APPROUVE", "rssi", -205, 160, "06 Audit et amélioration", ""),
    ("DOC-020", "Ancienne charte informatique v2", "POLITIQUE", "2.0", "OBSOLETE", "rh", -700, None, "04 Politiques", "Remplacée par DOC-017."),
]

# ---------------------------------------------------------------------------
# Preuves : (titre, description, J collecte, responsable, mesures)
# ---------------------------------------------------------------------------
EVIDENCE = [
    ("PSSI signée par le directeur général", "Version 2.1 signée et datée.", -95, "rssi", ["5.1", "5.4"]),
    ("Compte rendu du comité sécurité mensuel", "Dernier comité : suivi des actions et des indicateurs.", -9, "rssi", ["5.2", "5.36"]),
    ("Export de la revue des droits d'accès (production)", "Revue complète réalisée suite à la NC C-01, validée par les responsables.", -38, "dsi", ["5.18", "5.15", "8.2"]),
    ("Configuration MFA de l'annuaire (export)", "MFA obligatoire, correspondance de nombres activée.", -30, "infra", ["5.17", "8.5"]),
    ("Rapport de test de restauration mensuel", "Restauration d'une base client complète en 47 min.", -14, "infra", ["8.13"]),
    ("Rapport du test d'intrusion annuel", "Prestataire indépendant ; 0 critique, 2 élevées, 5 moyennes.", -64, "dev", ["8.29", "8.8"]),
    ("Résultats de la campagne de phishing du trimestre", "Taux de clic 6 % (contre 18 % au premier trimestre), 41 % de signalements.", -20, "rssi", ["6.3", "6.8"]),
    ("Attestations de formation d'intégration sécurité", "100 % des arrivants du semestre formés sous 30 jours.", -25, "rh", ["6.3"]),
    ("Registre des traitements et AIPD de la plateforme", "Registre à jour, AIPD validée par la DPO.", -45, "dpo", ["5.34", "5.31"]),
    ("Certificats ISO 27001 / 27017 du fournisseur IaaS", "Certificats en cours de validité et rapport SOC 2 Type II.", -100, "infra", ["5.23", "5.19"]),
    ("Rapport des scans de vulnérabilités hebdomadaires", "Tendance sur 3 mois, délais de correction par criticité.", -3, "infra", ["8.8"]),
    ("Tableau de bord SIEM - cas d'usage de détection", "Couverture des cas d'usage, alertes du mois.", -7, "infra", ["8.15", "8.16"]),
    ("Procès-verbal du CAB (gestion des changements)", "Échantillon de 10 changements approuvés avec retour arrière prévu.", -5, "dsi", ["8.32"]),
    ("Certificats de destruction des disques", "Destruction de 12 disques de l'ancien serveur de fichiers.", -160, "infra", ["7.14", "7.10"]),
    ("Contrats fournisseurs avec clauses sécurité et DPA", "Échantillon des 9 fournisseurs critiques évalués.", -50, "dpo", ["5.20", "5.22"]),
    ("Rapport de configuration des postes (MDM / EDR)", "100 % des postes chiffrés et protégés par l'EDR.", -10, "dsi", ["8.1", "8.7", "7.9"]),
]

# ---------------------------------------------------------------------------
# Sensibilisation : (titre, type, statut, J, public, participants, taux, notes)
# ---------------------------------------------------------------------------
AWARENESS = [
    ("Module e-learning d'intégration à la sécurité", "FORMATION", "TERMINEE", -150, "Nouveaux arrivants", 26, 100, "Obligatoire sous 30 jours, quiz final (score minimal 80 %)."),
    ("Campagne de phishing simulé - trimestre 1", "CAMPAGNE_PHISHING", "TERMINEE", -200, "Tous les collaborateurs", 176, 82, "Taux de clic 18 %, signalement 12 %."),
    ("Campagne de phishing simulé - trimestre 2", "CAMPAGNE_PHISHING", "TERMINEE", -110, "Tous les collaborateurs", 178, 89, "Taux de clic 11 %, signalement 27 %."),
    ("Campagne de phishing simulé - trimestre 3", "CAMPAGNE_PHISHING", "TERMINEE", -20, "Tous les collaborateurs", 181, 94, "Taux de clic 6 %, signalement 41 %."),
    ("Formation au développement sécurisé (OWASP Top 10)", "FORMATION", "TERMINEE", -60, "Équipe développement", 34, 91, "2 sessions d'une journée, ateliers pratiques."),
    ("Atelier sensibilisation du comité de direction", "ATELIER", "TERMINEE", -90, "Comité de direction", 8, 100, "Scénario de crise rançongiciel, rôles et décisions."),
    ("Lettre d'information sécurité mensuelle", "COMMUNICATION", "EN_COURS", -5, "Tous les collaborateurs", None, None, "Thème du mois : fraude au président."),
    ("Exercice de crise cyber (simulation)", "ATELIER", "PLANIFIEE", 21, "Cellule de crise", 12, None, "Scénario : fuite de données de paie."),
    ("Campagne de phishing simulé - trimestre 4", "CAMPAGNE_PHISHING", "PLANIFIEE", 35, "Tous les collaborateurs", None, None, "Objectif : taux de clic inférieur à 5 %."),
]


# ===========================================================================
# P2 : contexte, objectifs et indicateurs, non-conformités, fournisseurs, exigences
# ===========================================================================
SCOPE_TEXT = {
    "scope_statement": SCOPE,
    "scope_included": "Processus : développement logiciel, exploitation et hébergement de la plateforme, support client, "
                      "gestion des accès, ressources humaines (pour les collaborateurs du périmètre).\n"
                      "Sites : siège de Tunis (Les Berges du Lac), agence de Sfax.\n"
                      "Systèmes : plateforme SaaS, environnements cloud (production, recette, développement), "
                      "postes de travail, outils internes (SSO, messagerie, forge de code, SIEM).",
    "scope_excluded": "Activité de conseil RH (filiale Fictivia Conseil) : entité juridique distincte, sans accès à la "
                      "plateforme ni aux données des clients.\nMesures A.7.6 et A.8.30 exclues (voir la DdA).",
    "scope_interfaces": "Fournisseur IaaS (infrastructure physique et virtualisation, couvert par sa certification "
                        "ISO/IEC 27001) ; SOC externalisé (détection) ; prestataire d'impression des bulletins ; "
                        "clients (paramétrage de leur espace et gestion de leurs utilisateurs).",
}

# (type, catégorie, intitulé, description, effet, prise en compte, n° des risques liés)
ISSUES = [
    ("EXTERNE", "TECHNOLOGIQUE", "Hausse des attaques par rançongiciel visant les éditeurs SaaS",
     "Multiplication des attaques ciblant les fournisseurs pour atteindre leurs clients.",
     "Menace directe sur la disponibilité et la confidentialité des données de paie.",
     "Risque R-0001 traité en priorité ; sauvegardes immuables ; SOC externalisé.", [1, 2]),
    ("EXTERNE", "LEGAL", "Durcissement du cadre de protection des données personnelles",
     "Projet de révision de la loi organique 2004-63 ; exigences RGPD des clients européens.",
     "Obligations renforcées de notification et de sous-traitance.",
     "Registre des exigences tenu par la DPO ; AIPD de la plateforme.", [11]),
    ("EXTERNE", "CONCURRENCE", "Exigence de certification ISO/IEC 27001 dans les appels d'offres",
     "Trois clients grands comptes exigent la certification sous 12 mois.",
     "Enjeu commercial majeur : maintien du chiffre d'affaires.",
     "Objectif OBJ-04 : certification ; calendrier validé en revue de direction.", []),
    ("EXTERNE", "ECONOMIQUE", "Dépendance à un fournisseur IaaS unique",
     "Concentration de la production chez un seul hébergeur, dans une seule région.",
     "Indisponibilité prolongée en cas de défaillance majeure du fournisseur.",
     "Risque R-0004 à accepter ou à traiter (bascule multirégion étudiée).", [4, 7]),
    ("EXTERNE", "SOCIAL", "Pénurie de compétences en cybersécurité",
     "Difficulté à recruter des profils sécurité expérimentés.",
     "Dépendance à quelques personnes clés.",
     "Documentation des procédures ; recrutement validé en revue de direction.", [10]),
    ("INTERNE", "ORGANISATIONNEL", "Croissance rapide des effectifs (+30 % en un an)",
     "Nombreuses arrivées, dont des prestataires.",
     "Risque d'erreurs et de droits d'accès mal maîtrisés.",
     "Intégration sécurité obligatoire ; revue trimestrielle des droits.", [5, 3]),
    ("INTERNE", "TECHNOLOGIQUE", "Dette technique d'un module historique de calcul de paie",
     "Module ancien, faiblement couvert par les tests de sécurité.",
     "Vulnérabilités applicatives plus probables.",
     "Plan de refonte ; analyses SAST renforcées sur ce module.", [2, 9]),
    ("INTERNE", "ORGANISATIONNEL", "Généralisation du travail hybride",
     "60 % des collaborateurs en télétravail au moins deux jours par semaine.",
     "Surface d'attaque élargie (réseaux domestiques, perte de matériel).",
     "Politique de télétravail ; postes chiffrés et gérés ; VPN + MFA.", [8, 3]),
    ("INTERNE", "SOCIAL", "Culture sécurité encore inégale selon les équipes",
     "Bonne maturité en infrastructure, plus faible côté commercial et support.",
     "Vulnérabilité à l'hameçonnage et aux erreurs de manipulation.",
     "Programme de sensibilisation ciblé ; objectif OBJ-01.", [3]),
]

# (nom, catégorie, attentes, retenue, réponse, influence)
PARTIES = [
    ("Clients entreprises (services RH et paie)", "CLIENT",
     "Confidentialité et exactitude des données de paie ; disponibilité de 99,9 % ; notification des incidents sous 24 h ; certification ISO 27001.",
     True, "Engagements contractuels suivis dans le registre des exigences ; objectifs de disponibilité ; certification visée.", 3),
    ("Salariés des clients (personnes concernées)", "CLIENT",
     "Protection de leurs données personnelles et salariales ; exercice de leurs droits.",
     True, "Traitement en sous-traitance pour le compte des clients ; procédure d'exercice des droits.", 2),
    ("INPDP (autorité de protection des données)", "AUTORITE",
     "Respect de la loi organique 2004-63 ; déclarations et notifications.",
     True, "DPO désignée ; registre des traitements ; procédure de notification.", 3),
    ("ANCS (Agence nationale de la cybersécurité)", "AUTORITE",
     "Audit de sécurité obligatoire et périodique ; signalement des incidents.",
     True, "Audit réglementaire planifié ; contacts tunCERT formalisés.", 3),
    ("Fournisseur IaaS", "FOURNISSEUR",
     "Respect de la politique d'usage acceptable et du modèle de responsabilité partagée.",
     True, "Matrice de responsabilité partagée ; configurations conformes aux bonnes pratiques.", 2),
    ("Collaborateurs de Fictivia", "PERSONNEL",
     "Outils fiables, règles claires, protection de leurs données personnelles.",
     True, "Charte informatique ; sensibilisation ; protection des données RH.", 2),
    ("Direction générale et actionnaires", "DIRECTION",
     "Continuité de l'activité, maîtrise des risques, certification à des fins commerciales.",
     True, "Revue de direction semestrielle ; tableau de bord du SMSI.", 3),
    ("Assureur cyber", "ASSUREUR",
     "Mesures minimales : MFA, sauvegardes hors ligne, EDR, plan de réponse aux incidents.",
     True, "Mesures en place et attestées lors du renouvellement annuel.", 2),
    ("Organisme de certification", "PARTENAIRE",
     "Accès aux informations documentées et aux preuves ; respect du calendrier d'audit.",
     True, "Préparation de l'audit à blanc AUD-03 ; exports des registres.", 2),
    ("Concurrents", "AUTRE",
     "Aucune exigence applicable au SMSI.", False, "", 1),
]

# (intitulé, type, source, émetteur, obligation, mise en conformité, statut, n° partie, mesures, revue J)
REQUIREMENTS = [
    ("Protection des données à caractère personnel", "LEGALE", "Loi organique n° 2004-63 du 27 juillet 2004",
     "INPDP", "Licéité des traitements, sécurité des données, déclaration et autorisations préalables.",
     "Registre des traitements ; AIPD de la plateforme ; DPO désignée.", "CONFORME", 3, ["5.34", "5.31"], 160),
    ("Notification des violations de données", "LEGALE", "Loi organique 2004-63 ; RGPD art. 33 (clients UE)",
     "INPDP / clients", "Notifier sans délai indu les violations de données aux responsables de traitement.",
     "Procédure PR-INC-01 : qualification sous 1 h, notification au client sous 24 h.", "CONFORME", 3, ["5.24", "5.26"], 160),
    ("Audit obligatoire et périodique de la sécurité informatique", "LEGALE",
     "Loi n° 2004-5 du 3 février 2004 et décret n° 2004-1250", "ANCS",
     "Faire réaliser un audit de sécurité par un auditeur certifié selon la périodicité réglementaire.",
     "Audit réglementaire à planifier avec un auditeur certifié ANCS.", "PARTIEL", 4, ["5.35"], 45),
    ("Obligations du sous-traitant (clients européens)", "REGLEMENTAIRE", "RGPD art. 28",
     "Clients UE", "Contrat de sous-traitance, instructions documentées, sous-traitants ultérieurs autorisés, assistance.",
     "DPA type annexé aux contrats ; liste des sous-traitants ultérieurs publiée.", "CONFORME", 1, ["5.20", "5.34"], 200),
    ("Hébergement des données dans l'Union européenne", "CONTRACTUELLE", "Contrats-cadres clients, annexe 2",
     "Clients", "Données de production et sauvegardes hébergées exclusivement dans l'UE.",
     "Régions UE uniquement ; contrôle de configuration automatisé.", "CONFORME", 1, ["5.23"], 220),
    ("Disponibilité contractuelle de 99,9 %", "CONTRACTUELLE", "SLA, annexe 3 des contrats",
     "Clients", "Disponibilité mensuelle ≥ 99,9 % hors maintenance planifiée ; pénalités au-delà.",
     "Architecture multizone ; indicateur KPI de disponibilité suivi mensuellement.", "PARTIEL", 1, ["8.14", "5.30"], 90),
    ("Notification des incidents de sécurité sous 24 h", "CONTRACTUELLE", "Annexe sécurité des contrats",
     "Clients", "Informer le client de tout incident l'affectant sous 24 h.",
     "Intégré à la procédure PR-INC-01 (suite à la non-conformité NC-004).", "CONFORME", 1, ["5.24", "5.26"], 120),
    ("Droit d'audit des clients", "CONTRACTUELLE", "Annexe sécurité des contrats",
     "Clients", "Permettre un audit annuel par le client ou un tiers mandaté.",
     "Processus de réponse aux questionnaires ; dossier de preuves prêt.", "CONFORME", 1, ["5.35"], 180),
    ("Certification ISO/IEC 27001 sous 12 mois", "CONTRACTUELLE", "Avenants des trois contrats grands comptes",
     "Clients grands comptes", "Obtenir la certification ISO/IEC 27001 du périmètre de la plateforme.",
     "Audit de certification planifié (objectif OBJ-04).", "PARTIEL", 1, ["5.36"], 60),
    ("Exigences minimales de l'assureur cyber", "CONTRACTUELLE", "Police d'assurance cyber, conditions particulières",
     "Assureur", "MFA généralisée, sauvegardes hors ligne testées, EDR, plan de réponse aux incidents.",
     "Mesures en place ; attestation fournie au renouvellement.", "CONFORME", 8, ["8.5", "8.13", "8.7"], 240),
    ("Conservation des documents de paie", "LEGALE", "Code du travail et législation fiscale",
     "Administration", "Conserver les bulletins et registres de paie pendant la durée légale.",
     "Archivage sécurisé 10 ans ; à confirmer pour les clients hors Tunisie.", "A_EVALUER", 2, ["5.33"], -10),
    ("Conformité aux licences logicielles", "LEGALE", "Code de la propriété intellectuelle ; licences open source",
     "Éditeurs", "Respecter les droits d'usage des logiciels et composants.",
     "Inventaire des licences ; analyse SCA des composants dans la CI.", "CONFORME", None, ["5.32"], 300),
]

# (nom, catégorie, service, criticité, accès, statut, clauses, DPA, certifications, résultat, J dernière éval, J prochaine)
SUPPLIERS = [
    ("Nuvola IaaS (fictif)", "CLOUD", "Hébergement de la production, des sauvegardes et des environnements cloud.",
     "CRITIQUE", "PERSONNEL", "ACTIF", True, True, "ISO/IEC 27001, 27017, 27018 ; SOC 2 Type II", "CONFORME", -100, 265),
    ("IdentiKey SSO (fictif)", "LOGICIEL", "Annuaire, authentification unique et MFA.",
     "CRITIQUE", "CONFIDENTIEL", "ACTIF", True, True, "ISO/IEC 27001", "CONFORME", -150, 215),
    ("Vigil SOC (fictif)", "SECURITE", "Centre opérationnel de sécurité externalisé, 24/7.",
     "CRITIQUE", "CONFIDENTIEL", "ACTIF", True, True, "ISO/IEC 27001 en cours", "RESERVES", -40, 140),
    ("PrintPaie Services (fictif)", "INFOGERANCE", "Impression et mise sous pli des bulletins papier pour certains clients.",
     "CRITIQUE", "PERSONNEL", "ACTIF", True, False, "", "NON_EVALUE", None, None),
    ("CodeForge (fictif)", "LOGICIEL", "Forge de code source, CI/CD.",
     "IMPORTANT", "CONFIDENTIEL", "ACTIF", True, False, "SOC 2 Type II", "CONFORME", -200, 530),
    ("SuiteMail Pro (fictif)", "LOGICIEL", "Messagerie et suite collaborative.",
     "IMPORTANT", "PERSONNEL", "ACTIF", True, True, "ISO/IEC 27001, 27018", "CONFORME", -300, 430),
    ("ShieldEDR (fictif)", "SECURITE", "Protection des postes et serveurs (EDR).",
     "IMPORTANT", "INTERNE", "ACTIF", True, False, "ISO/IEC 27001", "CONFORME", -120, 610),
    ("PentestLab (fictif)", "CONSEIL", "Tests d'intrusion annuels.",
     "IMPORTANT", "CONFIDENTIEL", "ACTIF", False, False, "Auditeurs certifiés", "RESERVES", -64, 300),
    ("TunNet Télécom (fictif)", "TELECOM", "Accès Internet et liaisons des sites.",
     "STANDARD", "AUCUN", "ACTIF", False, False, "", "CONFORME", -400, 700),
    ("EcoShred (fictif)", "AUTRE", "Destruction certifiée des supports et du matériel.",
     "STANDARD", "CONFIDENTIEL", "ACTIF", True, False, "NF EN 15713", "CONFORME", -160, 935),
    ("BackupOld Hosting (fictif)", "CLOUD", "Ancien hébergement des sauvegardes (migré).",
     "IMPORTANT", "PERSONNEL", "TERMINE", True, True, "", "CONFORME", -500, None),
]

# Objectifs : (intitulé, description, actions, ressources, responsable, J échéance, évaluation, statut, indicateurs)
# indicateur : (nom, unité, sens, cible, alerte, fréquence, méthode, responsable, analyste, mesure Annexe A, valeurs anciennes -> récentes)
OBJECTIVES = [
    ("Réduire la vulnérabilité à l'hameçonnage", "Décliné de la PSSI (principe de sensibilisation) et de l'enjeu culture sécurité.",
     "Campagnes trimestrielles, formation ciblée des équipes les plus exposées, bouton de signalement.",
     "Plateforme de simulation (budget annuel validé), 2 jours de formation par an.", "rssi", 70,
     "Résultats des campagnes analysés en comité sécurité ; revue en revue de direction.", "EN_COURS", [
         ("Taux de clic aux campagnes de phishing simulé", "%", "BAISSE", 5, 8, "TRIMESTRIELLE",
          "Rapport de la plateforme de simulation (clics / destinataires).", "rssi", "Comité sécurité", "6.3",
          [18, 11, 6]),
         ("Taux de signalement des campagnes", "%", "HAUSSE", 50, 35, "TRIMESTRIELLE",
          "Signalements via le bouton dédié / destinataires.", "rssi", "Comité sécurité", "6.8", [12, 27, 41]),
     ]),
    ("Garantir une disponibilité de la plateforme ≥ 99,9 %", "Engagement contractuel (SLA) et enjeu de dépendance à l'IaaS.",
     "Architecture multizone, supervision, tests de bascule PRA.", "Équipe infrastructure ; budget cloud.", "infra", 300,
     "Disponibilité mensuelle mesurée par la supervision externe.", "EN_COURS", [
         ("Disponibilité mensuelle de la plateforme", "%", "HAUSSE", 99.9, 99.5, "MENSUELLE",
          "Sondes de supervision externes, hors maintenance planifiée.", "infra", "DSI", "8.14",
          [99.97, 99.95, 99.99, 99.93, 99.82, 99.96, 99.98, 99.94, 99.97, 99.99, 99.95, 99.87]),
         ("Tests de restauration réussis", "%", "HAUSSE", 100, 90, "MENSUELLE",
          "Restaurations mensuelles réussies / tentées.", "infra", "DSI", "8.13", [100, 100, 80, 100, 100, 100]),
     ]),
    ("Maîtriser les vulnérabilités techniques", "Décliné du risque R-0009 et de l'enjeu dette technique.",
     "Scans hebdomadaires, correctifs prioritaires, retest après test d'intrusion.", "0,5 ETP sécurité ; outil de scan.",
     "infra", 120, "Délais de correction par criticité, analysés mensuellement.", "EN_COURS", [
         ("Vulnérabilités critiques corrigées sous 15 jours", "%", "HAUSSE", 100, 90, "MENSUELLE",
          "Tickets de correction (date de détection -> date de correction).", "infra", "Comité sécurité", "8.8",
          [75, 80, 85, 92, 88, 100, 95, 80]),
         ("Délai moyen de correction des vulnérabilités critiques", "j", "BAISSE", 15, 20, "MENSUELLE",
          "Moyenne des délais de correction du mois.", "infra", "Comité sécurité", "8.8", [24, 22, 19, 17, 14, 16, 13, 21]),
     ]),
    ("Obtenir la certification ISO/IEC 27001", "Exigence contractuelle de trois clients grands comptes.",
     "Mise en œuvre des mesures de la DdA, audit interne, audit à blanc, audit de certification.",
     "Accompagnement externe ; budget de certification validé.", "dg", 75,
     "Taux de mise en œuvre de la DdA et résultat des audits.", "EN_COURS", [
         ("Mesures applicables implémentées", "%", "HAUSSE", 95, 80, "MENSUELLE",
          "Déclaration d'applicabilité (statut Implémenté / mesures applicables).", "rssi", "Revue de direction", "5.36",
          [48, 52, 58, 63, 68, 72, 75, 77]),
         ("Revues des droits d'accès réalisées dans les délais", "%", "HAUSSE", 100, 90, "TRIMESTRIELLE",
          "Revues réalisées / revues planifiées.", "dsi", "RSSI", "5.18", [0, 50, 100]),
     ]),
]

# Indicateurs de surveillance sans objectif rattaché
SURVEILLANCE = [
    ("Incidents de sécurité majeurs ou critiques", "nb", "BAISSE", 0, 1, "MENSUELLE",
     "Incidents de gravité majeure ou critique déclarés dans le mois.", "rssi", "Comité sécurité", "5.26",
     [0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1]),
    ("Collaborateurs à jour de la formation sécurité", "%", "HAUSSE", 100, 90, "TRIMESTRIELLE",
     "Collaborateurs ayant suivi le module annuel / effectif.", "rh", "RSSI", "6.3", [78, 85, 92, 96]),
]

# Non-conformités : (intitulé, source, gravité, statut, J détection, détecteur, lien, description, correction,
#                    méthode, cause, étendue, modifications SMSI, actions [(desc, resp, J échéance, statut)], efficacité)
NONCONFORMITIES = [
    ("Revue des droits d'accès à la production non réalisée", "AUDIT_INTERNE", "MAJEURE", "A_VERIFIER", -48,
     "Amel Jaziri (audit interne)", ("finding", "AUD-{Y}-01", "C-01"),
     "Aucune revue des accès à la production depuis 9 mois ; 3 comptes de collaborateurs partis encore actifs sur le bastion.",
     "Comptes orphelins désactivés le jour même ; revue complète des accès réalisée.",
     "5 pourquoi",
     "La revue reposait sur une action manuelle sans rappel ni responsable désigné ; le processus de départ RH ne "
     "déclenchait pas la désactivation des comptes techniques.",
     "Même faiblesse possible sur la forge de code et l'outil de supervision : revus dans la même campagne.",
     "Procédure de gestion des accès mise à jour ; indicateur « revues dans les délais » créé.",
     [("Désactiver automatiquement les comptes à partir des départs du SIRH.", "infra", -10, "REALISEE"),
      ("Planifier les revues trimestrielles avec rappel et preuve de réalisation.", "rssi", -20, "REALISEE")], None),
    ("Bulletin de paie transmis à un mauvais destinataire", "INCIDENT", "MAJEURE", "EN_TRAITEMENT", -23,
     "Client (service RH)", ("incident", "INC-{Y}-0004"),
     "Une anomalie de paramétrage des homonymes a conduit à l'envoi d'un bulletin à un autre salarié.",
     "Correctif déployé, client notifié sous 24 h, registre des violations mis à jour.",
     "Ishikawa (5M)",
     "Absence de contrôle d'unicité sur l'adresse de diffusion ; cas des homonymes non couvert par les tests.",
     "Autres envois de documents (attestations, relevés annuels) potentiellement concernés.",
     "",
     [("Ajouter un contrôle d'unicité sur toutes les diffusions de documents.", "dev", -5, "REALISEE"),
      ("Ajouter des cas de test « homonymes » à la recette de non-régression.", "dev", 12, "EN_COURS")], None),
    ("Délai de correction des vulnérabilités critiques non tenu", "SURVEILLANCE", "MINEURE", "OUVERTE", -3,
     "Indicateur KPI de délai de correction", None,
     "Dernière mesure : 21 jours en moyenne pour une cible de 15 jours.", "", None, "", "", "", [], None),
    ("Délai de notification contractuel non intégré à la procédure d'incident", "RECLAMATION", "MINEURE", "CLOTUREE", -130,
     "Client grand compte (questionnaire sécurité)", None,
     "La procédure PR-INC-01 ne reprenait pas l'engagement contractuel de notification sous 24 h.",
     "Engagement rappelé à l'équipe d'astreinte.",
     "5 pourquoi",
     "Les exigences contractuelles n'étaient pas recensées dans un registre consulté lors des mises à jour de procédures.",
     "Autres engagements contractuels (droit d'audit, localisation des données) vérifiés : intégrés.",
     "Création du registre des exigences légales et contractuelles ; revue annuelle des procédures au regard du registre.",
     [("Intégrer la notification sous 24 h dans la procédure PR-INC-01.", "rssi", -100, "VERIFIEE"),
      ("Créer le registre des exigences contractuelles.", "dpo", -95, "VERIFIEE")],
     ("Exercice d'incident du mois suivant : notification simulée envoyée en 6 h ; registre utilisé lors de 2 mises à jour de procédures.", "audit", -60)),
    ("Indicateurs du SMSI collectés mais non analysés", "REVUE_DIRECTION", "MINEURE", "EN_TRAITEMENT", -35,
     "Revue de direction RD-{Y}-01", None,
     "Les indicateurs sont produits chaque mois sans analyse ni décision tracée (9.1).",
     "", "5 pourquoi",
     "Pas de rituel d'analyse défini ; responsable de l'analyse non désigné.",
     "", "Ajout d'un point « indicateurs » à l'ordre du jour du comité sécurité.",
     [("Désigner un analyste pour chaque indicateur et tracer l'analyse à chaque mesure.", "rssi", 15, "EN_COURS")], None),
]


# ===========================================================================
# P3 : programme d'audit, compétences, continuité, changements, actifs <-> risques
# ===========================================================================
# (décalage d'année, domaine, trimestre, auditeur, audit réalisé "AUD-{Y}-0n" ou None, note)
AUDIT_PROGRAMME = [
    (0, "C4", 2, "audit", "AUD-{Y}-01", ""), (0, "C5", 2, "audit", "AUD-{Y}-01", ""),
    (0, "C6", 2, "audit", "AUD-{Y}-01", ""), (0, "C7", 2, "audit", "AUD-{Y}-01", ""),
    (0, "C8", 2, "audit", "AUD-{Y}-01", ""), (0, "C9", 2, "audit", "AUD-{Y}-01", ""),
    (0, "C10", 2, "audit", "AUD-{Y}-01", ""), (0, "A5", 2, "audit", "AUD-{Y}-01", ""),
    (0, "A6", 2, "audit", "AUD-{Y}-01", ""), (0, "A8", 4, "audit", "AUD-{Y}-02", "Audit technique CI/CD"),
    (1, "C9", 1, "audit", None, "Audit à blanc pré-certification"), (1, "C10", 1, "audit", None, ""),
    (1, "A5", 2, "rssi", None, "Auditeur à revoir : responsable de mesures A.5"),
    (1, "A7", 2, "audit", None, "Sites de Tunis et Sfax"), (1, "A8", 3, "audit", None, "Avec prestataire externe"),
    (2, "C4", 2, "audit", None, ""), (2, "C5", 2, "audit", None, ""), (2, "C6", 2, "audit", None, ""),
    (2, "C7", 2, "audit", None, ""), (2, "C8", 2, "audit", None, ""), (2, "A6", 3, "audit", None, ""),
]

# Compétences requises : (intitulé, description, validité en mois, personnes)
COMPETENCES = [
    ("Sensibilisation annuelle à la sécurité", "Module d'e-learning annuel et quiz (score ≥ 80 %).", 12,
     ["rssi", "dg", "dsi", "infra", "dev", "dpo", "rh", "audit"]),
    ("Développement sécurisé (OWASP Top 10)", "Formation pratique aux vulnérabilités applicatives.", 24, ["dev", "dsi"]),
    ("Audit interne ISO/IEC 27001", "Certification Lead Auditor ou formation d'auditeur interne équivalente.", None, ["audit"]),
    ("Gestion des incidents et investigation", "Réponse aux incidents, recueil de preuves (A.5.26, A.5.28).", 36, ["rssi", "infra"]),
    ("Administration cloud sécurisée", "Certification sécurité du fournisseur IaaS.", 36, ["infra"]),
    ("Protection des données personnelles", "Formation DPO certifiante.", None, ["dpo"]),
]
# Preuves : (personne, n° de compétence ou None, intitulé, type, organisme, J obtention, J expiration ou None)
COMPETENCE_RECORDS = [
    ("rssi", 1, "E-learning sécurité annuel", "FORMATION", "Plateforme interne", -40, None),
    ("dg", 1, "E-learning sécurité annuel", "FORMATION", "Plateforme interne", -55, None),
    ("dsi", 1, "E-learning sécurité annuel", "FORMATION", "Plateforme interne", -70, None),
    ("infra", 1, "E-learning sécurité annuel", "FORMATION", "Plateforme interne", -30, None),
    ("dev", 1, "E-learning sécurité annuel", "FORMATION", "Plateforme interne", -100, None),
    ("dpo", 1, "E-learning sécurité annuel", "FORMATION", "Plateforme interne", -20, None),
    ("rh", 1, "E-learning sécurité annuel", "FORMATION", "Plateforme interne", -380, None),
    ("audit", 1, "E-learning sécurité annuel", "FORMATION", "Plateforme interne", -15, None),
    ("dev", 2, "Formation OWASP Top 10 (2 jours)", "FORMATION", "Organisme de formation agréé", -60, None),
    ("audit", 3, "ISO/IEC 27001 Lead Auditor", "CERTIFICATION", "Organisme de certification de personnes", -500, None),
    ("rssi", 4, "Gestion de crise cyber et réponse aux incidents", "FORMATION", "Organisme de formation agréé", -1200, None),
    ("infra", 4, "Réponse aux incidents (atelier tunCERT)", "FORMATION", "tunCERT", -200, None),
    ("infra", 5, "Certification sécurité cloud du fournisseur", "CERTIFICATION", "Fournisseur IaaS", -1050, 40),
    ("dpo", 6, "Certification DPO", "CERTIFICATION", "Organisme de certification de personnes", -700, None),
    ("rssi", None, "ISO/IEC 27001 Lead Implementer", "CERTIFICATION", "Organisme de certification de personnes", -900, None),
]

# Activités (BIA) : (nom, description, responsable, criticité, impacts, DMIA, RTO, RPO, dépendances, stratégie, n° d'actifs, plan)
PROCESSES = [
    ("Calcul et diffusion de la paie", "Traitement mensuel des paies des 240 clients.", "dev", 4,
     "4 h : appels clients ; 24 h : pénalités SLA ; 48 h : paies en retard, impact légal et image.",
     48, 8, 1, "Plateforme SaaS, base de production, fournisseur IaaS, équipe développement.",
     "Bascule multizone automatique ; restauration depuis sauvegarde immuable ; calcul de secours sur la paie du mois précédent.",
     [1, 2, 3], "DOC-014"),
    ("Accès des clients à la plateforme", "Connexion, consultation et paramétrage par les clients.", "infra", 4,
     "2 h : réclamations ; 24 h : rupture SLA et pénalités.", 24, 4, 1,
     "SSO, plateforme, fournisseur IaaS, opérateur télécom.", "Architecture multizone, CDN, page de statut.", [1, 5], "DOC-014"),
    ("Support client", "Assistance de niveau 1 et 2 par téléphone et ticket.", "dsi", 3,
     "4 h : dégradation de la satisfaction ; 24 h : clients bloqués sans assistance.", 24, 4, 4,
     "Outil de ticketing SaaS, téléphonie, équipe support (Sfax).", "Bascule de l'équipe entre Tunis et Sfax ; télétravail.",
     [6], None),
    ("Développement et livraison", "Développement, tests et mise en production.", "dev", 2,
     "Retard des évolutions ; correctifs de sécurité bloqués au-delà de 5 jours.", 120, 48, 24,
     "Forge de code, CI/CD, équipe développement.", "Reconstruction de la CI par Infrastructure as Code.", [4, 14], None),
    ("Paie et RH internes", "Gestion du personnel de Fictivia.", "rh", 2,
     "Retard de paie interne au-delà de 7 jours.", 168, 72, 24, "SIRH SaaS.", "Saisie manuelle de secours.", [7], None),
    ("Facturation des abonnements", "Émission des factures mensuelles.", "dg", 1,
     "Décalage de trésorerie au-delà de 2 jours.", 48, 72, 24, "ERP SaaS.", "Facturation reportée.", [8], None),
]
# Exercices : (intitulé, type, J date, objectifs, résultat, RTO atteint, constats, n° d'activités, pilote)
CONTINUITY_TESTS = [
    ("Restauration complète d'une base client", "RESTAURATION", -14,
     "Restaurer la base d'un client depuis la sauvegarde immuable et vérifier l'intégrité.", "REUSSI", 0.8,
     "Restauration en 47 min, intégrité vérifiée par contrôle des sommes.", [1], "infra"),
    ("Exercice sur table : rançongiciel sur la production", "TABLE_TOP", -90,
     "Dérouler la cellule de crise, les décisions et la communication client.", "PARTIEL", None,
     "Rôles clairs ; modèle de communication client absent ; contacts de l'assureur à mettre à jour.", [1, 2], "rssi"),
    ("Bascule de la production sur la région secondaire", "BASCULE", 30,
     "Démontrer le RTO de 4 h du PRA (non-conformité C-02).", "PLANIFIE", None, "", [1, 2], "infra"),
    ("Test de bascule de zone de disponibilité", "TECHNIQUE", -420,
     "Couper une zone et vérifier la continuité du service.", "REUSSI", 0.2,
     "Bascule transparente en 12 min.", [2], "infra"),
]

# Changements : (intitulé, type, risque, urgent, demandeur, statut, approbateur, J prévu, description,
#                justification, impact, retour arrière, note de décision, revue, n° d'actifs)
CHANGES = [
    ("Migration de l'intégration continue vers des agents éphémères", "TECHNIQUE", "MOYEN", False, "dev", "REALISE", "rssi", -8,
     "Remplacer le serveur de CI permanent par des agents créés à chaque exécution.",
     "Réduire la surface d'attaque et les secrets persistants (constat C-01 de l'audit AUD-02).",
     "Amélioration de la confidentialité des secrets ; risque d'interruption des déploiements pendant la migration.",
     "Conserver l'ancien serveur en veille pendant 2 semaines.", "Approuvé : fenêtre hors période de paie.", "", [14]),
    ("Activation de la MFA avec correspondance de nombres", "TECHNIQUE", "FAIBLE", False, "infra", "CLOTURE", "rssi", -130,
     "Activer la correspondance de nombres sur l'annuaire.", "Retour d'expérience de l'incident INC-0001 (fatigue MFA).",
     "Réduit le risque de compromission de compte ; gêne utilisateur limitée.", "Désactivation de l'option dans la console.",
     "", "Aucun incident ; 2 appels au support la première semaine.", [5]),
    ("Ajout d'une région secondaire pour la production", "TECHNIQUE", "ELEVE", False, "infra", "DEMANDE", None, 25,
     "Répliquer la production dans une seconde région UE.", "Traiter le risque R-0004 (dépendance à une région).",
     "Disponibilité améliorée ; nouveaux flux de réplication à chiffrer ; coût supplémentaire.",
     "Désactivation de la réplication, retour à la région unique.", "", "", [1, 2, 3]),
    ("Révision de la PSSI : objectifs de sécurité mesurables", "SMSI", "FAIBLE", False, "rssi", "CLOTURE", "rssi", -100,
     "Ajouter des objectifs mesurables et leurs indicateurs à la PSSI.", "Exigence 6.2 ; préparation de la certification.",
     "Aucun impact technique ; communication à prévoir à tout le personnel.", "", "",
     "PSSI v2.1 approuvée et diffusée ; indicateurs suivis depuis.", []),
    ("Nouveau prestataire d'impression des bulletins", "ORGANISATIONNEL", "MOYEN", False, "dsi", "REFUSE", "rssi", -20,
     "Confier l'impression des bulletins papier à PrintPaie Services.", "Réduction des coûts.",
     "Transfert de données personnelles de paie à un sous-traitant.", "",
     "Refusé tant que l'accord de traitement des données (DPA) n'est pas signé.", "", []),
    ("Correctif urgent d'une bibliothèque vulnérable", "TECHNIQUE", "ELEVE", True, "dev", "CLOTURE", "rssi", -45,
     "Mise à jour d'une bibliothèque de sérialisation (vulnérabilité critique publiée).",
     "Vulnérabilité exploitable à distance.", "Correction d'une faille critique ; risque de régression applicative.",
     "Redéploiement de la version précédente.", "Approuvé en urgence.", "Aucune régression ; scan de vulnérabilités propre.", [1]),
]

# Actifs touchés par les risques : n° de risque -> n° d'actifs (ordre de ASSETS)
RISK_ASSETS = {1: [1, 2, 3], 2: [1, 2], 3: [5, 6], 4: [1, 2], 5: [10, 2], 6: [4], 8: [12], 9: [1, 14],
               10: [15], 11: [2], 13: [17], 14: [12], 15: [2]}


# Maillage SMI (3.8) : n° du risque -> éléments liés (type, n° de l'élément dans sa liste)
RISK_LINKS = {
    1: [("Incident", 2), ("Supplier", 7), ("BusinessProcess", 2)],
    2: [("Incident", 4), ("BusinessProcess", 1)],
    3: [("Incident", 1), ("Incident", 7), ("ChangeRequest", 2)],
    4: [("Incident", 5), ("Supplier", 1), ("ChangeRequest", 3), ("BusinessProcess", 2)],
    7: [("Supplier", 4), ("Supplier", 5), ("ChangeRequest", 5)],
    8: [("Incident", 3)],
    9: [("ChangeRequest", 6)],
}
# risque dont la réévaluation est demandée (incident lié récemment)
RISK_REASSESS = (6, ("Incident", 6))

# Acceptation des politiques (3.10) : document -> (rôles concernés, délai en jours, comptes ayant accepté)
POLICY_ACKS = {
    "DOC-002": ("", 30, ["rssi", "dg", "dsi", "infra", "dev", "rh", "dpo"]),      # PSSI : tous
    "DOC-007": ("", 30, ["rssi", "dsi", "infra"]),                              # contrôle d'accès
    "DOC-010": ("", 45, ["rssi", "dg", "rh"]),                                  # télétravail
    "DOC-009": ("RSSI,CONTRIBUTEUR", 30, ["rssi", "infra", "dev"]),             # cryptographie : équipes techniques
}

