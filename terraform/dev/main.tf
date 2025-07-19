provider "aws" {
    region  = var.aws_region
    profile = var.aws_profile  # SSO Profile name (e.g., "Priyesh")
}

resource "aws_vpc" "main" {
    cidr_block = "10.0.0.0/16"
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

resource "aws_ecs_cluster" "cluster" {
    name = "${var.env}-ecs-cluster"
}

resource "aws_security_group" "ecs_sg" {
    name        = "${var.env}-ecs-sg"
    description = "Allow HTTP"
    vpc_id      = aws_vpc.main.id

    ingress {
        from_port   = 80
        to_port     = 80
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

resource "aws_iam_role" "ecs_task_execution_role" {
    name = "${var.env}-ecsTaskExecutionRole"

    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [{
            Action    = "sts:AssumeRole"
            Effect    = "Allow"
            Principal = {
                Service = "ecs-tasks.amazonaws.com"
            }
        }]
    })

    tags = {
        Name = "${var.env}-ecs-task-role"
    }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
    role       = aws_iam_role.ecs_task_execution_role.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ALB
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
# TAREGT GROUP

resource "aws_lb_target_group" "frontend_tg" {
    name_prefix = "${var.env}-tg"
    port     = 80
    protocol = "HTTP"
    vpc_id   = aws_vpc.main.id
    target_type = "ip"
    lifecycle {
    create_before_destroy = true
    }
    health_check {
        path                = "/"
        protocol            = "HTTP"
        matcher             = "200-399"
        interval            = 30
        timeout             = 5
        healthy_threshold   = 2
        unhealthy_threshold = 2
    }
    tags = {
        Name = "${var.env}-tg"
    }
}
# ALB LISTNER
resource "aws_lb_listener" "frontend_listener" {
    load_balancer_arn = aws_lb.frontend_alb.arn
    port              = 80
    protocol          = "HTTP"
    
    default_action {
        type             = "forward"
        target_group_arn = aws_lb_target_group.frontend_tg.arn
    }
    depends_on = [aws_lb_target_group.frontend_tg]
}

# # ECS TASK DEFINITION
resource "aws_ecs_task_definition" "frontend_task" { 
    family                   = "${var.env}-frontend-task"
    network_mode             = "awsvpc"
    requires_compatibilities = ["FARGATE"]
    cpu                      = "256"
    memory                   = "512"
    execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

    container_definitions = jsonencode([
        {
            name      = "frontend"
            image     = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.env}-frontend-ecr:latest"
            portMappings = [{
                containerPort = 80
                hostPort      = 80
            }]
        }
    ])
}

# # ECS SERVICE

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

    depends_on = [aws_lb_listener.frontend_listener]
}
#---------------------    applying the auto scaling  to the ECS cluster [FARGATE]    -------------------
#---------------------    Just an add-on feature  => Only for self satisfaction    -------------------

resource "aws_appautoscaling_target" "frontend_scaling_target" {
    service_namespace  = "ecs"
    resource_id        = "service/${var.env}-ecs-cluster/${var.env}-frontend-service"
    scalable_dimension = "ecs:service:DesiredCount"
    min_capacity       = 1
    max_capacity       = 4
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
}
