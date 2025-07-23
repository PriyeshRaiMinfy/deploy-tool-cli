variable "env" {
  description = "The deployment environment (e.g., dev, prod)."
  type        = string
  default     = "prod" # You can set a default value
}

variable "aws_region" {
  description = "The AWS region for the resources."
  type        = string
}

variable "aws_profile" {
  description = "The AWS CLI profile to use."
  type        = string
}

variable "aws_account_id" {
  description = "The AWS Account ID where the ECR repository is located."
  type        = string
}