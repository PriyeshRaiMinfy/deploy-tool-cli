import boto3
import json
import click
import webbrowser

@click.command(name="status")
def status_command():
    click.echo("📊 Checking deployment status...")

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

    # Fetch ECS service info
    response = ecs.describe_services(cluster=cluster_name, services=[service_name])
    services = response["services"]

    if not services or services[0]["status"] != "ACTIVE":
        click.echo("❌ ECS service not running or not found.")
        return

    click.echo(f"✅ ECS service '{service_name}' is active.")

    # Fetch Load Balancer DNS name
    target_group_arn = services[0]["loadBalancers"][0]["targetGroupArn"]
    tg_response = elbv2.describe_target_groups(TargetGroupArns=[target_group_arn])
    lb_arn = tg_response["TargetGroups"][0]["LoadBalancerArns"][0]

    lb_response = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])
    dns_name = lb_response["LoadBalancers"][0]["DNSName"]

    grafana_url = f"http://{dns_name}/grafana"

    click.echo(f"🌐 Grafana Dashboard: {grafana_url}/login")
    webbrowser.open(grafana_url)
