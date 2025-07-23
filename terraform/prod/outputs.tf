output "ecs_cluster_name" {
  description = "The name of the ECS cluster."
  # Incorrect: value = aws_ecs_cluster.prod_cluster.name
  value = aws_ecs_cluster.cluster.name # Corrected to use local name "cluster"
}

output "vpc_id" {
  description = "The ID of the VPC."
  # Incorrect: value = aws_vpc.prod_vpc.id
  value = aws_vpc.main.id # Corrected to use local name "main"
}

output "subnet_ids" {
  description = "The IDs of the public subnets."
  # Incorrect: value = [aws_subnet.prod_subnet_1.id, aws_subnet.prod_subnet_2.id]
  value = [aws_subnet.public_1.id, aws_subnet.public_2.id] # Corrected to use "public_1" and "public_2"
}

output "security_group_id" {
  description = "The ID of the ECS security group."
  # Incorrect: value = aws_security_group.prod_sg.id
  value = aws_security_group.ecs_sg.id # Corrected to use local name "ecs_sg"
}