"""Catalogues des référentiels autres que l'ISO 27001 (références + intitulés courts
reformulés ; le texte normatif reste dans les normes, que l'organisation doit posséder).

Chaque catalogue : liste de (groupe, [(référence, intitulé), ...]).
Les correspondances (MAPPINGS) sont des propositions : partielles, à valider par
l'organisation, jamais appliquées automatiquement.
"""

# ---------------------------------------------------------------------------
# ISO/IEC 42001:2023 - Système de management de l'intelligence artificielle
# Annexe A (38 mesures)
# ---------------------------------------------------------------------------
ISO42001 = [
    ("A.2 Politiques relatives à l'IA", [
        ("A.2.2", "Politique en matière d'IA"),
        ("A.2.3", "Alignement avec les autres politiques de l'organisation"),
        ("A.2.4", "Revue de la politique en matière d'IA"),
    ]),
    ("A.3 Organisation interne", [
        ("A.3.2", "Rôles et responsabilités liés à l'IA"),
        ("A.3.3", "Signalement des préoccupations"),
    ]),
    ("A.4 Ressources des systèmes d'IA", [
        ("A.4.2", "Documentation des ressources"),
        ("A.4.3", "Ressources en données"),
        ("A.4.4", "Ressources en outils"),
        ("A.4.5", "Ressources système et de calcul"),
        ("A.4.6", "Ressources humaines"),
    ]),
    ("A.5 Évaluation des impacts des systèmes d'IA", [
        ("A.5.2", "Processus d'évaluation d'impact des systèmes d'IA"),
        ("A.5.3", "Documentation des évaluations d'impact"),
        ("A.5.4", "Impact sur les individus ou groupes d'individus"),
        ("A.5.5", "Impacts sociétaux des systèmes d'IA"),
    ]),
    ("A.6 Cycle de vie des systèmes d'IA", [
        ("A.6.1.2", "Objectifs de développement responsable"),
        ("A.6.1.3", "Processus de conception et de développement responsables"),
        ("A.6.2.2", "Exigences et spécification du système d'IA"),
        ("A.6.2.3", "Documentation de la conception et du développement"),
        ("A.6.2.4", "Vérification et validation"),
        ("A.6.2.5", "Déploiement"),
        ("A.6.2.6", "Exploitation et surveillance"),
        ("A.6.2.7", "Documentation technique"),
        ("A.6.2.8", "Enregistrement des journaux d'événements"),
    ]),
    ("A.7 Données des systèmes d'IA", [
        ("A.7.2", "Données pour le développement et l'amélioration"),
        ("A.7.3", "Acquisition des données"),
        ("A.7.4", "Qualité des données"),
        ("A.7.5", "Provenance des données"),
        ("A.7.6", "Préparation des données"),
    ]),
    ("A.8 Informations pour les parties intéressées", [
        ("A.8.2", "Documentation et informations pour les utilisateurs"),
        ("A.8.3", "Rapports externes"),
        ("A.8.4", "Communication des incidents"),
        ("A.8.5", "Informations pour les parties intéressées"),
    ]),
    ("A.9 Utilisation des systèmes d'IA", [
        ("A.9.2", "Processus d'utilisation responsable"),
        ("A.9.3", "Objectifs d'utilisation responsable"),
        ("A.9.4", "Utilisation prévue du système d'IA"),
    ]),
    ("A.10 Relations avec les tiers et les clients", [
        ("A.10.2", "Répartition des responsabilités"),
        ("A.10.3", "Fournisseurs"),
        ("A.10.4", "Clients"),
    ]),
]

# ---------------------------------------------------------------------------
# ISO/IEC 27701:2019 - Système de management de la protection de la vie privée
# Annexe A (responsable de traitement, 31) et Annexe B (sous-traitant, 18)
# ---------------------------------------------------------------------------
ISO27701 = [
    ("A.7.2 Collecte et traitement (responsable)", [
        ("A.7.2.1", "Identifier et documenter la finalité"),
        ("A.7.2.2", "Identifier la base juridique"),
        ("A.7.2.3", "Déterminer quand et comment obtenir le consentement"),
        ("A.7.2.4", "Obtenir et enregistrer le consentement"),
        ("A.7.2.5", "Analyse d'impact relative à la vie privée"),
        ("A.7.2.6", "Contrats avec les sous-traitants"),
        ("A.7.2.7", "Responsable conjoint du traitement"),
        ("A.7.2.8", "Enregistrements relatifs au traitement"),
    ]),
    ("A.7.3 Obligations envers les personnes (responsable)", [
        ("A.7.3.1", "Déterminer et remplir les obligations envers les personnes"),
        ("A.7.3.2", "Déterminer les informations destinées aux personnes"),
        ("A.7.3.3", "Fournir les informations aux personnes"),
        ("A.7.3.4", "Permettre de modifier ou retirer le consentement"),
        ("A.7.3.5", "Permettre de s'opposer au traitement"),
        ("A.7.3.6", "Accès, rectification et effacement"),
        ("A.7.3.7", "Informer les tiers des modifications"),
        ("A.7.3.8", "Fournir une copie des données traitées"),
        ("A.7.3.9", "Traitement des demandes"),
        ("A.7.3.10", "Prise de décision automatisée"),
    ]),
    ("A.7.4 Vie privée dès la conception et par défaut (responsable)", [
        ("A.7.4.1", "Limiter la collecte"),
        ("A.7.4.2", "Limiter le traitement"),
        ("A.7.4.3", "Exactitude et qualité"),
        ("A.7.4.4", "Objectifs de minimisation"),
        ("A.7.4.5", "Désidentification et suppression en fin de traitement"),
        ("A.7.4.6", "Fichiers temporaires"),
        ("A.7.4.7", "Conservation"),
        ("A.7.4.8", "Élimination"),
        ("A.7.4.9", "Contrôles de transmission"),
    ]),
    ("A.7.5 Partage, transfert et divulgation (responsable)", [
        ("A.7.5.1", "Base des transferts entre juridictions"),
        ("A.7.5.2", "Pays et organisations destinataires des transferts"),
        ("A.7.5.3", "Enregistrements des transferts"),
        ("A.7.5.4", "Enregistrements des divulgations à des tiers"),
    ]),
    ("B.8.2 Collecte et traitement (sous-traitant)", [
        ("B.8.2.1", "Accord avec le client"),
        ("B.8.2.2", "Finalités propres de l'organisation"),
        ("B.8.2.3", "Utilisation à des fins de marketing et de publicité"),
        ("B.8.2.4", "Instruction contraire à la réglementation"),
        ("B.8.2.5", "Obligations du client"),
        ("B.8.2.6", "Enregistrements relatifs au traitement"),
    ]),
    ("B.8.3 Obligations envers les personnes (sous-traitant)", [
        ("B.8.3.1", "Obligations envers les personnes concernées"),
    ]),
    ("B.8.4 Vie privée dès la conception et par défaut (sous-traitant)", [
        ("B.8.4.1", "Fichiers temporaires"),
        ("B.8.4.2", "Restitution, transfert ou élimination des données"),
        ("B.8.4.3", "Contrôles de transmission"),
    ]),
    ("B.8.5 Partage, transfert et divulgation (sous-traitant)", [
        ("B.8.5.1", "Base des transferts entre juridictions"),
        ("B.8.5.2", "Pays et organisations destinataires des transferts"),
        ("B.8.5.3", "Enregistrements des divulgations à des tiers"),
        ("B.8.5.4", "Notification des demandes de divulgation"),
        ("B.8.5.5", "Divulgations juridiquement contraignantes"),
        ("B.8.5.6", "Communication des sous-traitants ultérieurs"),
        ("B.8.5.7", "Recours à un sous-traitant ultérieur"),
        ("B.8.5.8", "Changement de sous-traitant ultérieur"),
    ]),
]

# ---------------------------------------------------------------------------
# Correspondances proposées vers l'ISO/IEC 27001:2022 (Annexe A, références sans « A. »)
# (code source, réf. source, code cible, réf. cible) - relation « partielle »
# ---------------------------------------------------------------------------
MAPPINGS = [
    # ISO 42001 -> ISO 27001
    ("ISO42001", "A.2.2", "ISO27001", "5.1"),
    ("ISO42001", "A.2.4", "ISO27001", "5.1"),
    ("ISO42001", "A.3.2", "ISO27001", "5.2"),
    ("ISO42001", "A.3.3", "ISO27001", "6.8"),
    ("ISO42001", "A.4.2", "ISO27001", "5.9"),
    ("ISO42001", "A.4.6", "ISO27001", "6.3"),
    ("ISO42001", "A.6.1.3", "ISO27001", "8.25"),
    ("ISO42001", "A.6.2.2", "ISO27001", "8.26"),
    ("ISO42001", "A.6.2.4", "ISO27001", "8.29"),
    ("ISO42001", "A.6.2.5", "ISO27001", "8.32"),
    ("ISO42001", "A.6.2.6", "ISO27001", "8.16"),
    ("ISO42001", "A.6.2.7", "ISO27001", "5.37"),
    ("ISO42001", "A.6.2.8", "ISO27001", "8.15"),
    ("ISO42001", "A.8.2", "ISO27001", "5.37"),
    ("ISO42001", "A.8.4", "ISO27001", "5.24"),
    ("ISO42001", "A.8.4", "ISO27001", "5.26"),
    ("ISO42001", "A.10.2", "ISO27001", "5.20"),
    ("ISO42001", "A.10.3", "ISO27001", "5.19"),
    ("ISO42001", "A.10.3", "ISO27001", "5.21"),
    # ISO 27701 -> ISO 27001
    ("ISO27701", "A.7.2.5", "ISO27001", "5.34"),
    ("ISO27701", "A.7.2.6", "ISO27001", "5.20"),
    ("ISO27701", "A.7.2.8", "ISO27001", "5.34"),
    ("ISO27701", "A.7.3.1", "ISO27001", "5.34"),
    ("ISO27701", "A.7.3.9", "ISO27001", "5.34"),
    ("ISO27701", "A.7.4.5", "ISO27001", "8.11"),
    ("ISO27701", "A.7.4.6", "ISO27001", "8.10"),
    ("ISO27701", "A.7.4.7", "ISO27001", "5.33"),
    ("ISO27701", "A.7.4.8", "ISO27001", "7.14"),
    ("ISO27701", "A.7.4.8", "ISO27001", "8.10"),
    ("ISO27701", "A.7.4.9", "ISO27001", "5.14"),
    ("ISO27701", "A.7.4.9", "ISO27001", "8.24"),
    ("ISO27701", "A.7.5.1", "ISO27001", "5.14"),
    ("ISO27701", "A.7.5.3", "ISO27001", "5.14"),
    ("ISO27701", "B.8.2.1", "ISO27001", "5.20"),
    ("ISO27701", "B.8.4.1", "ISO27001", "8.10"),
    ("ISO27701", "B.8.4.2", "ISO27001", "8.10"),
    ("ISO27701", "B.8.4.3", "ISO27001", "8.24"),
    ("ISO27701", "B.8.5.1", "ISO27001", "5.14"),
    ("ISO27701", "B.8.5.4", "ISO27001", "5.34"),
    ("ISO27701", "B.8.5.6", "ISO27001", "5.21"),
    ("ISO27701", "B.8.5.7", "ISO27001", "5.21"),
    ("ISO27701", "B.8.5.8", "ISO27001", "5.21"),
    # ISO 42001 <-> ISO 27701 (données personnelles dans les systèmes d'IA)
    ("ISO42001", "A.7.3", "ISO27701", "A.7.2.2"),
    ("ISO42001", "A.5.4", "ISO27701", "A.7.2.5"),
    ("ISO42001", "A.9.4", "ISO27701", "A.7.3.10"),
]


# ---------------------------------------------------------------------------
# Référentiels « exigences » (pas d'annexe de mesures) : chapitres 4 à 10.
# Références = numéros de chapitre ; intitulés courts reformulés.
# ---------------------------------------------------------------------------
_HLS_GROUPS = {"4": "4 Contexte de l'organisation", "5": "5 Leadership", "6": "6 Planification", "7": "7 Support",
               "8": "8 Fonctionnement", "9": "9 Évaluation des performances", "10": "10 Amélioration"}


def _by_chapter(items):
    groups = {}
    for ref, title in items:
        groups.setdefault(_HLS_GROUPS[ref.split(".")[0]], []).append((ref, title))
    return list(groups.items())


# ISO 22301:2019 - Système de management de la continuité d'activité
ISO22301 = _by_chapter([
    ("4.1", "Compréhension de l'organisation et de son contexte"),
    ("4.2.1", "Besoins et attentes des parties intéressées"),
    ("4.2.2", "Exigences légales et réglementaires"),
    ("4.3.1", "Domaine d'application du SMCA : généralités"),
    ("4.3.2", "Domaine d'application du SMCA : périmètre et exclusions"),
    ("4.4", "Système de management de la continuité d'activité"),
    ("5.1", "Leadership et engagement"),
    ("5.2.1", "Établissement de la politique de continuité"),
    ("5.2.2", "Communication de la politique de continuité"),
    ("5.3", "Rôles, responsabilités et autorités"),
    ("6.1.1", "Détermination des risques et opportunités"),
    ("6.1.2", "Actions face aux risques et opportunités"),
    ("6.2.1", "Établissement des objectifs de continuité"),
    ("6.2.2", "Planification des actions pour atteindre les objectifs"),
    ("6.3", "Planification des modifications du SMCA"),
    ("7.1", "Ressources"),
    ("7.2", "Compétences"),
    ("7.3", "Sensibilisation"),
    ("7.4", "Communication"),
    ("7.5.1", "Informations documentées : généralités"),
    ("7.5.2", "Création et mise à jour des informations documentées"),
    ("7.5.3", "Maîtrise des informations documentées"),
    ("8.1", "Planification et maîtrise opérationnelles"),
    ("8.2.1", "Analyse d'impact et appréciation du risque : généralités"),
    ("8.2.2", "Analyse d'impact sur l'activité (BIA)"),
    ("8.2.3", "Appréciation du risque"),
    ("8.3.1", "Stratégies et solutions : généralités"),
    ("8.3.2", "Identification des stratégies et solutions"),
    ("8.3.3", "Choix des stratégies et solutions"),
    ("8.3.4", "Besoins en ressources"),
    ("8.3.5", "Mise en œuvre des solutions"),
    ("8.4.1", "Plans et procédures : généralités"),
    ("8.4.2", "Structure de réponse"),
    ("8.4.3", "Alerte et communication"),
    ("8.4.4", "Plans de continuité d'activité"),
    ("8.4.5", "Reprise"),
    ("8.5", "Programme d'exercices"),
    ("8.6", "Évaluation de la documentation et des capacités de continuité"),
    ("9.1", "Surveillance, mesure, analyse et évaluation"),
    ("9.2.1", "Audit interne : généralités"),
    ("9.2.2", "Programme d'audit"),
    ("9.3.1", "Revue de direction : généralités"),
    ("9.3.2", "Éléments d'entrée de la revue de direction"),
    ("9.3.3", "Éléments de sortie de la revue de direction"),
    ("10.1", "Non-conformité et action corrective"),
    ("10.2", "Amélioration continue"),
])

# ISO/IEC 20000-1:2018 - Système de management des services
ISO20000 = _by_chapter([
    ("4.1", "Compréhension de l'organisation et de son contexte"),
    ("4.2", "Besoins et attentes des parties intéressées"),
    ("4.3", "Domaine d'application du SMS"),
    ("4.4", "Système de management des services"),
    ("5.1", "Leadership et engagement"),
    ("5.2", "Politique de management des services"),
    ("5.3", "Rôles, responsabilités et autorités"),
    ("6.1", "Actions face aux risques et opportunités"),
    ("6.2", "Objectifs de management des services et planification"),
    ("6.3", "Planification du SMS"),
    ("7.1", "Ressources"),
    ("7.2", "Compétences"),
    ("7.3", "Sensibilisation"),
    ("7.4", "Communication"),
    ("7.5", "Informations documentées"),
    ("7.6", "Connaissances"),
    ("8.1", "Planification et maîtrise opérationnelles"),
    ("8.2.1", "Fourniture des services"),
    ("8.2.2", "Planification des services"),
    ("8.2.3", "Maîtrise des parties intervenant dans le cycle de vie des services"),
    ("8.2.4", "Gestion du catalogue de services"),
    ("8.2.5", "Gestion des actifs"),
    ("8.2.6", "Gestion de la configuration"),
    ("8.3.1", "Relations et accords : généralités"),
    ("8.3.2", "Gestion de la relation client"),
    ("8.3.3", "Gestion des niveaux de service"),
    ("8.3.4", "Gestion des fournisseurs"),
    ("8.4.1", "Budgétisation et comptabilisation des services"),
    ("8.4.2", "Gestion de la demande"),
    ("8.4.3", "Gestion de la capacité"),
    ("8.5.1", "Gestion des changements"),
    ("8.5.2", "Conception et transition des services"),
    ("8.5.3", "Gestion des mises en production et des déploiements"),
    ("8.6.1", "Gestion des incidents"),
    ("8.6.2", "Gestion des demandes de service"),
    ("8.6.3", "Gestion des problèmes"),
    ("8.7.1", "Gestion de la disponibilité des services"),
    ("8.7.2", "Gestion de la continuité des services"),
    ("8.7.3", "Gestion de la sécurité de l'information"),
    ("9.1", "Surveillance, mesure, analyse et évaluation"),
    ("9.2", "Audit interne"),
    ("9.3", "Revue de direction"),
    ("9.4", "Rapports sur les services"),
    ("10.1", "Non-conformité et action corrective"),
    ("10.2", "Amélioration continue"),
])

MAPPINGS += [
    # ISO 22301 -> ISO 27001 (Annexe A)
    ("ISO22301", "8.2.2", "ISO27001", "5.30"),
    ("ISO22301", "8.3.2", "ISO27001", "5.30"),
    ("ISO22301", "8.4.4", "ISO27001", "5.29"),
    ("ISO22301", "8.4.4", "ISO27001", "5.30"),
    ("ISO22301", "8.4.5", "ISO27001", "8.13"),
    ("ISO22301", "8.5", "ISO27001", "5.30"),
    ("ISO22301", "8.3.4", "ISO27001", "8.14"),
    ("ISO22301", "8.4.3", "ISO27001", "5.24"),
    # ISO/IEC 20000-1 -> ISO 27001 (Annexe A)
    ("ISO20000", "8.2.5", "ISO27001", "5.9"),
    ("ISO20000", "8.2.6", "ISO27001", "8.9"),
    ("ISO20000", "8.3.4", "ISO27001", "5.19"),
    ("ISO20000", "8.3.4", "ISO27001", "5.22"),
    ("ISO20000", "8.4.3", "ISO27001", "8.6"),
    ("ISO20000", "8.5.1", "ISO27001", "8.32"),
    ("ISO20000", "8.5.3", "ISO27001", "8.32"),
    ("ISO20000", "8.6.1", "ISO27001", "5.24"),
    ("ISO20000", "8.6.1", "ISO27001", "5.26"),
    ("ISO20000", "8.6.3", "ISO27001", "5.27"),
    ("ISO20000", "8.7.1", "ISO27001", "8.14"),
    ("ISO20000", "8.7.2", "ISO27001", "5.30"),
    ("ISO20000", "8.7.3", "ISO27001", "5.1"),
    ("ISO20000", "7.6", "ISO27001", "5.37"),
    # ISO/IEC 20000-1 <-> ISO 22301
    ("ISO20000", "8.7.2", "ISO22301", "8.4.4"),
    ("ISO20000", "8.7.2", "ISO22301", "8.5"),
    ("ISO20000", "8.7.1", "ISO22301", "8.3.2"),
]
