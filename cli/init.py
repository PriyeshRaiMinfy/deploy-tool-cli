import os
import json
from pathlib import Path
import click

@click.command(name='init')
def init_command():
    """
    Detects frontend framework and sets up deployment config + Dockerfile
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

    # 👇 Hardcoded or dynamically resolved path to your CLI root folder
    # Update this path to your actual CLI tool location during development
    cli_project_root = "C:\\Users\\Minfy\\Desktop\\frontend-deployer-cli"

    # Save config
    deploy_config = {
        "framework": framework,
        "cli_project_root": cli_project_root
    }
# 
    if framework == "react":
        deploy_config["build_command"] = "npm run build"
        deploy_config["output_dir"] = "dist"
    elif framework == "nextjs":
        deploy_config["build_command"] = "npm run build"
        deploy_config["output_dir"] = ".next"  # or "out" for static export
    else:
        deploy_config["build_command"] = None
        deploy_config["output_dir"] = "."
# 
#   savin the configurations
    with open(config_path, "w") as f:
        json.dump(deploy_config, f, indent=2)

    click.echo(f"✅ Detected framework: {framework}")
    click.echo("✅ Created .deployconfig.json")

    # Auto-generate Dockerfile if not present
    if dockerfile_path.exists():
        click.echo("📦 Dockerfile already exists, skipping auto-generation.")
        return

    dockerfile_content = ""
    if framework == "static":
        dockerfile_content = """\
FROM nginx:alpine

# Clean default nginx files
RUN rm -rf /usr/share/nginx/html/*

# Copy only necessary static files (you can adjust these as needed)
COPY index.html /usr/share/nginx/html/

# Optional: If you have a static folder with CSS/JS/assets
# COPY static/ /usr/share/nginx/html/static/

# Expose the port nginx serves
EXPOSE 80

# Add healthcheck for ECS
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \\
    CMD wget --spider -q http://localhost || exit 1
"""

    elif framework == "react":
        dockerfile_content = """
# Stage 1: Build
FROM node:20 AS builder
WORKDIR /app

# First copy only package files for clean npm install
COPY package*.json ./
RUN npm install

# Now copy everything else except what's in .dockerignore
COPY . .

# Clean old build if any, and run fresh build
RUN rm -rf dist && npm run build && ls -al dist

# Stage 2: Serve
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Clean default nginx folder
RUN rm -rf ./*

# Copy fresh dist from builder
COPY --from=builder /app/dist ./

# Custom nginx config
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
        click.echo("✅ Auto-generated Dockerfile for your project 🎉")
