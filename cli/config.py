import os
import json
import click
import boto3

@click.command(name='config')
def config_command():
    """Generates .awsconfig.json with default AWS config values, with optional environment selection."""

    # Default values
    profile = "Priyesh"
    region = "ap-south-1"

    # Ask for environment, default to 'dev'
    environment = click.prompt(
        "Choose environment", 
        type=click.Choice(['dev', 'prod']), 
        default='dev'
    )

    try:
        # Create boto3 session using profile and region
        session = boto3.Session(profile_name=profile, region_name=region)
        sts = session.client("sts")
        account_id = sts.get_caller_identity()["Account"]
    except Exception as e:
        click.echo(f"❌ Error fetching account ID: {e}")
        return

    # Final config data
    config_data = {
        "aws_profile": profile,
        "region": region,
        "environment": environment,
        "aws_account_id": int(account_id)
    }

    # Write the final config data to file -> .awsconfig.json:::
    with open(".awsconfig.json", "w") as f:
        json.dump(config_data, f, indent=2)
    # click.echo("✅ Deployment initialized in the ", f" {environment}", " environment:")
    click.echo("✅ .awsconfig.json created with:")
    # click.echo(json.dumps(config_data, indent=2))


def load_config():
    """Loads settings from .awsconfig.json and returns as a dictionary."""
    config_path = ".awsconfig.json"
    if not os.path.exists(config_path):
        raise FileNotFoundError("❌ .awsconfig.json not found. Please run 'deploy-tool config' first.")
    with open(config_path, "r") as f:
        return json.load(f)
