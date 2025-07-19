variable "aws_region" {
  type        = string
  description = "AWS region"
}

variable "aws_profile" {
  type        = string
  description = "AWS SSO profile name"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for VPC"
}

variable "subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for subnets"
}

variable "ecr_repo_name" {
  type        = string
  description = "ECR repo name"
}

variable "ecs_cluster_name" {
  type        = string
  description = "ECS cluster name"
}
