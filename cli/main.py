import click

# Import commands
from cli.deploy import deploy_command
from cli.init import init_command
from cli.config import config_command
# from cli.status import status_command
# from cli.populate_efs import populate_efs
from cli.rollback import rollback_command
from cli.clone import clone_command
from cli.status import display_command

@click.group()
def cli():
    """Frontend Deployer CLI Tool"""
    pass

cli.add_command(init_command)
# cli.add_command(populate_efs)
cli.add_command(config_command)
cli.add_command(deploy_command)
cli.add_command(rollback_command)
# cli.add_command(status_command)
cli.add_command(display_command)
cli.add_command(clone_command)

if __name__ == '__main__':
    cli()
