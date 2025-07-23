import click
import json
import subprocess
from pathlib import Path
import paramiko
import time

# Define the absolute path to your project root to avoid path errors.
PROJECT_ROOT = Path("C:/Users/Minfy/Desktop/frontend-deployer-cli")
# PROJECT_ROOT = Path.cwd().parent  # Assuming this script is in the 'cli' folder, this will go one level up to the project root.
# Define the absolute path to your SSH key.
SSH_KEY_PATH = "C:/Users/Minfy/Downloads/monitoring-key.pem"


def get_terraform_outputs(tf_dir):
    """Get outputs from terraform state."""
    if not tf_dir.exists():
        click.secho(f"Terraform directory not found at: {tf_dir}")
        return None
    try:
        output = subprocess.check_output(['terraform', 'output', '-json'], cwd=tf_dir, stderr=subprocess.PIPE)
        return json.loads(output)
    except FileNotFoundError:
        click.secho("---- Error: 'terraform' command not found. Is Terraform installed and in your PATH?")
        return None
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode()
        click.secho(f"---- Error getting terraform output. Did you run 'terraform apply' in the correct directory?")
        click.echo(f"Details: {error_message.strip()}")
        return None

# The --env option has been removed
@click.command(name="setup-monitoring")
def setup_monitoring_command():
    """
    Sets up the monitoring stack on the dedicated EC2 instance.
    This command should be run AFTER 'terraform apply'.
    """
    # The path is now hardcoded to the 'dev' environment
    tf_dir = PROJECT_ROOT / 'terraform' / 'dev'
    click.echo(f"Reading Terraform outputs from: {tf_dir}")
    
    outputs = get_terraform_outputs(tf_dir)
    if not outputs:
        return

    try:
        monitoring_ip = outputs['monitoring_instance_ip']['value']
        frontend_url = outputs['frontend_url']['value']
    except KeyError as e:
        click.secho(f"---- Missing required output ({e}) from Terraform. Check your outputs.tf file.")
        return

    click.secho(f"✅ Monitoring Instance IP: {monitoring_ip}")
    # click.secho(f"✅ Frontend URL to monitor: {frontend_url}")

    # --- Prepare Prometheus Config ---
    prometheus_template_path = PROJECT_ROOT / 'monitoring' / 'prometheus' / 'prometheus.yml'
    with open(prometheus_template_path, 'r') as f:
        prometheus_config = f.read().replace('http://placeholder.url', frontend_url)
    
    final_prometheus_path = PROJECT_ROOT / 'monitoring' / 'prometheus' / 'prometheus.yml.final'
    with open(final_prometheus_path, 'w') as f:
        f.write(prometheus_config)

    # --- Connect via SSH and Deploy ---
    click.echo(f"---- Connecting to {monitoring_ip} via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(monitoring_ip, username='ec2-user', key_filename=SSH_KEY_PATH)
        click.secho("---- SSH connection established.")
        
        sftp = ssh.open_sftp()
        
        click.echo("⬆️  Uploading monitoring configuration files...")
        remote_base_dir = '/home/ec2-user/monitoring'
        
        sftp.put(str(PROJECT_ROOT / 'monitoring' / 'docker-compose.yml'), f'{remote_base_dir}/docker-compose.yml')
        sftp.put(str(final_prometheus_path), f'{remote_base_dir}/prometheus/prometheus.yml')
        sftp.put(str(PROJECT_ROOT / 'monitoring' / 'blackbox' / 'config.yml'), f'{remote_base_dir}/blackbox/config.yml')
        sftp.put(str(PROJECT_ROOT / 'monitoring' / 'grafana' / 'provisioning' / 'datasources' / 'datasource.yml'), f'{remote_base_dir}/grafana/provisioning/datasources/datasource.yml')
        sftp.put(str(PROJECT_ROOT / 'monitoring' / 'grafana' / 'provisioning' / 'dashboards' / 'dashboard.yml'), f'{remote_base_dir}/grafana/provisioning/dashboards/dashboard.yml')
        sftp.put(str(PROJECT_ROOT / 'monitoring' / 'grafana' / 'dashboards' / 'blackbox.json'), f'{remote_base_dir}/grafana/dashboards/blackbox.json')
        # click.secho("✅ All files uploaded successfully.")

        click.echo("---- Starting monitoring stack with Docker Compose...")
        compose_command = f'cd {remote_base_dir} && /usr/local/lib/docker/cli-plugins/docker-compose up -d'
        stdin, stdout, stderr = ssh.exec_command(compose_command)
        
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            click.secho("---- Monitoring stack deployed successfully!")
            click.echo(f"✅ View your Grafana dashboard at: http://{monitoring_ip}:3000")
        else:
            click.secho("---- Failed to start Docker Compose stack. Error:")
            click.echo(stderr.read().decode())

    except Exception as e:
        click.secho(f"---- An error occurred during SSH deployment: {e}")
    finally:
        if 'ssh' in locals() and ssh.get_transport() and ssh.get_transport().is_active():
            ssh.close()
        if final_prometheus_path.exists():
            final_prometheus_path.unlink()