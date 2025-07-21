variable "aws_profile" {
    description = "AWS SSO CLI Profile Name"
    type        = string
}

variable "env" {
    description = "Environment name (e.g., dev or prod)"
    type        = string
}
variable "aws_account_id" {
    description = "Your AWS Account ID"
    type        = string
}

variable "aws_region" {
    description = "AWS Region"
    type        = string
    default     = "ap-south-1"
}