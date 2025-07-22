import click
from git import Repo
from pathlib import Path

@click.command(name="clone")
@click.argument("repo_url")
@click.option("--dir", "target_dir", default="cloned-repo", help="The target directory to clone into.")
def clone_command(repo_url, target_dir):
    """Clones a Git repository into a specified directory."""
    root_dir = Path.cwd()
    destination = root_dir / target_dir

    if destination.exists():
        click.echo(f"----- The directory '{target_dir}' already exists. Please choose a different name or remove the existing directory.", fg="purple")
        return

    click.echo(f"----- Cloning from {repo_url} into {destination}...", fg="purple")
    try:
        Repo.clone_from(repo_url, destination)
        click.echo(f"---✅ The repository was cloned successfully. You can now navigate to the new directory using:\n  cd {target_dir}", fg="purple")
    except Exception as e:
        click.echo(f"----- Failed to clone the repository: {str(e)}", fg="purple")