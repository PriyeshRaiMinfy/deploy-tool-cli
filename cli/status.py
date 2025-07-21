import click
import json
import subprocess
from pathlib import Path
import paramiko
import time
import os

# Path to the root of your CLI tool project
CLI_ROOT = Path(__file__).resolve().parents[1]

def get_terraform_outputs(tf_dir):
    """Get outputs from terraform state."""
    try:
        output = subprocess.check_output(['terraform', 'output', '-json'], cwd=tf_dir)
        return json.loads(output)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        click.echo(f"❌ Error getting terraform output: {e}")
        return None

@click.command(name="setup-monitoring")
@click.option('--env', default='dev', type=click.Choice(['dev', 'prod']), help='Environment to set up monitoring for.')
@click.option('--ssh-key', 'ssh_key_path', required=True, type=click.Path(exists=True), help='Path to your SSH private key for the monitoring EC2 instance.')
def setup_monitoring_command(env, ssh_key_path):
    """
    Sets up the monitoring stack on the dedicated EC2 instance.
    This command should be run AFTER 'terraform apply'.
    """
    tf_dir = CLI_ROOT / 'terraform' / env
    click.echo(f"Reading Terraform outputs from: {tf_dir}")
    
    outputs = get_terraform_outputs(tf_dir)
    if not outputs:
        click.echo("❌ Could not read terraform outputs. Did you run 'terraform apply'?")
        return

    try:
        monitoring_ip = outputs['monitoring_instance_ip']['value']
        frontend_url = outputs['frontend_url']['value']
    except KeyError as e:
        click.echo(f"❌ Missing required output ({e}) from Terraform. Check your outputs.tf file.")
        return

    click.echo(f"✅ Monitoring Instance IP: {monitoring_ip}")
    click.echo(f"✅ Frontend URL to monitor: {frontend_url}")

    # --- 1. Prepare Prometheus Config ---
    prometheus_template_path = CLI_ROOT / 'monitoring' / 'prometheus' / 'prometheus.yml'
    with open(prometheus_template_path, 'r') as f:
        prometheus_config = f.read()
    
    prometheus_config = prometheus_config.replace('http://placeholder.url', frontend_url)
    
    final_prometheus_path = CLI_ROOT / 'monitoring' / 'prometheus' / 'prometheus.yml.final'
    with open(final_prometheus_path, 'w') as f:
        f.write(prometheus_config)

    # --- 2. Connect via SSH and Deploy ---
    click.echo(f"🔑 Connecting to {monitoring_ip} via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(monitoring_ip, username='ec2-user', key_filename=ssh_key_path)
        sftp = ssh.open_sftp()

        click.echo("⬆️  Uploading monitoring configuration files...")
        remote_base_dir = '/home/ec2-user/monitoring'

        local_monitoring_dir = CLI_ROOT / 'monitoring'
        for root, dirs, files in os.walk(local_monitoring_dir):
            # Create remote directories
            for dirname in dirs:
                remote_path = os.path.join(remote_base_dir, os.path.relpath(os.path.join(root, dirname), local_monitoring_dir)).replace("\\", "/")
                try:
                    sftp.stat(remote_path)
                except FileNotFoundError:
                    sftp.mkdir(remote_path)

            # Upload files
            for filename in files:
                local_path = os.path.join(root, filename)
                remote_path = os.path.join(remote_base_dir, os.path.relpath(local_path, local_monitoring_dir)).replace("\\", "/")
                
                # Use the modified prometheus config
                if 'prometheus.yml' in str(local_path) and not str(local_path).endswith('.final'):
                    sftp.put(str(final_prometheus_path), remote_path)
                elif not str(local_path).endswith('.final'):
                     sftp.put(local_path, remote_path)

        click.echo("✅ All files uploaded successfully.")

        # --- 4. Run Docker Compose ---
        click.echo("🚀 Starting monitoring stack with Docker Compose...")
        # CORRECTED: Use 'docker compose' (with a space) for V2
        stdin, stdout, stderr = ssh.exec_command(f'cd {remote_base_dir} && docker compose up -d')
        
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            click.echo("🎉 Monitoring stack deployed successfully!")
            click.echo(f"View your Grafana dashboard at: http://{monitoring_ip}:3000")
            click.echo("(Login with admin/admin, you will be prompted to change the password)")
        else:
            click.echo("❌ Failed to start Docker Compose stack. Error:")
            click.echo(stderr.read().decode())

    except Exception as e:
        click.echo(f"❌ An error occurred during SSH deployment: {e}")
    finally:
        if ssh:
            ssh.close()
        if final_prometheus_path.exists():
            final_prometheus_path.unlink()
