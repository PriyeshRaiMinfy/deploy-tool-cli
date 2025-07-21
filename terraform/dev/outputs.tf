  # output "ecr_repo_url" {
  #     value = aws_ecr_repository.repo.repository_url
  # }

  output "ecs_cluster_name" {
      value = aws_ecs_cluster.cluster.name
  }

  # output "vpc_id" {
  #     value = aws_vpc.main.id
  # }

  # output "subnet_ids" {
  #     value = [aws_subnet.public_1.id, aws_subnet.public_2.id]
  # }

  # output "ecs_security_group_id" {
  #     value = aws_security_group.ecs_sg.id
  # }
  # -------------------------------------------------
  output "frontend_url" {
    value = "http://${aws_lb.frontend_alb.dns_name}"
  }
  output "grafana_dashboard_url" {
    value = "http://${aws_lb.frontend_alb.dns_name}/grafana"
  }
output "grafana_url" {
  description = "The URL for the Grafana dashboard"
  value       = "http://${aws_instance.monitoring_instance.public_ip}:3000"
}




output "monitoring_instance_ip" {
  description = "The public IP of the monitoring EC2 instance"
  value       = aws_instance.monitoring_instance.public_ip
}