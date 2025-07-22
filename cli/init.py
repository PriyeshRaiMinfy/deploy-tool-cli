import os
import json
from pathlib import Path
import click

@click.command(name='init')
def init_command():
    """
    Detects the frontend framework and sets up the deployment configuration
    and a suitable Dockerfile.
    """
    cwd = Path.cwd()
    config_path = cwd / ".deployconfig.json"
    dockerfile_path = cwd / "Dockerfile"

    # Basic framework detection
    framework = "static"
    if (cwd / "package.json").exists():
        with open(cwd / "package.json") as f:
            pkg = json.load(f)
            deps = pkg.get("dependencies", {})
            if "react" in deps:
                framework = "react"
            elif "next" in deps:
                framework = "nextjs"

    # This path should point to the root folder of your CLI tool.
    # Please update this path to your actual CLI tool location.
    cli_project_root = "C:\\Users\\Minfy\\Desktop\\frontend-deployer-cli"

    # Save deployment configuration
    deploy_config = {
        "framework": framework,
        "cli_project_root": cli_project_root
    }

    if framework == "react":
        deploy_config["build_command"] = "npm run build"
        deploy_config["output_dir"] = "dist"
    elif framework == "nextjs":
        deploy_config["build_command"] = "npm run build"
        deploy_config["output_dir"] = ".next"
    else:
        deploy_config["build_command"] = None
        deploy_config["output_dir"] = "."

    # Saving the configurations
    with open(config_path, "w") as f:
        json.dump(deploy_config, f, indent=2)

    click.echo(f"---✅ Detected framework: {framework}", fg="purple")
    click.echo("---✅ Created .deployconfig.json", fg="purple")

    # Auto-generate Dockerfile if it does not already exist
    if dockerfile_path.exists():
        click.echo("----- Dockerfile already exists, skipping auto-generation.", fg="purple")
        return

    dockerfile_content = ""
    if framework == "static":
        dockerfile_content = """\
FROM nginx:alpine

# Clean default nginx files
RUN rm -rf /usr/share/nginx/html/*

# Copy necessary static files
COPY index.html /usr/share/nginx/html/

# Optional: If you have a static folder with CSS/JS/assets
# COPY static/ /usr/share/nginx/html/static/

# Expose the port nginx serves on
EXPOSE 80

# Add healthcheck for Amazon ECS
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \\
    CMD wget --spider -q http://localhost || exit 1
"""

    elif framework == "react":
        dockerfile_content = """
# Stage 1: Build the application
FROM node:20 AS builder
WORKDIR /app

# Copy package files first for dependency caching
COPY package*.json ./
RUN npm install

# Copy the rest of the application source code
COPY . .

# Create a fresh production build
RUN rm -rf dist && npm run build && ls -al dist

# Stage 2: Serve the application
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Clean the default nginx folder
RUN rm -rf ./*

# Copy the build output from the builder stage
COPY --from=builder /app/dist ./

# Use a custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""

    elif framework == "nextjs":
        dockerfile_content = """FROM node:18-alpine
WORKDIR /app
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
"""

    if dockerfile_content:
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)
        click.echo("---✅ Auto-generated a Dockerfile for your project.", fg="purple")
    click.echo("----- Now populating EFS with Prometheus/Grafana configs.", fg="purple")