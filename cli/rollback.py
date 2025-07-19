import click
import subprocess
import json
import os
from cli.config import load_config

@click.command(name='rollback')  # ✅ Register with CLI as "rollback"
@click.option('--version', required=True, help='Version to rollback to (e.g., v1, v2)')
def rollback_command(version):
    """
    Roll back the ECS service to a previously deployed task definition version.
    """
    config = load_config()
    aws_profile = config['aws_profile']
    region = config['aws_region']
    environment = config['environment']
    cluster_name = f"{environment}-ecs-cluster"
    service_name = f"{environment}-frontend-service"

    # ✅ Ensure version.json file exists
    version_file = "version.json"
    if not os.path.exists(version_file):
        click.echo("❌ version.json not found. No versions to rollback.")
        return

    with open(version_file) as f:
        versions = json.load(f)

    if version not in versions:
        click.echo(f"❌ Version '{version}' not found in version.json.")
        return

    task_def_arn = versions[version]

    # ✅ Update ECS service with selected version
    try:
        subprocess.run(
            [
                "aws", "ecs", "update-service",
                "--cluster", cluster_name,
                "--service", service_name,
                "--task-definition", task_def_arn,
                "--region", region,
                "--profile", aws_profile
            ],
            check=True
        )
        click.echo(f"🔁 Rolled back ECS service to version '{version}' with task definition: {task_def_arn}")
    except subprocess.CalledProcessError:
        click.echo("❌ Rollback failed. Check AWS CLI or task definition ARN.")
