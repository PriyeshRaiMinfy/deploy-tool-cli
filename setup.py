from setuptools import setup, find_packages

setup(
    name='frontend-deployer-cli',  # Name of your CLI package
    version='0.1.0',               # Versioning
    packages=find_packages(),      # Finds all folders with __init__.py
    install_requires=[
        'click'                    # We are using Click for CLI commands
    ],
    entry_points={
        'console_scripts': [
            # It is mapped to a functionin main.py -> cli/main.py
            'deploy-tool=cli.main:cli'  # Command to run in terminal: deploy-tool
        ]
    }
)
