import os
import json
import time
import click
import boto3
from pathlib import Path

AWS_REGION = "ap-south-1"
AWS_PROFILE = "Priyesh"
ENV = "dev"
versionjson_path = Path("C:/Users/Minfy/Desktop/frontend-deployer-cli/version.json")


@click.command(name='rollback')
@click.option('--version', required=True, type=str, help='Version tag to rollback to (e.g. v3, v5)')
def rollback_command(version):
    """
    Rollback ECS service to a previously deployed version using task definition revision.
    """
    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        sts = session.client("sts")
        ecs = session.client("ecs")
        elbv2 = session.client("elbv2")
        account_id = sts.get_caller_identity()["Account"]
        click.echo(f"✅ AWS Account ID: {account_id}")
    except Exception as e:
        click.echo(f"❌ Failed to authenticate AWS session: {e}")
        return

    # 🔍 Load version.json and find the target revision
    if not versionjson_path.exists():
        click.echo("❌ version.json not found.")
        return

    with open(versionjson_path, "r") as vf:
        version_data = json.load(vf)
        history = version_data.get("history", [])
        match = next((entry for entry in history if entry["version"] == version), None)

        if not match:
            click.echo(f"❌ Version '{version}' not found in version.json.")
            return

    revision = match["revision"]
    task_family = f"{ENV}-frontend-task"
    task_definition = f"{task_family}:{revision}"
    cluster_name = f"{ENV}-ecs-cluster"
    service_name = f"{ENV}-frontend-service"

    click.echo(f"📦 Found revision {revision} for version '{version}'")
    click.echo(f"🔁 Rolling back ECS service '{service_name}' to task definition: {task_definition}")

    # ✅ Rollback via ECS Update
    try:
        ecs.update_service(
            cluster=cluster_name,
            service=service_name,
            taskDefinition=task_definition,
            forceNewDeployment=True
        )
    except Exception as e:
        click.echo(f"❌ Failed to update ECS service: {e}")
        return

    # ⏳ Wait until ECS service becomes stable again
    click.echo("⏳ Waiting for ECS Service to stabilize...")
    while True:
        res = ecs.describe_services(cluster=cluster_name, services=[service_name])
        deployments = res["services"][0]["deployments"]
        primary = next((d for d in deployments if d["status"] == "PRIMARY"), None)

        if primary and primary["desiredCount"] == primary["runningCount"] and primary["pendingCount"] == 0:
            click.echo("✅ Rollback complete. Service is stable.")
            break

        click.echo(f"🔁 Running: {primary['runningCount']} / Desired: {primary['desiredCount']}")
        time.sleep(5)

    # 🌐 Show ALB URL if available
    try:
        alb_name = f"{ENV}-alb"
        albs = elbv2.describe_load_balancers(Names=[alb_name])
        alb_dns = albs["LoadBalancers"][0]["DNSName"]
        website_url = f"http://{alb_dns}"
        click.echo(f"🌐 Rolled-back app is live at: {website_url}")
    except Exception as e:
        click.echo(f"⚠️ Rollback succeeded, but could not retrieve ALB DNS: {e}")
