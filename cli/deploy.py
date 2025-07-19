import os
import json
import subprocess
import time
from pathlib import Path
import click
import boto3

AWS_REGION = "ap-south-1"
AWS_PROFILE = "Priyesh"
ENV = "dev"
versionjson_path = Path("C:/Users/Minfy/Desktop/frontend-deployer-cli/version.json")


def wait_for_service_active(cluster, service, region, profile):
    session = boto3.Session(profile_name=profile, region_name=region)
    ecs_client = session.client("ecs")

    click.echo(f"⏳ Waiting for ECS service '{service}' to become ACTIVE...")

    for attempt in range(10):
        response = ecs_client.describe_services(cluster=cluster, services=[service])
        status = response['services'][0]['status']

        if status == "ACTIVE":
            click.echo("✅ ECS service is ACTIVE!")
            return True

        click.echo(f"Attempt {attempt+1}/10: Service status = {status}. Retrying in 5s...")
        time.sleep(5)

    click.echo("❌ ECS service did not become ACTIVE in time.")
    return False


@click.command(name='deploy')
@click.option('--version', required=True, help='Image version to deploy (e.g. v1, v2)')
def deploy_command(version):
    """
    Deploy Docker image to ECR and update ECS service with new Task Definition.
    """
    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        sts = session.client("sts")
        ecs = session.client("ecs")
        elbv2 = session.client("elbv2")
        account_id = sts.get_caller_identity()["Account"]
        ecr_url = f"{account_id}.dkr.ecr.{AWS_REGION}.amazonaws.com"
        click.echo(f"✅ AWS Account ID: {account_id}")
    except Exception as e:
        click.echo(f"❌ Failed to authenticate AWS session: {e}")
        return

    image = f"{ecr_url}/{ENV}-frontend-ecr:{version}"

    click.echo("🔐 Logging into ECR...")
    try:
        login_cmd = (
            f"aws ecr get-login-password --region {AWS_REGION} --profile {AWS_PROFILE} | "
            f"docker login --username AWS --password-stdin {ecr_url}"
        )
        subprocess.run(login_cmd, shell=True, check=True)
    except subprocess.CalledProcessError:
        click.echo("❌ ECR login failed.")
        return

    try:
        click.echo(f"🐳 Building Docker image '{version}'...")
        subprocess.run(["docker", "build", 
                        "--no-cache", # this ensures every --version creates a new-fresh image to push to ECR
                        "--pull","-t", image, 
                        "."
        ], check=True)

        click.echo("📤 Pushing to ECR...")
        subprocess.run(["docker", "push", image], check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Docker build/push failed: {e}")
        return

    task_family = f"{ENV}-frontend-task"
    cluster_name = f"{ENV}-ecs-cluster"
    service_name = f"{ENV}-frontend-service"
    execution_role_arn = f"arn:aws:iam::{account_id}:role/{ENV}-ecsTaskExecutionRole"

    try:
        click.echo("📦 Registering ECS Task Definition...")
        response = ecs.register_task_definition(
            family=task_family,
            executionRoleArn=execution_role_arn,
            networkMode="awsvpc",
            requiresCompatibilities=["FARGATE"],
            cpu="256",
            memory="512",
            containerDefinitions=[{
                "name": "frontend",
                "image": image,
                "essential": True,
                "portMappings": [{
                    "containerPort": 80,
                    "protocol": "tcp"
                }]
            }]
        )
        task_def_arn = response["taskDefinition"]["taskDefinitionArn"]
        revision = response["taskDefinition"]["revision"]
        click.echo(f"✅ Task Definition Registered: {task_def_arn}")
    except Exception as e:
        click.echo(f"❌ Task definition failed: {e}")
        return

    try:
        ecs.describe_services(cluster=cluster_name, services=[service_name])
        
        # 🔁 Wait until service becomes ACTIVE
        if not wait_for_service_active(cluster_name, service_name, AWS_REGION, AWS_PROFILE):
            return
        
        click.echo(f"🔄 Updating ECS Service '{service_name}'...")
        ecs.update_service(
            cluster=cluster_name,
            service=service_name,
            taskDefinition=task_def_arn,
            forceNewDeployment=True
        )
    except ecs.exceptions.ClientError as e:
        if "ServiceNotFoundException" in str(e):
            click.echo(f"🆕 Creating ECS Service '{service_name}'...")
            click.echo("❌ Missing create-service logic. Add subnet, sg, alb_target_group manually if needed.")
            return
        else:
            click.echo(f"❌ Failed to update/create ECS service: {e}")
            return

    click.echo("⏳ Waiting for ECS Service to stabilize...")
    while True:
        res = ecs.describe_services(cluster=cluster_name, services=[service_name])
        deployments = res["services"][0]["deployments"]
        primary = next((d for d in deployments if d["status"] == "PRIMARY"), None)
        if primary and primary["desiredCount"] == primary["runningCount"] and primary["pendingCount"] == 0:
            click.echo("✅ Service is stable.")
            break
        click.echo(f"🔁 Running: {primary['runningCount']} / Desired: {primary['desiredCount']}")
        time.sleep(5)

    version_entry = {
        "version": version,
        "revision": revision
    }
    if versionjson_path.exists():
        with open(versionjson_path) as vf:
            version_data = json.load(vf)
            history = version_data.get("history", [])
    else:
        history = []

    version_data = {
        "latest_version": version,
        "history": history + [version_entry]
    }

    with open(versionjson_path, "w") as vf:
        json.dump(version_data, vf, indent=2)

    click.echo("📝 version.json updated.")

    try:
        alb_name = f"{ENV}-alb"
        albs = elbv2.describe_load_balancers(Names=[alb_name])
        alb_dns = albs["LoadBalancers"][0]["DNSName"]
        website_url = f"http://{alb_dns}"
        click.echo(f"🌐 App is live at: {website_url}")
        return website_url
    except Exception as e:
        click.echo(f"❌ Could not retrieve ALB DNS: {e}")
        return


if __name__ == "__main__":
    deploy_command()
