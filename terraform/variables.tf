variable "capacity" {
  type = object({ autoscaling = object({ min_worker_count = number, max_worker_count = number, mcu_count = number, scale_in_policy = object({ cpu_utilization_percentage = number }), scale_out_policy = object({ cpu_utilization_percentage = number }) }), provisioned_capacity = object({ worker_count = number, mcu_count = number }) })
  default = {
    autoscaling = null
    provisioned_capacity = {
      worker_count = 1
      mcu_count    = 1
    }
  }
}

variable "connector_configuration" {
  type = map(string)
}

variable "custom_plugin" {
  type = object({ s3_bucket_arn = string, s3_key = string, s3_object_version = string, content_type = string })
}

variable "identifier" {
  type = string
}

variable "kafka_cluster_bootstrap_servers" {
  type = string
}

variable "kafka_connect_version" {
  type    = string
  default = "3.7.x"
}

variable "log_delivery" {
  type    = object({ cloudwatch_logs = object({ enabled = bool, retention_in_days = number }), s3 = object({ enabled = bool, bucket = string, prefix = string }) })
  default = null
}

variable "region" {
  type = string
}

variable "service_execution_role" {
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
  type    = string
  default = null
}
