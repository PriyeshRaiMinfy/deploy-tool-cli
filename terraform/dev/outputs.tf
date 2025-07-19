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
