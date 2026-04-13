variable "capacity" {
  type = object({ autoscaling = object({ max_worker_count = number, min_worker_count = number, mcu_count = string, scale_in_policy = object({ cpu_utilization_percentage = number }), scale_out_policy = object({ cpu_utilization_percentage = number }) }), provisioned_capacity = object({ worker_count = number, mcu_count = string }) })
}

variable "connector_configuration" {
  type = map(string)
}

variable "custom_plugin" {
  type = object({ name = string, content_type = string, location = object({ s3_bucket_arn = string, s3_file_key = string, s3_object_version = string }) })
}

variable "identifier" {
  type = string
}

variable "kafka_cluster_bootstrap_servers" {
  type = string
}

variable "kafka_connect_version" {
  type = string
}

variable "log_delivery" {
  type    = object({ worker_log_delivery = object({ cloudwatch_logs = object({ enabled = bool, retention_in_days = number }), s3 = object({ enabled = bool, bucket = string, prefix = string }) }) })
  default = null
}

variable "output_prefix" {
  type = string
}

variable "output_resource_name" {
  type    = string
  default = null
}

variable "region" {
  type = string
}

variable "service_execution_role_arn" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "vpc" {
  type = object({ subnets = list(string), security_groups = list(string) })
}

variable "worker_configuration" {
  type    = object({ name = string, properties_file_content = string, description = string })
  default = null
}
