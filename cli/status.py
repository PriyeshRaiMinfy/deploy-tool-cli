# import boto3
# import click
# import json
# import os
# import time
# import webbrowser
# from datetime import datetime, timedelta

# @click.command(name="status")
# def status_command():
#     click.echo("📊 Checking deployment status...")

#     if not os.path.exists(".awsconfig.json"):
#         click.echo("❌ .awsconfig.json file not found. Run `deploy-tool config`.")
#         return

#     with open(".awsconfig.json") as f:
#         config = json.load(f)

#     region = config["region"]
#     profile = config["aws_profile"]
#     env = config["environment"]

#     session = boto3.Session(profile_name=profile, region_name=region)
#     ecs = session.client("ecs")
#     elbv2 = session.client("elbv2")
#     ssm = session.client("ssm")
#     cloudwatch = session.client("cloudwatch")

#     # Re-run SSM command to upload provisioning files
#     click.echo("🛰️ Uploading monitoring config to EFS via SSM...")
#     instances = ssm.describe_instance_information()["InstanceInformationList"]
#     ec2_instance_id = next((i["InstanceId"] for i in instances if i["PlatformName"] == "Amazon Linux"), None)

#     if ec2_instance_id:
#         response = ssm.send_command(
#             InstanceIds=[ec2_instance_id],
#             DocumentName=f"{env}-upload-efs"
#         )
#         command_id = response["Command"]["CommandId"]

#         # Wait for completion
#         for _ in range(10):
#             time.sleep(5)
#             output = ssm.get_command_invocation(CommandId=command_id, InstanceId=ec2_instance_id)
#             if output["Status"] in ["Success", "Failed", "Cancelled", "TimedOut"]:
#                 break

#         if output["Status"] != "Success":
#             click.echo(f"❌ SSM failed: {output['Status']}")
#             return

#         click.echo("✅ Config uploaded to EFS successfully.")
#     else:
#         click.echo("❌ Could not find EC2 instance with SSM agent.")
#         return

#     # ECS Health Check
#     cluster_name = f"{env}-ecs-cluster"
#     service_name = f"{env}-frontend-service"
#     service_desc = ecs.describe_services(cluster=cluster_name, services=[service_name])["services"][0]

#     if service_desc["status"] != "ACTIVE":
#         click.echo("❌ ECS service not running.")
#         return
#     click.echo("✅ ECS service is active.")

#     # Load Balancer URL
#     tg_arn = service_desc["loadBalancers"][0]["targetGroupArn"]
#     lb_arn = elbv2.describe_target_groups(TargetGroupArns=[tg_arn])["TargetGroups"][0]["LoadBalancerArns"][0]
#     dns_name = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])["LoadBalancers"][0]["DNSName"]
#     grafana_url = f"http://{dns_name}/grafana"

#     # ✅ CloudWatch CPU metric (last 5 minutes)
#     service_name = service_desc["serviceName"]
#     cluster_name = service_desc["clusterArn"].split("/")[-1]
#     metric = cloudwatch.get_metric_statistics(
#         Namespace='AWS/ECS',
#         MetricName='CPUUtilization',
#         Dimensions=[
#             {'Name': 'ClusterName', 'Value': cluster_name},
#             {'Name': 'ServiceName', 'Value': service_name},
#         ],
#         StartTime=datetime.utcnow() - timedelta(minutes=10),
#         EndTime=datetime.utcnow(),
#         Period=300,
#         Statistics=['Average'],
#         Unit='Percent'
#     )

#     datapoints = metric.get('Datapoints', [])
#     if datapoints:
#         latest = sorted(datapoints, key=lambda x: x["Timestamp"])[-1]
#         cpu = round(latest["Average"], 2)
#         click.echo(f"📈 ECS CPU Utilization (avg, last 5 min): {cpu}%")
#     else:
#         click.echo("⚠️ No CPU data available from CloudWatch yet.")

#     click.echo(f"🌐 Grafana Dashboard: {grafana_url}/login")
#     webbrowser.open(grafana_url)


import click
import requests
import json
import time

@click.command(name="display")
def display_command():
    """
    Black-Box Method
    """
    click.echo("📦 Checking deployment status...\n")

    # Normally read from Terraform output or config
    with open(".awsconfig.json") as f:
        config = json.load(f)

    env = config.get("env", "dev")
    alb_url = "http://dev-alb-578605638.ap-south-1.elb.amazonaws.com"  # Replace with actual DNS or Terraform output

    endpoints = {
        "App": alb_url,
        "Grafana": f"{alb_url}/grafana"
    }

    for name, url in endpoints.items():
        try:
            start = time.time()
            response = requests.get(url, timeout=5)
            duration = int((time.time() - start) * 1000)
            status = f"{response.status_code} OK" if response.ok else f"{response.status_code} Error"
            click.echo(f"✅ {name} Response: {status} (in {duration}ms)")
        except Exception as e:
            click.echo(f"❌ {name} Check Failed: {e}")

    # (Optional) Load deployed version
    try:
        with open("version.json") as f:
            version_info = json.load(f)
            current = version_info.get("current", {})
            click.echo(f"\n🚀 Deployed Version: {current.get('version')} (Image: {current.get('image')})")
    except FileNotFoundError:
        click.echo("\n⚠️ Version file not found")

