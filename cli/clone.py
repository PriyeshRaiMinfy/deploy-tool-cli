import os
import click
from git import Repo
from pathlib import Path

@click.command(name="clone")
@click.argument("repo_url")
@click.option("--dir", "target_dir", default="cloned-repo", help="Target directory to clone into")
def clone_command(repo_url, target_dir):
    """Clone a Git repository into the root project directory."""
    root_dir = Path.cwd()
    destination = root_dir / target_dir

    if destination.exists():
        click.echo(f"⚠️ Directory '{target_dir}' already exists.")
        return

    click.echo(f"🔄 Cloning {repo_url} into {destination}...")
    try:
        Repo.clone_from(repo_url, destination)
        # click.echo("✅ Clone successful.")
        click.echo(f"✅ Clone successful. Run the following to enter the directory:\n  cd {target_dir}")

    except Exception as e:
        click.echo(f"❌ Failed to clone repo: {str(e)}")
