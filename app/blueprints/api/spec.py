"""Description OpenAPI 3.0 de l'API (3.14)."""
from app.models import AssetCategory, AssetStatus, Classification
from app.services.inventory import CYCLE, ROLES


def _param(name, desc, schema):
    return {"name": name, "in": "query", "required": False, "description": desc, "schema": schema}


def _err(desc):
    return {"description": desc, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Erreur"}}}}


def document():
    nullable_int = {"type": "integer", "minimum": 1, "maximum": 4, "nullable": True}
    need = {"type": "object", "properties": {
        "propre": nullable_int, "retenu": nullable_int,
        "herite_de": {"type": "string", "nullable": True, "description": "Référence de la valeur métier déterminante"}}}
    link = {"type": "object", "properties": {"id": {"type": "integer"}, "reference": {"type": "string"}, "nom": {"type": "string"}}}
    person = {"type": "object", "nullable": True, "properties": {"nom": {"type": "string"}, "email": {"type": "string"}}}
    text = {"type": "string", "nullable": True}
    day = {"type": "string", "format": "date", "nullable": True}
    asset = {"type": "object", "properties": {
        "id": {"type": "integer"}, "reference": {"type": "string"}, "nom": {"type": "string"}, "description": text,
        "role": {"type": "string", "enum": ["valeur_metier", "bien_support"]},
        "categorie": {"type": "string", "enum": [x.value for x in AssetCategory]}, "categorie_libelle": {"type": "string"},
        "classification": {"type": "string", "enum": [x.value for x in Classification]},
        "statut": {"type": "string", "enum": [x.value for x in AssetStatus]},
        "proprietaire": person, "depositaire": text, "detenteur": person, "localisation": text,
        "besoins": {"type": "object", "properties": {k: need for k in "ciat"},
                    "description": "c confidentialité, i intégrité, a disponibilité, t traçabilité (1 à 4)"},
        "criticite": nullable_int, "criticite_libelle": text,
        "biens_supports": {"type": "array", "items": link}, "valeurs_metier": {"type": "array", "items": link},
        "risques": {"type": "array", "items": {"type": "string"}},
        "cycle_de_vie": {"type": "object", "properties": {
            "mise_en_service": day, "fin_de_support": day,
            "etat_support": {"type": "string", "enum": ["depassee", "proche"], "nullable": True},
            "a_restituer": {"type": "boolean"},
            "elimination": {"type": "object", "properties": {
                "date": day, "methode": text, "preuve": text, "preuve_manquante": {"type": "boolean"}}}}},
        "cree_le": {"type": "string", "format": "date-time"}, "modifie_le": {"type": "string", "format": "date-time", "nullable": True},
    }}
    refused = {"401": _err("Jeton absent, invalide, expiré ou révoqué"), "403": _err("Portée insuffisante ou organisation désactivée"),
               "429": _err("Limite de 120 appels par minute atteinte (voir Retry-After)")}
    filters = [
        _param("page", "Numéro de page (à partir de 1)", {"type": "integer", "minimum": 1, "default": 1}),
        _param("par_page", "Taille de page", {"type": "integer", "minimum": 1, "maximum": 500, "default": 100}),
        _param("role", "Valeurs métier ou biens supports", {"type": "string", "enum": list(ROLES)}),
        _param("categorie", "Catégorie", {"type": "string", "enum": [x.value for x in AssetCategory]}),
        _param("classification", "Classification", {"type": "string", "enum": [x.value for x in Classification]}),
        _param("statut", "Statut", {"type": "string", "enum": [x.value for x in AssetStatus]}),
        _param("criticite", "Criticité (besoin le plus élevé)", {"type": "integer", "minimum": 1, "maximum": 4}),
        _param("cycle", "État du cycle de vie", {"type": "string", "enum": list(CYCLE)}),
        _param("reference", "Référence exacte", {"type": "string"}),
        _param("modifie_depuis", "Fiches modifiées depuis cette date (ISO 8601). Les besoins hérités peuvent changer sans "
               "que la fiche du bien support soit modifiée : prévoir aussi une lecture complète périodique.",
               {"type": "string", "format": "date-time"}),
    ]
    return {
        "openapi": "3.0.3",
        "info": {"title": "API Integra", "version": "1.0",
                 "description": "Lecture de l'inventaire des actifs d'une organisation. Chaque appel est inscrit au journal d'activité."},
        "servers": [{"url": "/api/v1"}],
        "security": [{"jeton": []}],
        "paths": {
            "/actifs": {"get": {"summary": "Inventaire des actifs", "operationId": "listerActifs", "parameters": filters, "responses": {
                "200": {"description": "Page d'actifs", "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "donnees": {"type": "array", "items": {"$ref": "#/components/schemas/Actif"}},
                    "pagination": {"type": "object", "properties": {
                        "page": {"type": "integer"}, "par_page": {"type": "integer"}, "total": {"type": "integer"},
                        "pages": {"type": "integer"}, "suivante": {"type": "integer", "nullable": True}}}}}}}},
                "400": _err("Paramètre invalide"), **refused}}},
            "/actifs/{id}": {"get": {"summary": "Fiche d'un actif", "operationId": "lireActif", "parameters": [
                {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {
                "200": {"description": "Actif", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Actif"}}}},
                "404": _err("Actif introuvable dans cette organisation"), **refused}}},
        },
        "components": {
            "securitySchemes": {"jeton": {"type": "http", "scheme": "bearer", "description": "Jeton créé dans Administration › API et intégrations"}},
            "schemas": {"Actif": asset, "Erreur": {"type": "object", "properties": {"erreur": {"type": "object", "properties": {
                "code": {"type": "string"}, "message": {"type": "string"}}}}}},
        },
    }
