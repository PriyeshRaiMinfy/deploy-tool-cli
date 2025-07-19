# output "ecr_repo_url" {
#   value = aws_ecr_repository.prod_repo.repository_url
# }

output "ecs_cluster_name" {
  value = aws_ecs_cluster.prod_cluster.name
}

output "vpc_id" {
  value = aws_vpc.prod_vpc.id
}

output "subnet_ids" {
  value = [aws_subnet.prod_subnet_1.id, aws_subnet.prod_subnet_2.id]
}

output "security_group_id" {
  value = aws_security_group.prod_sg.id
}
