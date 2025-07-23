provider "aws" {
    region  = var.aws_region
    profile = var.aws_profile
}

# ------------------------------------------------------------------
# Networking
# ------------------------------------------------------------------
resource "aws_ecr_repository" "frontend_ecr" {
  name = "${var.env}-frontend-ecr"

  tags = {
    Name = "${var.env}-frontend-ecr"
    Env  = var.env
  }
}
resource "aws_vpc" "main" {
    cidr_block           = "10.0.0.0/16"
    enable_dns_hostnames = true
    enable_dns_support   = true
    tags = {
        Name = "${var.env}-vpc"
    }
}

resource "aws_subnet" "public_1" {
    vpc_id                  = aws_vpc.main.id
    cidr_block              = "10.0.1.0/24"
    availability_zone       = "ap-south-1a"
    map_public_ip_on_launch = true
    tags = {
        Name = "${var.env}-subnet-1"
    }
}

resource "aws_subnet" "public_2" {
    vpc_id                  = aws_vpc.main.id
    cidr_block              = "10.0.2.0/24"
    availability_zone       = "ap-south-1b"
    map_public_ip_on_launch = true
    tags = {
        Name = "${var.env}-subnet-2"
    }
}

resource "aws_internet_gateway" "gw" {
    vpc_id = aws_vpc.main.id
    tags = {
        Name = "${var.env}-igw"
    }
}

resource "aws_route_table" "public" {
    vpc_id = aws_vpc.main.id
    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = aws_internet_gateway.gw.id
    }
    tags = {
        Name = "${var.env}-route-table"
    }
}

resource "aws_route_table_association" "a" {
    subnet_id      = aws_subnet.public_1.id
    route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "b" {
    subnet_id      = aws_subnet.public_2.id
    route_table_id = aws_route_table.public.id
}

# ------------------------------------------------------------------
# Security Groups
# ------------------------------------------------------------------
resource "aws_security_group" "ecs_sg" {
    name        = "${var.env}-ecs-sg"
    description = "Allow HTTP from ALB"
    vpc_id      = aws_vpc.main.id

    ingress {
        description = "Allow HTTP from anywhere"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
    ingress {
        description = "SSH"
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"] # For production, restrict to your IP
    }
    ingress {
        description = "Grafana"
        from_port   = 3000
        to_port     = 3000
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
    ingress {
        description = "Prometheus"
        from_port   = 9090
        to_port     = 9090
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
    ingress {
        description = "Blackbox Exporter"
        from_port   = 9115
        to_port     = 9115
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
        Name = "${var.env}-ecs-sg"
    }
}

resource "aws_security_group" "monitoring_sg" {
    name        = "${var.env}-monitoring-sg"
    description = "Allow traffic for monitoring stack"
    vpc_id      = aws_vpc.main.id

    ingress {
        description = "Allow HTTP from anywhere"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
    ingress {
        description = "SSH"
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"] # For production, restrict to your IP
    }
    ingress {
        description = "Grafana"
        from_port   = 3000
        to_port     = 3000
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
    ingress {
        description = "Prometheus"
        from_port   = 9090
        to_port     = 9090
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
    ingress {
        description = "Blackbox Exporter"
        from_port   = 9115
        to_port     = 9115
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
    ingress {
    from_port         = 9100
    to_port           = 9100
    protocol          = "tcp"
    # security_group_id = aws_security_group.ecs_sg.id
    # source_security_group_id = aws_security_group.monitoring_sg.id
    }
    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }
    tags = {
        Name = "${var.env}-monitoring-sg"
    }
}

# ------------------------------------------------------------------
# IAM Roles
# ------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_execution_role" {
    name = "${var.env}-ecsTaskExecutionRole"
    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [{
            Action    = "sts:AssumeRole"
            Effect    = "Allow"
            Principal = { Service = "ecs-tasks.amazonaws.com" }
        }]
    })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
    role       = aws_iam_role.ecs_task_execution_role.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
    name = "${var.env}-ecs-task-role"
    assume_role_policy = jsonencode({
        Version = "2012-10-17",
        Statement = [{
            Effect    = "Allow",
            Principal = { Service = "ecs-tasks.amazonaws.com" },
            Action    = "sts:AssumeRole"
        }]
    })
}

# ------------------------------------------------------------------
# CloudWatch & ECS
# ------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ecs_logs" {
    name              = "/ecs/${var.env}-frontend"
    retention_in_days = 7
}

resource "aws_ecs_cluster" "cluster" {
    name = "${var.env}-ecs-cluster"
}

resource "aws_ecs_task_definition" "frontend_task" {
    family                   = "${var.env}-frontend-task"
    network_mode             = "awsvpc"
    requires_compatibilities = ["FARGATE"]
    cpu                      = "256"
    memory                   = "512"
    execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
    task_role_arn            = aws_iam_role.ecs_task_role.arn

    container_definitions = jsonencode([
        {
            name  = "frontend"
            image = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.env}-frontend-ecr:latest"
            portMappings = [{
                containerPort = 80
            }]
            logConfiguration = {
                logDriver = "awslogs",
                options = {
                    "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
                    "awslogs-region"        = var.aws_region
                    "awslogs-stream-prefix" = "frontend"
                }
            }
        }
    ])
}

resource "aws_ecs_service" "frontend_service" {
    name            = "${var.env}-frontend-service"
    cluster         = aws_ecs_cluster.cluster.id
    launch_type     = "FARGATE"
    task_definition = aws_ecs_task_definition.frontend_task.arn
    desired_count   = 1
    network_configuration {
        subnets         = [aws_subnet.public_1.id, aws_subnet.public_2.id]
        security_groups = [aws_security_group.ecs_sg.id]
        assign_public_ip = true
    }
    load_balancer {
        target_group_arn = aws_lb_target_group.frontend_tg.arn
        container_name   = "frontend"
        container_port   = 80
    }
    # depends_on = [
    #   aws_lb_listener.frontend_listener,
    #   aws_lb_listener_rule.grafana_listener_rule
    # ]
}

# ------------------------------------------------------------------
# ALB
# ------------------------------------------------------------------
resource "aws_lb" "frontend_alb" {
    name               = "${var.env}-alb"
    internal           = false
    load_balancer_type = "application"
    subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]
    security_groups    = [aws_security_group.ecs_sg.id]
    tags = {
      Name = "${var.env}-alb"
    }
}

resource "aws_lb_target_group" "frontend_tg" {
    name_prefix = "${var.env}tg"
    port        = 80
    protocol    = "HTTP"
    vpc_id      = aws_vpc.main.id
    target_type = "ip"
    health_check {
        path    = "/"
        matcher = "200"
    }
    tags = {
      Name = "${var.env}-tg"
    }
}

# resource "aws_lb_target_group" "grafana_tg" {
#     name_prefix = "${var.env}-gf"
#     port        = 3000
#     protocol    = "HTTP"
#     vpc_id      = aws_vpc.main.id
#     target_type = "ip"
#     health_check {
#         path    = "/grafana/login"
#         matcher = "200"
#     }
#     tags = {
#       Name = "${var.env}-grafana-tg"
#     }
# }

resource "aws_lb_listener" "frontend_listener" {
    load_balancer_arn = aws_lb.frontend_alb.arn
    port              = 80
    protocol          = "HTTP"
    default_action {
        type             = "forward"
        target_group_arn = aws_lb_target_group.frontend_tg.arn
    }
}

# resource "aws_lb_listener_rule" "grafana_listener_rule" {
#     listener_arn = aws_lb_listener.frontend_listener.arn
#     priority     = 10
#     action {
#         type             = "forward"
#         target_group_arn = aws_lb_target_group.grafana_tg.arn
#     }
#     condition {
#         path_pattern {
#             values = ["/grafana*","/grafana/*"]
#         }
#     }
# }

# ------------------------------------------------------------------
# Monitoring Instance
# ------------------------------------------------------------------
resource "aws_instance" "monitoring_instance" {
    # ami           = "ami-0c55b159cbfafe1f0" # Amazon Linux 2 AMI
    ami           = "ami-0a1235697f4afa8a4" # Amazon Linux 2 AMI
    instance_type = "t2.micro"
    # subnet_id     = aws_subnet.public_1.id
    subnet_id     = aws_subnet.public_1.id
    # vpc_security_group_ids = [aws_security_group.monitoring_sg.id]
    vpc_security_group_ids = [aws_security_group.ecs_sg.id]
    associate_public_ip_address = true
    key_name      = "monitoring-key"

    user_data = <<-EOF
                #!/bin/bash -xe
                exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
                yum update -y
                yum install -y docker
                systemctl start docker
                systemctl enable docker
                usermod -a -G docker ec2-user

                DOCKER_CONFIG_DIR="/usr/local/lib/docker/cli-plugins"
                mkdir -p "$DOCKER_CONFIG_DIR"
                curl -SL "https://github.com/docker/compose/releases/download/v2.17.2/docker-compose-linux-x86_64" -o "$DOCKER_CONFIG_DIR/docker-compose"
                chmod +x "$DOCKER_CONFIG_DIR/docker-compose"

                MONITORING_DIR="/home/ec2-user/monitoring"
                mkdir -p "$MONITORING_DIR/prometheus"
                mkdir -p "$MONITORING_DIR/grafana/provisioning/datasources"
                mkdir -p "$MONITORING_DIR/grafana/provisioning/dashboards"
                mkdir -p "$MONITORING_DIR/grafana/dashboards"
                mkdir -p "$MONITORING_DIR/blackbox"

                chown -R ec2-user:ec2-user "$MONITORING_DIR"
                EOF
    tags = {Name = "${var.env}-monitoring-instance"}
}


# resource "aws_lb_target_group_attachment" "grafana_ec2_attachment" {
#     target_group_arn = aws_lb_target_group.grafana_tg.arn
#     target_id        = aws_instance.monitoring_instance.private_ip
#     port             = 3000
# }

# ------------------------------------------------------------------
# Auto Scaling
# ------------------------------------------------------------------
resource "aws_appautoscaling_target" "frontend_scaling_target" {
    service_namespace  = "ecs"
    resource_id        = "service/${aws_ecs_cluster.cluster.name}/${aws_ecs_service.frontend_service.name}"
    scalable_dimension = "ecs:service:DesiredCount"
    min_capacity       = 1
    max_capacity       = 4
    depends_on         = [aws_ecs_service.frontend_service]
}

resource "aws_appautoscaling_policy" "frontend_cpu_policy" {
    name               = "${var.env}-frontend-cpu-policy"
    policy_type        = "TargetTrackingScaling"
    service_namespace  = "ecs"
    resource_id        = aws_appautoscaling_target.frontend_scaling_target.resource_id
    scalable_dimension = aws_appautoscaling_target.frontend_scaling_target.scalable_dimension

    target_tracking_scaling_policy_configuration {
        predefined_metric_specification {
            predefined_metric_type = "ECSServiceAverageCPUUtilization"
        }
        target_value       = 60.0
        scale_in_cooldown  = 60
        scale_out_cooldown = 60
    }
    depends_on = [aws_ecs_service.frontend_service]
}

