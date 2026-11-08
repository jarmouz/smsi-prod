"""Microsoft : Intune (appareils gérés), Entra ID (applications SaaS), Azure (ressources cloud)."""
import re
from datetime import datetime

from app.models import AssetCategory
from app.services.connectors import ConnectorError, Kind, Param, call

LOGIN_URL = "https://login.microsoftonline.com"
GRAPH_URL = "https://graph.microsoft.com"
MANAGEMENT_URL = "https://management.azure.com"
MICROSOFT_TENANTS = {"f8cdef31-a31e-4b4a-93e4-5f571e91255a", "72f988bf-86f1-41af-91ab-2d7cd011db47"}   # applications de Microsoft
AZURE_TYPES = ("microsoft.compute/virtualmachines", "microsoft.sql/servers", "microsoft.dbforpostgresql/flexibleservers",
               "microsoft.dbformysql/flexibleservers", "microsoft.storage/storageaccounts", "microsoft.keyvault/vaults",
               "microsoft.web/sites", "microsoft.containerservice/managedclusters")


def _token(cfg, secrets, resource):
    tenant = (cfg.get("tenant_id") or "").strip()
    if not re.fullmatch(r"[\w.-]+", tenant):
        raise ConnectorError("Identifiant de tenant invalide.")
    r = call("Microsoft", "POST", f"{LOGIN_URL}/{tenant}/oauth2/v2.0/token",
             data={"grant_type": "client_credentials", "client_id": (cfg.get("client_id") or "").strip(),
                   "client_secret": secrets.get("client_secret", ""), "scope": f"{resource}/.default"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _graph(url, head):
    while url:
        if not url.startswith(GRAPH_URL + "/"):
            raise ConnectorError("Microsoft Graph : page suivante hors de Graph refusée.")
        data = call("Microsoft Graph", "GET", url, headers=head).json()
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")


def _day(raw):
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except (AttributeError, ValueError):
        return None


def fetch_intune(cfg, secrets):
    head = _token(cfg, secrets, GRAPH_URL)
    fields = "id,deviceName,serialNumber,userPrincipalName,operatingSystem,osVersion,complianceState,manufacturer,model,enrolledDateTime"
    for d in _graph(f"{GRAPH_URL}/v1.0/deviceManagement/managedDevices?$select={fields}&$top=500", head):
        parts = [" ".join(p for p in (d.get("manufacturer"), d.get("model")) if p), " ".join(p for p in (d.get("operatingSystem"), d.get("osVersion")) if p),
                 f"série {d['serialNumber']}" if d.get("serialNumber") else "", f"conformité : {d['complianceState']}" if d.get("complianceState") else ""]
        yield {"external_id": d.get("id"), "name": d.get("deviceName") or "", "category": AssetCategory.MATERIEL,
               "description": " - ".join(p for p in parts if p) + " (Intune)", "holder": d.get("userPrincipalName"),
               "acquired_on": _day(d.get("enrolledDateTime"))}


def fetch_entra(cfg, secrets):
    head = _token(cfg, secrets, GRAPH_URL)
    fields = "id,appId,displayName,accountEnabled,appOwnerOrganizationId,servicePrincipalType,homepage"
    for s in _graph(f"{GRAPH_URL}/v1.0/servicePrincipals?$select={fields}&$top=500", head):
        if s.get("servicePrincipalType") != "Application" or not s.get("accountEnabled") or s.get("appOwnerOrganizationId") in MICROSOFT_TENANTS:
            continue
        yield {"external_id": s.get("appId"), "name": s.get("displayName") or "", "category": AssetCategory.SERVICE,
               "description": "Application d'entreprise déclarée dans Entra ID" + (f" - {s['homepage']}" if s.get("homepage") else "")}


def fetch_azure(cfg, secrets):
    head = _token(cfg, secrets, MANAGEMENT_URL)
    types = ", ".join(f"'{t}'" for t in AZURE_TYPES)
    body = {"query": f"Resources | where type in~ ({types}) | project id, name, type, location, resourceGroup, subscriptionId | order by id asc",
            "options": {"$top": 1000}}
    while True:
        data = call("Azure", "POST", f"{MANAGEMENT_URL}/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01", headers=head, json=body).json()
        for x in data.get("data", []):
            yield {"external_id": (x.get("id") or "").lower(), "name": x.get("name") or "", "category": AssetCategory.SERVICE,
                   "location": f"Azure {x.get('location')}", "description": f"{x.get('type')} - groupe {x.get('resourceGroup')} - abonnement {x.get('subscriptionId')}"}
        token = data.get("$skipToken")
        if not token:
            return
        body["options"]["$skipToken"] = token


_PARAMS = [Param("tenant_id", "Identifiant du tenant"), Param("client_id", "Identifiant de l'application (client)"),
           Param("client_secret", "Secret de l'application", secret=True)]
INTUNE = Kind("intune", "Microsoft Intune", "Ordinateurs et mobiles gérés, avec leur utilisateur et leur conformité.",
              "Inscription d'application Entra avec la seule autorisation d'application DeviceManagementManagedDevices.Read.All.", _PARAMS, fetch_intune)
ENTRA = Kind("entra", "Microsoft Entra ID", "Applications SaaS raccordées à l'annuaire : révèle le catalogue réel (Salesforce, Stripe, etc.).",
             "Inscription d'application Entra avec la seule autorisation d'application Application.Read.All.", _PARAMS, fetch_entra)
AZURE = Kind("azure", "Microsoft Azure", "Machines virtuelles, bases, stockage, coffres, applications web et clusters.",
             "Inscription d'application Entra avec le rôle Lecteur sur les abonnements concernés.", _PARAMS, fetch_azure)
