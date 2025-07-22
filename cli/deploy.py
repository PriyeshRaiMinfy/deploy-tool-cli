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
    """Polls the ECS service until it becomes active."""
    session = boto3.Session(profile_name=profile, region_name=region)
    ecs_client = session.client("ecs")

    click.echo(f"----- Waiting for the ECS service '{service}' to become active...")

    for attempt in range(10):
        response = ecs_client.describe_services(cluster=cluster, services=[service])
        status = response['services'][0]['status']

        if status == "ACTIVE":
            click.echo("----- The ECS service is now active.")
            return True

        click.echo(f"Attempt {attempt + 1}/10: Service status is '{status}'. Retrying in 5 seconds...")
        time.sleep(5)

    click.echo("----- The ECS service did not become active within the expected time.")
    return False


@click.command(name='deploy')
@click.option('--version', required=True, help='The image version to deploy (e.g., v1, v2).')
def deploy_command(version):
    """
    Deploys a Docker image to ECR and updates the ECS service.
    """
    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        sts = session.client("sts")
        ecs = session.client("ecs")
        elbv2 = session.client("elbv2")
        account_id = sts.get_caller_identity()["Account"]
        ecr_url = f"{account_id}.dkr.ecr.{AWS_REGION}.amazonaws.com"
        click.echo(f"----- Successfully authenticated with AWS Account ID: {account_id}")
    except Exception as e:
        click.echo(f"----- Failed to authenticate the AWS session: {e}")
        return

    image = f"{ecr_url}/{ENV}-frontend-ecr:{version}"

    click.echo("----- Logging into Amazon ECR...")
    try:
        login_cmd = (
            f"aws ecr get-login-password --region {AWS_REGION} --profile {AWS_PROFILE} | "
            f"docker login --username AWS --password-stdin {ecr_url}"
        )
        subprocess.run(login_cmd, shell=True, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"----- ECR login failed. Please check your credentials. Error: {e.stderr.decode()}")
        return

    try:
        click.echo(f"----- Building Docker image with tag '{version}'...")
        # Using --no-cache ensures a fresh image is built for each version
        subprocess.run(["docker", "build", "--no-cache", "--pull", "-t", image, "."], check=True)

        click.echo("----- Pushing the image to ECR...")
        subprocess.run(["docker", "push", image], check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"----- The Docker build or push process failed: {e}")
        return

    task_family = f"{ENV}-frontend-task"
    cluster_name = f"{ENV}-ecs-cluster"
    service_name = f"{ENV}-frontend-service"
    execution_role_arn = f"arn:aws:iam::{account_id}:role/{ENV}-ecsTaskExecutionRole"

    try:
        click.echo("----- Registering a new ECS Task Definition...")
        response = ecs.register_task_definition(
            family=task_family,
            executionRoleArn=execution_role_arn,
            networkMode="awsvpc",
            requiresCompatibilities=["FARGATE"],
            cpu="256",
            memory="512",
            containerDefinitions=[
                {
                    "name": "frontend",
                    "image": image,
                    "essential": True,
                    "portMappings": [{"containerPort": 80}]
                },
                {
                    "name": "prometheus",
                    "image": "prom/prometheus:latest",
                    "portMappings": [{"containerPort": 9090}],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": f"/ecs/{ENV}-frontend",
                            "awslogs-region": AWS_REGION,
                            "awslogs-stream-prefix": "ecs"
                        }
                    }
                },
                {
                    "name": "grafana",
                    "image": "grafana/grafana:latest",
                    "portMappings": [{"containerPort": 3000}],
                    "environment": [
                        {"name": "GF_SECURITY_ADMIN_PASSWORD", "value": "admin"},
                        {"name": "GF_SERVER_ROOT_URL", "value": "%(protocol)s://%(domain)s/grafana/"},
                        {"name": "GF_SERVER_SERVE_FROM_SUB_PATH", "value": "true"}
                    ],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": f"/ecs/{ENV}-frontend",
                            "awslogs-region": AWS_REGION,
                            "awslogs-stream-prefix": "ecs"
                        }
                    }
                }
            ]
        )
        task_def_arn = response["taskDefinition"]["taskDefinitionArn"]
        revision = response["taskDefinition"]["revision"]
        click.echo(f"----- Task Definition registered successfully: {task_def_arn}")
    except Exception as e:
        click.echo(f"----- Failed to register the task definition: {e}")
        return

    try:
        ecs.describe_services(cluster=cluster_name, services=[service_name])
        
        if not wait_for_service_active(cluster_name, service_name, AWS_REGION, AWS_PROFILE):
            return
        
        click.echo(f"----- Updating the ECS Service '{service_name}'...")
        ecs.update_service(
            cluster=cluster_name,
            service=service_name,
            taskDefinition=task_def_arn,
            forceNewDeployment=True
        )
    except ecs.exceptions.ClientError as e:
        if "ServiceNotFoundException" in str(e):
            click.echo(f"----- Service '{service_name}' not found. You may need to create it manually.")
            click.echo("----- Logic to create a new service is not implemented. Please configure subnet, security group, and ALB target group as needed.")
            return
        else:
            click.echo(f"----- Failed to update or create the ECS service: {e}")
            return

    click.echo("----- Waiting for the ECS service deployment to stabilize...")
    while True:
        res = ecs.describe_services(cluster=cluster_name, services=[service_name])
        deployments = res["services"][0]["deployments"]
        primary = next((d for d in deployments if d["status"] == "PRIMARY"), None)
        if primary and primary["desiredCount"] == primary["runningCount"] and primary["pendingCount"] == 0:
            click.echo("----- The service is now stable.")
            break
        click.echo(f"----- Deployment status: {primary['runningCount']} running / {primary['desiredCount']} desired")
        time.sleep(5)

    history = []
    if versionjson_path.exists():
        with open(versionjson_path) as vf:
            version_data = json.load(vf)
            history = version_data.get("history", [])

    version_entry = {"version": version, "revision": revision}
    version_data = {"latest_version": version, "history": history + [version_entry]}

    with open(versionjson_path, "w") as vf:
        json.dump(version_data, vf, indent=2)

    click.echo("----- The 'version.json' file has been updated.")

    try:
        alb_name = f"{ENV}-alb"
        albs = elbv2.describe_load_balancers(Names=[alb_name])
        alb_dns = albs["LoadBalancers"][0]["DNSName"]
        website_url = f"http://{alb_dns}"
        click.echo(f"----- Your application is now live at: {website_url}")
        return website_url
    except Exception as e:
        click.echo(f"----- Could not retrieve the Application Load Balancer DNS: {e}")
        return