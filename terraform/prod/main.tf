provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

# VPC
resource "aws_vpc" "prod_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "prod-vpc"
  }
}

# Subnets (2 public subnets)
resource "aws_subnet" "prod_subnet_1" {
  vpc_id                  = aws_vpc.prod_vpc.id
  cidr_block              = var.subnet_cidrs[0]
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags = {
    Name = "prod-subnet-1"
  }
}

resource "aws_subnet" "prod_subnet_2" {
  vpc_id                  = aws_vpc.prod_vpc.id
  cidr_block              = var.subnet_cidrs[1]
  availability_zone       = data.aws_availability_zones.available.names[1]
  map_public_ip_on_launch = true
  tags = {
    Name = "prod-subnet-2"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "prod_igw" {
  vpc_id = aws_vpc.prod_vpc.id
  tags = {
    Name = "prod-igw"
  }
}

# Route Table
resource "aws_route_table" "prod_rt" {
  vpc_id = aws_vpc.prod_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.prod_igw.id
  }
  tags = {
    Name = "prod-rt"
  }
}

resource "aws_route_table_association" "prod_subnet_1_assoc" {
  subnet_id      = aws_subnet.prod_subnet_1.id
  route_table_id = aws_route_table.prod_rt.id
}

resource "aws_route_table_association" "prod_subnet_2_assoc" {
  subnet_id      = aws_subnet.prod_subnet_2.id
  route_table_id = aws_route_table.prod_rt.id
}

# Security Group
resource "aws_security_group" "prod_sg" {
  name        = "prod-sg"
  description = "Allow HTTP and HTTPS"
  vpc_id      = aws_vpc.prod_vpc.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "prod-sg"
  }
}

# # ECR
# resource "aws_ecr_repository" "prod_repo" {
#   name = var.ecr_repo_name
# }

# ECS Cluster
resource "aws_ecs_cluster" "prod_cluster" {
  name = var.ecs_cluster_name
}

# Data for AZs
data "aws_availability_zones" "available" {}
