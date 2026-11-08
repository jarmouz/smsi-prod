"""Amazon Web Services : instances, bases, fonctions et compartiments."""
import re

from app.models import AssetCategory
from app.services.connectors import ConnectorError, Kind, Param


def _client(service, region, cfg, secrets):
    import boto3
    from botocore.config import Config
    return boto3.client(service, region_name=region, aws_access_key_id=(cfg.get("access_key_id") or "").strip(),
                        aws_secret_access_key=secrets.get("secret_access_key", ""),
                        config=Config(connect_timeout=10, read_timeout=30, retries={"max_attempts": 3}))


def _regions(cfg):
    regions = [r.strip() for r in (cfg.get("regions") or "").split(",") if r.strip()]
    if not regions or not all(re.fullmatch(r"[a-z]{2}(-[a-z]+)+-\d", r) for r in regions):
        raise ConnectorError("Indiquez les régions AWS séparées par des virgules (ex. eu-west-3, eu-central-1).")
    return regions


def _item(external_id, name, region, description):
    return {"external_id": external_id, "name": name, "category": AssetCategory.SERVICE, "location": f"AWS {region}", "description": description}


def _fetch(cfg, secrets):
    regions = _regions(cfg)
    for region in regions:
        ec2 = _client("ec2", region, cfg, secrets)
        for page in ec2.get_paginator("describe_instances").paginate():
            for res in page.get("Reservations", []):
                for i in res.get("Instances", []):
                    if i.get("State", {}).get("Name") == "terminated":
                        continue
                    tags = {t.get("Key"): t.get("Value") for t in i.get("Tags", [])}
                    yield _item(f"ec2:{region}:{i['InstanceId']}", tags.get("Name") or i["InstanceId"], region, f"Instance EC2 {i.get('InstanceType', '')} {i['InstanceId']}")
        rds = _client("rds", region, cfg, secrets)
        for page in rds.get_paginator("describe_db_instances").paginate():
            for d in page.get("DBInstances", []):
                yield _item(d["DBInstanceArn"], d["DBInstanceIdentifier"], region, f"Base RDS {d.get('Engine', '')}")
        fn = _client("lambda", region, cfg, secrets)
        for page in fn.get_paginator("list_functions").paginate():
            for f in page.get("Functions", []):
                yield _item(f["FunctionArn"], f["FunctionName"], region, f"Fonction Lambda {f.get('Runtime', '')}")
    for b in _client("s3", regions[0], cfg, secrets).list_buckets().get("Buckets", []):
        yield _item(f"s3:{b['Name']}", b["Name"], "global", "Compartiment S3")


def fetch(cfg, secrets):
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        yield from _fetch(cfg, secrets)
    except ClientError as e:
        raise ConnectorError(f"AWS : accès refusé ou erreur ({e.response.get('Error', {}).get('Code', 'inconnue')}). Vérifiez la stratégie IAM.")
    except BotoCoreError as e:
        raise ConnectorError(f"AWS injoignable ({e.__class__.__name__}).")


KIND = Kind("aws", "Amazon Web Services", "Instances EC2, bases RDS, fonctions Lambda et compartiments S3.",
            "Un utilisateur IAM dédié avec ec2:DescribeInstances, rds:DescribeDBInstances, lambda:ListFunctions et s3:ListAllMyBuckets, sans autre droit.",
            [Param("access_key_id", "Identifiant de clé d'accès"), Param("secret_access_key", "Clé d'accès secrète", secret=True),
             Param("regions", "Régions", hint="séparées par des virgules, ex. eu-west-3, eu-central-1")], fetch)
