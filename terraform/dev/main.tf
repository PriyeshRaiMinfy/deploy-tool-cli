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
# -----------------for prometheus and grafana----------------------------
    ingress {
        from_port   = 3000
        to_port     = 3000
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    ingress {
        from_port   = 9090
        to_port     = 9090
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
# ---------------------------------------------
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

resource "aws_iam_role" "ecs_task_role" {
    name = "${var.env}-ecs-task-role"

    assume_role_policy = jsonencode({
        Version = "2012-10-17",
        Statement = [
        {
        Effect = "Allow",
        Principal = {
            Service = "ecs-tasks.amazonaws.com"
        },
        Action = "sts:AssumeRole"
        }
    ]
    })
}
# ------------------------------------------------------------------
# -------------------- resource block------------------------------
resource "aws_efs_file_system" "prometheus_efs" {
    tags = {
        Name = "${var.env}-prometheus-efs"
    }
}
resource "aws_efs_mount_target" "prometheus_1" {
    file_system_id  = aws_efs_file_system.prometheus_efs.id
    subnet_id       = aws_subnet.public_1.id
    security_groups = [aws_security_group.ecs_sg.id]
}

resource "aws_efs_mount_target" "prometheus_2" {
    file_system_id  = aws_efs_file_system.prometheus_efs.id
    subnet_id       = aws_subnet.public_2.id
    security_groups = [aws_security_group.ecs_sg.id]
}




resource "aws_efs_access_point" "prometheus_ap" {
    file_system_id = aws_efs_file_system.prometheus_efs.id

    posix_user {
        uid = 1000
        gid = 1000
    }

    root_directory {
        path = "/prometheus"
        creation_info {
            owner_gid   = 1000
            owner_uid   = 1000
            permissions = "755"
        }
    }

    tags = {
    Name = "${var.env}-prometheus-ap"
    }
}
resource "aws_cloudwatch_log_group" "ecs_logs" {
    name              = "/ecs/${var.env}-frontend"
    retention_in_days = 1
}


# ------------------------------------------------------------------
resource "aws_iam_role_policy" "ecs_task_efs_policy" {
    name = "${var.env}-ecs-task-efs-policy"
    role = aws_iam_role.ecs_task_role.id

    policy = jsonencode({
        Version = "2012-10-17",
        Statement = [{
        Action = [
            "elasticfilesystem:ClientMount",
            "elasticfilesystem:ClientWrite",
            "elasticfilesystem:ClientRootAccess"
        ],
            Effect   = "Allow",
            Resource = aws_efs_file_system.prometheus_efs.arn
            # resource = aws_efs_file_system.prometheus_efs.arn
        }]
    })
}

# -------------------------------------efs access------------------------
resource "aws_iam_role_policy_attachment" "efs_access" {
    role       = aws_iam_role.ecs_task_execution_role.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonElasticFileSystemClientFullAccess"
}

# ------------------------------------------------------------------
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
# FRONTEND - TAREGT GROUP

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
# FRONTEND - ALB LISTNER
resource "aws_lb_listener" "frontend_listener" {
    load_balancer_arn = aws_lb.frontend_alb.arn
    port              = 80
    protocol          = "HTTP"
    
    default_action {
        type             = "forward"
        target_group_arn = aws_lb_target_group.frontend_tg.arn

    }

    depends_on = [aws_lb_target_group.frontend_tg,    
    aws_lb_target_group.grafana_tg]
}
# ------------------------------------------------------------------------------------------------------


# ------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------
# # ECS TASK DEFINITION
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
            name      = "frontend"
            image     = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.env}-frontend-ecr:latest"
            portMappings = [{
                containerPort = 80
                # hostPort      = 80
            }]
            logConfiguration: {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/${var.env}-frontend",
                    "awslogs-region": "${var.aws_region}",
                    "awslogs-stream-prefix": "ecs"
                }
            }
        },
        {
            name      = "prometheus"
            image     = "prom/prometheus:latest"
            essential = false
            portMappings = [{
                containerPort = 9090
                # hostPort      = 9090
            }],
            mountPoints = [{
                    sourceVolume  = "prometheus-config"
                    containerPath = "/etc/prometheus"
            }]
            logConfiguration: {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/${var.env}-frontend",
                    "awslogs-region": "${var.aws_region}",
                    "awslogs-stream-prefix": "ecs"
                }
            }
        },
        {
            name      = "grafana"
            image     = "grafana/grafana:latest"
            essential = false
            portMappings = [{
                containerPort = 3000
                # hostPort      = 3000
            }]
            environment = [{
                name  = "GF_SECURITY_ADMIN_PASSWORD"
                value = "admin"
            },{
                name  = "GF_SERVER_ROOT_URL"
                value = "/grafana"
            },{
                name  = "GF_SERVER_SERVE_FROM_SUB_PATH"
                value = "true"
            }
            ]
            mountPoints = [{
                sourceVolume  = "grafana-config"
                containerPath = "/var/lib/grafana/dashboards"
                readOnly      = false
            },
            {
                sourceVolume  = "grafana-provisioning"
                containerPath = "/etc/grafana/provisioning"
                readOnly      = false
            }]
            logConfiguration: {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/${var.env}-frontend",
                    "awslogs-region": "${var.aws_region}",
                    "awslogs-stream-prefix": "ecs"
                }
            }
        }
    ])
    volume {
        name = "prometheus-config"
        # host_path {
        #     path = "/ecs/prometheus-config"
        # }
        # host_path can't be use with the ECS-FARGATE so we will use AWSW EFS - 
        efs_volume_configuration {
            file_system_id     = aws_efs_file_system.prometheus_efs.id  # define this!
            # root_directory     = "/prometheus"
            root_directory     = "/"
            transit_encryption = "ENABLED"
            authorization_config {
                access_point_id = aws_efs_access_point.prometheus_ap.id
                iam             = "ENABLED"
            }
        }
    }
    volume {
        name = "grafana-config"
        # host_path {
        #     path = "/ecs/grafana-config"
        # }
        # host_path can't be use with the ECS-FARGATE so we will use AWSW EFS - 
        efs_volume_configuration {
            file_system_id     = aws_efs_file_system.prometheus_efs.id  # define this!
            # root_directory     = "/grafana/provisioning/dashboards"
            root_directory     = "/"
            transit_encryption = "ENABLED"
            authorization_config {
                access_point_id = aws_efs_access_point.prometheus_ap.id
                iam             = "ENABLED"
            }
        }
    }
    volume {
        name = "grafana-provisioning"
        efs_volume_configuration {
            file_system_id     = aws_efs_file_system.prometheus_efs.id
            # root_directory     = "/grafana/provisioning"
            root_directory     = "/"
            transit_encryption = "ENABLED"
            authorization_config {
                access_point_id = aws_efs_access_point.prometheus_ap.id
                iam             = "ENABLED"
            }
        }
    }
}
# ----------------------------------------------------------------------------------------
# ALB TARGER GROUP - GRAFANA
resource "aws_lb_target_group" "grafana_tg" {
    name_prefix = "${var.env}-gf"
    port        = 3000
    protocol    = "HTTP"
    vpc_id      = aws_vpc.main.id
    target_type = "ip"

    health_check {
        path                = "/grafana/login"
        protocol            = "HTTP"
        matcher             = "200-399"
        interval            = 30
        timeout             = 5
        healthy_threshold   = 2
        unhealthy_threshold = 2
    }

    tags = {
        Name = "${var.env}-grafana-tg"
    }
}
# ALB LISTNER - GRAFANA

resource "aws_lb_listener_rule" "grafana_listener_rule" {
    listener_arn = aws_lb_listener.frontend_listener.arn
    priority = 10

    action {
        type             = "forward"
        target_group_arn = aws_lb_target_group.grafana_tg.arn
    }

    condition {
        path_pattern {
            values = ["/grafana*","/grafana"]
        }
    }
    depends_on = [aws_lb_listener.frontend_listener]
}
# ----------------------------------------------------------------------------------------
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
    load_balancer {
        target_group_arn = aws_lb_target_group.grafana_tg.arn
        container_name   = "grafana"
        container_port   = 3000
    }

    depends_on = [
        aws_lb_listener.frontend_listener,
        # aws_lb_listener.grafana_listener_
        aws_lb_listener_rule.grafana_listener_rule

    ]
}
#---------------------    applying the auto scaling  to the ECS cluster [FARGATE]    -------------------
#---------------------    Just an add-on feature  => Only for self satisfaction    -------------------

resource "aws_appautoscaling_target" "frontend_scaling_target" {
    service_namespace  = "ecs"
    resource_id        = "service/${var.env}-ecs-cluster/${var.env}-frontend-service"
    scalable_dimension = "ecs:service:DesiredCount"
    min_capacity       = 1
    max_capacity       = 4

    depends_on = [aws_ecs_service.frontend_service]

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
