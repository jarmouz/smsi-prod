import enum


class Role(str, enum.Enum):
    RSSI = "RSSI"
    CONTRIBUTEUR = "CONTRIBUTEUR"
    AUDITEUR = "AUDITEUR"
    LECTEUR = "LECTEUR"

    @property
    def label(self):
        return {
            "RSSI": "RSSI / Responsable SMSI",
            "CONTRIBUTEUR": "Contributeur",
            "AUDITEUR": "Auditeur interne",
            "LECTEUR": "Lecteur",
        }[self.value]


class Theme(str, enum.Enum):
    """Thèmes de l'Annexe A ISO/IEC 27001:2022."""
    ORGANISATIONNELLE = "ORGANISATIONNELLE"
    HUMAINE = "HUMAINE"
    PHYSIQUE = "PHYSIQUE"
    TECHNOLOGIQUE = "TECHNOLOGIQUE"

    @property
    def label(self):
        return {
            "ORGANISATIONNELLE": "Mesures organisationnelles",
            "HUMAINE": "Mesures liées aux personnes",
            "PHYSIQUE": "Mesures physiques",
            "TECHNOLOGIQUE": "Mesures technologiques",
        }[self.value]

    @property
    def annex(self):
        return {"ORGANISATIONNELLE": "A.5", "HUMAINE": "A.6",
                "PHYSIQUE": "A.7", "TECHNOLOGIQUE": "A.8"}[self.value]


class ControlStatus(str, enum.Enum):
    NON_APPLICABLE = "NON_APPLICABLE"
    NON_DEMARRE = "NON_DEMARRE"
    EN_COURS = "EN_COURS"
    IMPLEMENTE = "IMPLEMENTE"

    @property
    def label(self):
        return {
            "NON_APPLICABLE": "Non applicable",
            "NON_DEMARRE": "Non démarré",
            "EN_COURS": "En cours",
            "IMPLEMENTE": "Implémenté",
        }[self.value]


class Treatment(str, enum.Enum):
    # risque (menace)
    REDUIRE = "REDUIRE"
    ACCEPTER = "ACCEPTER"
    EVITER = "EVITER"
    PARTAGER = "PARTAGER"            # aussi pour une opportunité
    # opportunité (3.6) : on ne « réduit » ni « n'accepte » une opportunité
    EXPLOITER = "EXPLOITER"
    RENFORCER = "RENFORCER"
    NE_PAS_SAISIR = "NE_PAS_SAISIR"

    @property
    def label(self):
        return {
            "REDUIRE": "Réduire",
            "ACCEPTER": "Accepter",
            "EVITER": "Éviter",
            "PARTAGER": "Partager / transférer",
            "EXPLOITER": "Exploiter (saisir)",
            "RENFORCER": "Renforcer (accroître le bénéfice)",
            "NE_PAS_SAISIR": "Ne pas donner suite",
        }[self.value]

    @classmethod
    def for_nature(cls, nature):
        """Options de traitement d'un risque (nature None) ou d'une opportunité."""
        if nature == "OPPORTUNITE":
            return [cls.EXPLOITER, cls.RENFORCER, cls.PARTAGER, cls.NE_PAS_SAISIR]
        return [cls.REDUIRE, cls.ACCEPTER, cls.EVITER, cls.PARTAGER]

    @classmethod
    def default_for(cls, nature):
        return cls.for_nature(nature)[0]


class RiskStatus(str, enum.Enum):
    IDENTIFIE = "IDENTIFIE"
    EN_TRAITEMENT = "EN_TRAITEMENT"
    TRAITE = "TRAITE"
    ACCEPTE = "ACCEPTE"
    CLOTURE = "CLOTURE"

    @property
    def label(self):
        return {
            "IDENTIFIE": "Identifié",
            "EN_TRAITEMENT": "En traitement",
            "TRAITE": "Traité",
            "ACCEPTE": "Accepté",
            "CLOTURE": "Clôturé",
        }[self.value]

    @property
    def is_open(self):
        return self.value not in ("CLOTURE",)


class AuditStatus(str, enum.Enum):
    PLANIFIE = "PLANIFIE"
    EN_COURS = "EN_COURS"
    TERMINE = "TERMINE"

    @property
    def label(self):
        return {"PLANIFIE": "Planifié", "EN_COURS": "En cours", "TERMINE": "Terminé"}[self.value]


class FindingType(str, enum.Enum):
    NC_MAJEURE = "NC_MAJEURE"
    NC_MINEURE = "NC_MINEURE"
    OBSERVATION = "OBSERVATION"
    OPPORTUNITE = "OPPORTUNITE"

    @property
    def label(self):
        return {
            "NC_MAJEURE": "Non-conformité majeure",
            "NC_MINEURE": "Non-conformité mineure",
            "OBSERVATION": "Observation",
            "OPPORTUNITE": "Piste d'amélioration",
        }[self.value]

    @property
    def short(self):
        return {"NC_MAJEURE": "NC majeure", "NC_MINEURE": "NC mineure",
                "OBSERVATION": "Observation", "OPPORTUNITE": "Amélioration"}[self.value]


class ActionStatus(str, enum.Enum):
    OUVERTE = "OUVERTE"
    EN_COURS = "EN_COURS"
    REALISEE = "REALISEE"
    VERIFIEE = "VERIFIEE"

    @property
    def label(self):
        return {"OUVERTE": "Ouverte", "EN_COURS": "En cours",
                "REALISEE": "Réalisée", "VERIFIEE": "Vérifiée (soldée)"}[self.value]

    @property
    def is_open(self):
        return self.value not in ("VERIFIEE",)


class DocStatus(str, enum.Enum):
    BROUILLON = "BROUILLON"
    EN_REVUE = "EN_REVUE"
    APPROUVE = "APPROUVE"
    OBSOLETE = "OBSOLETE"

    @property
    def label(self):
        return {"BROUILLON": "Brouillon", "EN_REVUE": "En revue",
                "APPROUVE": "Approuvé", "OBSOLETE": "Obsolète"}[self.value]


class DocType(str, enum.Enum):
    POLITIQUE = "POLITIQUE"
    PROCEDURE = "PROCEDURE"
    ENREGISTREMENT = "ENREGISTREMENT"
    AUTRE = "AUTRE"

    @property
    def label(self):
        return {"POLITIQUE": "Politique", "PROCEDURE": "Procédure",
                "ENREGISTREMENT": "Enregistrement", "AUTRE": "Autre"}[self.value]


class ReviewStatus(str, enum.Enum):
    PLANIFIEE = "PLANIFIEE"
    TENUE = "TENUE"

    @property
    def label(self):
        return {"PLANIFIEE": "Planifiée", "TENUE": "Tenue"}[self.value]


class AssetCategory(str, enum.Enum):
    INFORMATION = "INFORMATION"
    LOGICIEL = "LOGICIEL"
    MATERIEL = "MATERIEL"
    SERVICE = "SERVICE"
    PERSONNEL = "PERSONNEL"
    SITE = "SITE"

    @property
    def label(self):
        return {"INFORMATION": "Information / données", "LOGICIEL": "Logiciel / application",
                "MATERIEL": "Matériel", "SERVICE": "Service", "PERSONNEL": "Personnel",
                "SITE": "Site / local"}[self.value]


class Classification(str, enum.Enum):
    PUBLIC = "PUBLIC"
    INTERNE = "INTERNE"
    CONFIDENTIEL = "CONFIDENTIEL"
    SECRET = "SECRET"

    @property
    def label(self):
        return {"PUBLIC": "Public", "INTERNE": "Interne",
                "CONFIDENTIEL": "Confidentiel", "SECRET": "Secret"}[self.value]

    @property
    def rank(self):
        return {"PUBLIC": 0, "INTERNE": 1, "CONFIDENTIEL": 2, "SECRET": 3}[self.value]


class AssetStatus(str, enum.Enum):
    ACTIF = "ACTIF"
    MAINTENANCE = "MAINTENANCE"
    RETIRE = "RETIRE"

    @property
    def label(self):
        return {"ACTIF": "Actif", "MAINTENANCE": "En maintenance", "RETIRE": "Retiré"}[self.value]


class IncidentCategory(str, enum.Enum):
    MALVEILLANCE = "MALVEILLANCE"
    PANNE = "PANNE"
    ERREUR_HUMAINE = "ERREUR_HUMAINE"
    PERTE_VOL = "PERTE_VOL"
    DIVULGATION = "DIVULGATION"
    AUTRE = "AUTRE"

    @property
    def label(self):
        return {"MALVEILLANCE": "Acte malveillant", "PANNE": "Panne / indisponibilité",
                "ERREUR_HUMAINE": "Erreur humaine", "PERTE_VOL": "Perte / vol",
                "DIVULGATION": "Divulgation de données", "AUTRE": "Autre"}[self.value]


class IncidentSeverity(str, enum.Enum):
    MINEUR = "MINEUR"
    MAJEUR = "MAJEUR"
    CRITIQUE = "CRITIQUE"

    @property
    def label(self):
        return {"MINEUR": "Mineur", "MAJEUR": "Majeur", "CRITIQUE": "Critique"}[self.value]


class IncidentStatus(str, enum.Enum):
    NOUVEAU = "NOUVEAU"
    EN_COURS = "EN_COURS"
    RESOLU = "RESOLU"
    CLOTURE = "CLOTURE"

    @property
    def label(self):
        return {"NOUVEAU": "Nouveau", "EN_COURS": "En cours",
                "RESOLU": "Résolu", "CLOTURE": "Clôturé"}[self.value]

    @property
    def is_open(self):
        return self.value not in ("CLOTURE",)


class AwarenessType(str, enum.Enum):
    FORMATION = "FORMATION"
    CAMPAGNE_PHISHING = "CAMPAGNE_PHISHING"
    COMMUNICATION = "COMMUNICATION"
    ATELIER = "ATELIER"

    @property
    def label(self):
        return {"FORMATION": "Formation", "CAMPAGNE_PHISHING": "Campagne de phishing",
                "COMMUNICATION": "Communication / rappel", "ATELIER": "Atelier"}[self.value]


class AwarenessStatus(str, enum.Enum):
    PLANIFIEE = "PLANIFIEE"
    EN_COURS = "EN_COURS"
    TERMINEE = "TERMINEE"

    @property
    def label(self):
        return {"PLANIFIEE": "Planifiée", "EN_COURS": "En cours", "TERMINEE": "Terminée"}[self.value]


# --- P2 : contexte, objectifs, non-conformités, fournisseurs, exigences --------
def _labelled(name, items):
    """Énumération str avec .label (évite de répéter le même patron)."""
    cls = enum.Enum(name, {k: k for k, _ in items}, type=str)
    labels = dict(items)
    cls.label = property(lambda self: labels[self.value])
    return cls


IssueKind = _labelled("IssueKind", [("EXTERNE", "Enjeu externe"), ("INTERNE", "Enjeu interne")])
IssueCategory = _labelled("IssueCategory", [
    ("POLITIQUE", "Politique / géopolitique"), ("ECONOMIQUE", "Économique / marché"), ("SOCIAL", "Social / humain"),
    ("TECHNOLOGIQUE", "Technologique"), ("ENVIRONNEMENTAL", "Environnemental"), ("LEGAL", "Légal / réglementaire"),
    ("ORGANISATIONNEL", "Organisation / gouvernance"), ("CONCURRENCE", "Clients / concurrence")])
PartyCategory = _labelled("PartyCategory", [
    ("CLIENT", "Clients"), ("AUTORITE", "Autorités / régulateurs"), ("FOURNISSEUR", "Fournisseurs / sous-traitants"),
    ("PERSONNEL", "Personnel"), ("DIRECTION", "Direction / actionnaires"), ("PARTENAIRE", "Partenaires"),
    ("ASSUREUR", "Assureurs / banques"), ("AUTRE", "Autre")])
ObjectiveStatus = _labelled("ObjectiveStatus", [
    ("PLANIFIE", "Planifié"), ("EN_COURS", "En cours"), ("ATTEINT", "Atteint"),
    ("NON_ATTEINT", "Non atteint"), ("ABANDONNE", "Abandonné")])
Frequency = _labelled("Frequency", [("MENSUELLE", "Mensuelle"), ("TRIMESTRIELLE", "Trimestrielle"),
                                    ("SEMESTRIELLE", "Semestrielle"), ("ANNUELLE", "Annuelle")])
Direction = _labelled("Direction", [("HAUSSE", "Plus c'est haut, mieux c'est"), ("BAISSE", "Plus c'est bas, mieux c'est")])
NcSource = _labelled("NcSource", [
    ("AUDIT_INTERNE", "Audit interne"), ("AUDIT_EXTERNE", "Audit externe / certification"), ("INCIDENT", "Incident"),
    ("RECLAMATION", "Réclamation client / partie intéressée"), ("REVUE_DIRECTION", "Revue de direction"),
    ("SURVEILLANCE", "Surveillance / indicateur"), ("CONTROLE", "Contrôle interne"), ("AUTRE", "Autre")])
NcSeverity = _labelled("NcSeverity", [("MAJEURE", "Majeure"), ("MINEURE", "Mineure")])
NcStatus = _labelled("NcStatus", [("OUVERTE", "Ouverte"), ("EN_TRAITEMENT", "En traitement"),
                                  ("A_VERIFIER", "Efficacité à vérifier"), ("CLOTUREE", "Clôturée")])
SupplierCategory = _labelled("SupplierCategory", [
    ("CLOUD", "Cloud / hébergement"), ("LOGICIEL", "Logiciel / SaaS"), ("INFOGERANCE", "Infogérance / support"),
    ("TELECOM", "Télécoms / réseau"), ("SECURITE", "Services de sécurité"), ("CONSEIL", "Conseil / prestations"),
    ("MATERIEL", "Matériel"), ("AUTRE", "Autre")])
Criticality = _labelled("Criticality", [("CRITIQUE", "Critique"), ("IMPORTANT", "Important"), ("STANDARD", "Standard")])
DataAccess = _labelled("DataAccess", [("AUCUN", "Aucun accès"), ("INTERNE", "Données internes"),
                                      ("CONFIDENTIEL", "Données confidentielles"), ("PERSONNEL", "Données personnelles")])
AssessmentResult = _labelled("AssessmentResult", [("NON_EVALUE", "Non évalué"), ("CONFORME", "Conforme"),
                                                  ("RESERVES", "Conforme avec réserves"), ("NON_CONFORME", "Non conforme")])
SupplierStatus = _labelled("SupplierStatus", [("EN_SELECTION", "En sélection"), ("ACTIF", "Actif"), ("TERMINE", "Relation terminée")])
RequirementType = _labelled("RequirementType", [
    ("LEGALE", "Légale"), ("REGLEMENTAIRE", "Réglementaire"), ("CONTRACTUELLE", "Contractuelle"),
    ("NORMATIVE", "Normative / référentiel"), ("INTERNE", "Engagement interne")])
ComplianceStatus = _labelled("ComplianceStatus", [("A_EVALUER", "À évaluer"), ("CONFORME", "Conforme"),
                                                  ("PARTIEL", "Partiellement conforme"), ("NON_CONFORME", "Non conforme")])


# --- P3 : programme d'audit, compétences, continuité, changements ------------
CompetenceType = _labelled("CompetenceType", [
    ("FORMATION", "Formation"), ("CERTIFICATION", "Certification"), ("EXPERIENCE", "Expérience"),
    ("HABILITATION", "Habilitation"), ("DIPLOME", "Diplôme")])
TestType = _labelled("TestType", [
    ("TABLE_TOP", "Exercice sur table"), ("SIMULATION", "Simulation"), ("BASCULE", "Bascule réelle"),
    ("RESTAURATION", "Test de restauration"), ("TECHNIQUE", "Test technique de composant")])
TestResult = _labelled("TestResult", [("PLANIFIE", "Planifié"), ("REUSSI", "Réussi"),
                                      ("PARTIEL", "Partiellement réussi"), ("ECHEC", "Échec")])
ChangeKind = _labelled("ChangeKind", [("TECHNIQUE", "Technique (A.8.32)"), ("SMSI", "Modification du SMSI (6.3)"),
                                      ("ORGANISATIONNEL", "Organisationnel")])
ChangeRisk = _labelled("ChangeRisk", [("FAIBLE", "Faible"), ("MOYEN", "Moyen"), ("ELEVE", "Élevé")])
ChangeStatus = _labelled("ChangeStatus", [
    ("DEMANDE", "Demandé"), ("APPROUVE", "Approuvé"), ("REFUSE", "Refusé"), ("REALISE", "Réalisé"),
    ("CLOTURE", "Revu et clôturé"), ("ANNULE", "Annulé")])
DigestFrequency = _labelled("DigestFrequency", [("QUOTIDIEN", "Quotidien"), ("HEBDO", "Hebdomadaire (lundi)"),
                                                ("JAMAIS", "Jamais")])
