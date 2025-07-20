import json
import click
import subprocess
from pathlib import Path

# ✅ Hardcoded CLI project root — aligned with your structure
REPO_ROOT = Path("C:/Users/Minfy/Desktop/frontend-deployer-cli")
# REPO_ROOT = "C:/Users/Minfy/Desktop/frontend-deployer-cli"
CONFIG_PATH = REPO_ROOT / ".awsconfig.json"
# CONFIG_PATH = Path(__file__).resolve().parents[2] / ".awsconfig.json"


def populate_efs():
    """Upload monitor configs to EC2-mounted EFS"""
    click.echo("📦 Populating EFS with monitoring configs...")

    if not CONFIG_PATH.exists():
        click.echo(f"❌ Config file not found at {CONFIG_PATH}")
        return

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    ec2_ip = config.get("ec2_public_ip")
    key_path = config.get("pem_file_path")

    if not ec2_ip or not key_path:
        click.echo("❌ Missing 'ec2_public_ip' or 'pem_file_path' in config.")
        return

    files_to_upload = [
        ("infra/prometheus/prometheus.yml", "prometheus.yml"),
        ("infra/grafana/provisioning/datasources.yaml", "datasources.yaml"),
        ("infra/grafana/provisioning/dashboards.yaml", "dashboards.yaml"),
        ("infra/grafana/provisioning/dashboards/ecs-dashboard.json", "ecs-dashboard.json"),
    ]

    for rel_path, remote_name in files_to_upload:
        local_path = REPO_ROOT / rel_path
        if not local_path.exists():
            click.echo(f"⚠️  Skipping {remote_name}, file not found ➤ {local_path}")
            continue

        click.echo(f"⬆️  Uploading {remote_name}...")
        cmd = [
            "scp", "-i", key_path, str(local_path),
            f"ec2-user@{ec2_ip}:/mnt/efs/{remote_name}"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            click.echo(f"❌ Failed to upload {remote_name}:\n{result.stderr}")
        else:
            click.echo(f"✅ {remote_name} uploaded successfully!")

    click.echo("🎉 All files uploaded to EFS!")
