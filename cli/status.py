import boto3
import json
import yaml
import os
import click
import webbrowser
from pathlib import Path

@click.command(name="status")
def status_command():
    click.echo("📊 Checking deployment status...")
    """Check ECS deployment status and monitoring dashboard"""
    if not os.path.exists(".awsconfig.json"):
        click.echo("❌ .awsconfig.json file not found. Run `deploy-tool config` to generate it.")
        return

    # Load config
    with open(".awsconfig.json") as f:
        config = json.load(f)

    region = config["region"]
    profile = config["aws_profile"]
    env = config["environment"]

    session = boto3.Session(profile_name=profile, region_name=region)
    ecs = session.client("ecs")
    elbv2 = session.client("elbv2")

    cluster_name = f"{env}-ecs-cluster"
    service_name = f"{env}-frontend-service"

    # Update Grafana configuration files
    update_grafana_configs(env, region)

    # Upload configuration to EFS via EC2
    upload_configs_to_efs(session, env)

    # Fetch ECS service info
    try:
        response = ecs.describe_services(cluster=cluster_name, services=[service_name])
        services = response["services"]

        if not services or services[0]["status"] != "ACTIVE":
            click.echo("❌ ECS service not running or not found.")
            return

        click.echo(f"✅ ECS service '{service_name}' is active.")

        # Fetch Load Balancer DNS name
        if services[0].get("loadBalancers"):
            target_group_arn = services[0]["loadBalancers"][0]["targetGroupArn"]
            tg_response = elbv2.describe_target_groups(TargetGroupArns=[target_group_arn])
            lb_arn = tg_response["TargetGroups"][0]["LoadBalancerArns"][0]

            lb_response = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])
            dns_name = lb_response["LoadBalancers"][0]["DNSName"]

            grafana_url = f"http://{dns_name}/grafana"
            click.echo(f"🌐 Grafana Dashboard: {grafana_url}")
            click.echo("👤 Username: Priyesh")
            click.echo("🔐 Password: Delhi")
            webbrowser.open(grafana_url)
        else:
            click.echo("⚠️  No load balancer configured.")

    except Exception as e:
        click.echo(f"❌ Error fetching service info: {e}")

def update_grafana_configs(env, region):
    """Update Grafana configuration files with correct paths and Prometheus integration"""
    click.echo("🔧 Updating Grafana configuration files...")
    
    # Create infra directory if it doesn't exist
    infra_dir = Path("infra")
    grafana_dir = infra_dir / "grafana" / "provisioning"
    dashboards_dir = grafana_dir / "dashboards"
    datasources_dir = grafana_dir / "datasources"
    
    # Ensure directories exist
    dashboards_dir.mkdir(parents=True, exist_ok=True)
    datasources_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create datasources.yaml with CloudWatch and Prometheus
    datasources_config = {
        "apiVersion": 1,
        "datasources": [
            {
                "name": "CloudWatch",
                "type": "cloudwatch",
                "access": "proxy",
                "jsonData": {
                    "authType": "default",
                    "defaultRegion": region
                },
                "isDefault": True,
                "editable": True,
                "uid": "cloudwatch-datasource"
            },
            {
                "name": "Prometheus",
                "type": "prometheus",
                "access": "proxy",
                "url": "http://localhost:9090",
                "isDefault": False,
                "editable": True,
                "uid": "prometheus-datasource",
                "jsonData": {
                    "httpMethod": "POST",
                    "queryTimeout": "60s",
                    "timeInterval": "5s"
                }
            }
        ]
    }

    with open(datasources_dir / "datasources.yaml", 'w') as f:
        yaml.dump(datasources_config, f, default_flow_style=False)

    # 2. Create dashboards.yaml pointing to the correct EFS path
    dashboards_config = {
        "apiVersion": 1,
        "providers": [
            {
                "name": "default",
                "orgId": 1,
                "folder": "",
                "type": "file",
                "disableDeletion": False,
                "updateIntervalSeconds": 10,
                "allowUiUpdates": True,
                "options": {
                    "path": "/mnt/efs/grafana/provisioning/dashboards"
                }
            }
        ]
    }

    with open(dashboards_dir / "dashboards.yaml", 'w') as f:
        yaml.dump(dashboards_config, f, default_flow_style=False)

    # 3. Create comprehensive ECS monitoring dashboard
    dashboard_json = create_ecs_dashboard(env, region)
    
    with open(dashboards_dir / "ecs-monitoring.json", 'w') as f:
        json.dump(dashboard_json, f, indent=2)

    # 4. Create dashboard provider config
    dashboard_provider = {
        "apiVersion": 1,
        "providers": [
            {
                "name": "ECS Monitoring",
                "orgId": 1,
                "folder": "",
                "type": "file",
                "disableDeletion": False,
                "editable": True,
                "options": {
                    "path": "/mnt/efs/grafana/provisioning/dashboards/ecs-monitoring.json"
                }
            }
        ]
    }

    with open(grafana_dir / "dashboard-providers.yaml", 'w') as f:
        yaml.dump(dashboard_provider, f, default_flow_style=False)

    click.echo("✅ Grafana configuration files updated successfully")

def create_ecs_dashboard(env, region):
    """Create a comprehensive ECS monitoring dashboard"""
    return {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": "-- Grafana --",
                    "enable": True,
                    "hide": True,
                    "iconColor": "rgba(0, 211, 255, 1)",
                    "name": "Annotations & Alerts",
                    "type": "dashboard"
                }
            ]
        },
        "editable": True,
        "gnetId": None,
        "graphTooltip": 0,
        "id": None,
        "links": [],
        "panels": [
            {
                "datasource": {
                    "type": "cloudwatch",
                    "uid": "cloudwatch-datasource"
                },
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisLabel": "",
                            "axisPlacement": "auto",
                            "barAlignment": 0,
                            "drawStyle": "line",
                            "fillOpacity": 10,
                            "gradientMode": "none",
                            "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                            "lineInterpolation": "linear",
                            "lineWidth": 1,
                            "pointSize": 5,
                            "scaleDistribution": {"type": "linear"},
                            "showPoints": "auto",
                            "spanNulls": False,
                            "stacking": {"group": "A", "mode": "none"},
                            "thresholdsStyle": {"mode": "off"}
                        },
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "red", "value": 80}
                            ]
                        },
                        "unit": "percent"
                    },
                    "overrides": []
                },
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "id": 1,
                "options": {
                    "legend": {"calcs": [], "displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "single", "sort": "none"}
                },
                "targets": [
                    {
                        "alias": "CPU Utilization",
                        "datasource": {"type": "cloudwatch", "uid": "cloudwatch-datasource"},
                        "dimensions": {
                            "ClusterName": f"{env}-ecs-cluster",
                            "ServiceName": f"{env}-frontend-service"
                        },
                        "expression": "",
                        "id": "",
                        "matchExact": True,
                        "metricName": "CPUUtilization",
                        "namespace": "AWS/ECS",
                        "period": "300",
                        "refId": "A",
                        "region": region,
                        "statistics": ["Average"]
                    }
                ],
                "title": "ECS Service CPU Utilization",
                "type": "timeseries"
            },
            {
                "datasource": {
                    "type": "cloudwatch",
                    "uid": "cloudwatch-datasource"
                },
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisLabel": "",
                            "axisPlacement": "auto",
                            "barAlignment": 0,
                            "drawStyle": "line",
                            "fillOpacity": 10,
                            "gradientMode": "none",
                            "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                            "lineInterpolation": "linear",
                            "lineWidth": 1,
                            "pointSize": 5,
                            "scaleDistribution": {"type": "linear"},
                            "showPoints": "auto",
                            "spanNulls": False,
                            "stacking": {"group": "A", "mode": "none"},
                            "thresholdsStyle": {"mode": "off"}
                        },
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "red", "value": 80}
                            ]
                        },
                        "unit": "percent"
                    },
                    "overrides": []
                },
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                "id": 2,
                "options": {
                    "legend": {"calcs": [], "displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "single", "sort": "none"}
                },
                "targets": [
                    {
                        "alias": "Memory Utilization",
                        "datasource": {"type": "cloudwatch", "uid": "cloudwatch-datasource"},
                        "dimensions": {
                            "ClusterName": f"{env}-ecs-cluster",
                            "ServiceName": f"{env}-frontend-service"
                        },
                        "expression": "",
                        "id": "",
                        "matchExact": True,
                        "metricName": "MemoryUtilization",
                        "namespace": "AWS/ECS",
                        "period": "300",
                        "refId": "A",
                        "region": region,
                        "statistics": ["Average"]
                    }
                ],
                "title": "ECS Service Memory Utilization",
                "type": "timeseries"
            },
            {
                "datasource": {
                    "type": "cloudwatch",
                    "uid": "cloudwatch-datasource"
                },
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "green", "value": 1}
                            ]
                        }
                    },
                    "overrides": []
                },
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                "id": 3,
                "options": {
                    "orientation": "auto",
                    "reduceOptions": {
                        "values": False,
                        "calcs": ["lastNotNull"],
                        "fields": ""
                    },
                    "showThresholdLabels": False,
                    "showThresholdMarkers": True,
                    "text": {}
                },
                "pluginVersion": "8.0.0",
                "targets": [
                    {
                        "alias": "Running Tasks",
                        "datasource": {"type": "cloudwatch", "uid": "cloudwatch-datasource"},
                        "dimensions": {
                            "ClusterName": f"{env}-ecs-cluster",
                            "ServiceName": f"{env}-frontend-service"
                        },
                        "expression": "",
                        "id": "",
                        "matchExact": True,
                        "metricName": "RunningTaskCount",
                        "namespace": "AWS/ECS",
                        "period": "300",
                        "refId": "A",
                        "region": region,
                        "statistics": ["Average"]
                    }
                ],
                "title": "Running Tasks Count",
                "type": "gauge"
            },
            {
                "datasource": {
                    "type": "cloudwatch",
                    "uid": "cloudwatch-datasource"
                },
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisLabel": "",
                            "axisPlacement": "auto",
                            "barAlignment": 0,
                            "drawStyle": "line",
                            "fillOpacity": 10,
                            "gradientMode": "none",
                            "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                            "lineInterpolation": "linear",
                            "lineWidth": 1,
                            "pointSize": 5,
                            "scaleDistribution": {"type": "linear"},
                            "showPoints": "auto",
                            "spanNulls": False,
                            "stacking": {"group": "A", "mode": "none"},
                            "thresholdsStyle": {"mode": "off"}
                        },
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "red", "value": 80}
                            ]
                        },
                        "unit": "short"
                    },
                    "overrides": []
                },
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                "id": 4,
                "options": {
                    "legend": {"calcs": [], "displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "single", "sort": "none"}
                },
                "targets": [
                    {
                        "alias": "Healthy Targets",
                        "datasource": {"type": "cloudwatch", "uid": "cloudwatch-datasource"},
                        "dimensions": {
                            "TargetGroup": f"{env}-tg*",
                            "LoadBalancer": f"{env}-alb*"
                        },
                        "expression": "",
                        "id": "",
                        "matchExact": False,
                        "metricName": "HealthyHostCount",
                        "namespace": "AWS/ApplicationELB",
                        "period": "300",
                        "refId": "A",
                        "region": region,
                        "statistics": ["Average"]
                    }
                ],
                "title": "Application Load Balancer Healthy Targets",
                "type": "timeseries"
            }
        ],
        "refresh": "30s",
        "schemaVersion": 27,
        "style": "dark",
        "tags": ["ecs", "monitoring", "aws"],
        "templating": {"list": []},
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {},
        "timezone": "",
        "title": f"ECS Monitoring Dashboard - {env}",
        "uid": f"ecs-monitoring-{env}",
        "version": 1
    }

def upload_configs_to_efs(session, env):
    """Upload configuration files to EFS via EC2 instance"""
    click.echo("📤 Uploading configuration files to EFS...")
    
    ec2 = session.client("ec2")
    ssm = session.client("ssm")
    
    try:
        # Find EC2 instance with EFS mounted
        response = ec2.describe_instances(
            Filters=[
                {"Name": "tag:Environment", "Values": [env]},
                {"Name": "instance-state-name", "Values": ["running"]}
            ]
        )
        
        instance_id = None
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                instance_id = instance["InstanceId"]
                break
        
        if not instance_id:
            click.echo("⚠️  No running EC2 instance found. Please upload files manually.")
            return
        
        click.echo(f"📡 Using EC2 instance: {instance_id}")
        
        # Prepare upload commands
        infra_dir = Path("infra")
        
        commands = [
            "sudo mkdir -p /mnt/efs/grafana/provisioning/dashboards",
            "sudo mkdir -p /mnt/efs/grafana/provisioning/datasources",
            "sudo chown -R 472:472 /mnt/efs/grafana",
            "sudo chmod -R 755 /mnt/efs/grafana"
        ]
        
        # Upload datasources.yaml
        dashboards_file = infra_dir / "grafana" / "provisioning" / "dashboards" / "dashboards.yaml"
        if dashboards_file.exists():
            with open(dashboards_file, 'r') as f:
                content = f.read().replace("'", "'\"'\"'")
            commands.append(
                f"sudo tee /mnt/efs/grafana/provisioning/dashboards/dashboards.yaml > /dev/null << 'EOF'\n{content}\nEOF"
            )

        # Upload ecs-monitoring.json
        ecs_dashboard_file = infra_dir / "grafana" / "provisioning" / "dashboards" / "ecs-monitoring.json"
        if ecs_dashboard_file.exists():
            with open(ecs_dashboard_file, 'r') as f:
                content = f.read().replace("'", "'\"'\"'")
            commands.append(
                f"sudo tee /mnt/efs/grafana/provisioning/dashboards/ecs-monitoring.json > /dev/null << 'EOF'\n{content}\nEOF"
            )

        # Upload dashboard-providers.yaml
        providers_file = infra_dir / "grafana" / "provisioning" / "dashboard-providers.yaml"
        if providers_file.exists():
            with open(providers_file, 'r') as f:
                content = f.read().replace("'", "'\"'\"'")
            commands.append(
                f"sudo tee /mnt/efs/grafana/provisioning/dashboard-providers.yaml > /dev/null << 'EOF'\n{content}\nEOF"
            )

        # Run commands using SSM
        click.echo("📤 Sending commands via SSM...")
        ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
            Comment="Upload Grafana configuration files to EFS"
        )

        click.echo("✅ Configuration uploaded via SSM to EC2 instance.")
    except Exception as e:
        click.echo(f"❌ Failed to upload configs via EC2: {e}")