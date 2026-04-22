provider "aws" {
  region = var.region
  default_tags {
    tags = var.tags
  }
}

# Look up the IAM role ARN from the role identifier
data "aws_iam_role" "execution_role" {
  name = var.service_execution_role
}

# Custom plugin
resource "aws_mskconnect_custom_plugin" "this" {
  name         = "${var.identifier}-plugin"
  content_type = upper(var.custom_plugin.content_type)

  location {
    s3 {
      bucket_arn     = var.custom_plugin.s3_bucket_arn
      file_key       = var.custom_plugin.s3_key
      object_version = var.custom_plugin.s3_object_version
    }
  }
}

# Worker configuration (optional)
resource "aws_mskconnect_worker_configuration" "this" {
  count                   = var.worker_configuration != null ? 1 : 0
  name                    = "${var.identifier}-wc"
  properties_file_content = var.worker_configuration
}

# CloudWatch log group (optional)
resource "aws_cloudwatch_log_group" "this" {
  count             = try(var.log_delivery.cloudwatch_logs.enabled, false) ? 1 : 0
  name              = "${var.identifier}-logs"
  retention_in_days = var.log_delivery.cloudwatch_logs.retention_in_days
}

# The connector
resource "aws_mskconnect_connector" "this" {
  name                       = var.identifier
  kafkaconnect_version       = var.kafka_connect_version
  service_execution_role_arn = data.aws_iam_role.execution_role.arn
  # Note: confluent.topic.bootstrap.servers is required by Confluent connectors
  # for their internal topic. Most non-Confluent connectors ignore unknown keys,
  # but connectors with strict config validation may reject it.
  connector_configuration = merge(
    var.connector_configuration,
    {
      "confluent.topic.bootstrap.servers" = var.kafka_cluster_bootstrap_servers
    }
  )

  kafka_cluster {
    apache_kafka_cluster {
      bootstrap_servers = var.kafka_cluster_bootstrap_servers
      vpc {
        subnets         = var.vpc.subnets
        security_groups = var.vpc.security_groups
      }
    }
  }

  kafka_cluster_client_authentication {
    authentication_type = "IAM"
  }

  kafka_cluster_encryption_in_transit {
    encryption_type = "TLS"
  }

  plugin {
    custom_plugin {
      arn      = aws_mskconnect_custom_plugin.this.arn
      revision = aws_mskconnect_custom_plugin.this.latest_revision
    }
  }

  # Capacity: autoscaling or provisioned (mutually exclusive, enforced by Pydantic)
  dynamic "capacity" {
    for_each = var.capacity.autoscaling != null ? [1] : []
    content {
      autoscaling {
        min_worker_count = var.capacity.autoscaling.min_worker_count
        max_worker_count = var.capacity.autoscaling.max_worker_count
        mcu_count        = var.capacity.autoscaling.mcu_count
        scale_in_policy {
          cpu_utilization_percentage = var.capacity.autoscaling.scale_in_policy.cpu_utilization_percentage
        }
        scale_out_policy {
          cpu_utilization_percentage = var.capacity.autoscaling.scale_out_policy.cpu_utilization_percentage
        }
      }
    }
  }

  dynamic "capacity" {
    for_each = var.capacity.provisioned_capacity != null ? [1] : []
    content {
      provisioned_capacity {
        worker_count = var.capacity.provisioned_capacity.worker_count
        mcu_count    = var.capacity.provisioned_capacity.mcu_count
      }
    }
  }

  # Worker configuration (optional)
  dynamic "worker_configuration" {
    for_each = var.worker_configuration != null ? [1] : []
    content {
      arn      = aws_mskconnect_worker_configuration.this[0].arn
      revision = aws_mskconnect_worker_configuration.this[0].latest_revision
    }
  }

  # Log delivery (optional)
  dynamic "log_delivery" {
    for_each = var.log_delivery != null ? [1] : []
    content {
      worker_log_delivery {
        dynamic "cloudwatch_logs" {
          for_each = try(var.log_delivery.cloudwatch_logs.enabled, false) ? [1] : []
          content {
            enabled   = true
            log_group = aws_cloudwatch_log_group.this[0].name
          }
        }
        dynamic "s3" {
          for_each = try(var.log_delivery.s3.enabled, false) ? [1] : []
          content {
            enabled = true
            bucket  = var.log_delivery.s3.bucket
            prefix  = var.log_delivery.s3.prefix
          }
        }
      }
    }
  }
}
