output "connector_arn" {
  value = aws_mskconnect_connector.this.arn
}

output "connector_version" {
  value = aws_mskconnect_connector.this.version
}

output "custom_plugin_arn" {
  value = aws_mskconnect_custom_plugin.this.arn
}

output "worker_configuration_arn" {
  value = var.worker_configuration != null ? aws_mskconnect_worker_configuration.this[0].arn : null
}

output "log_group_name" {
  value = try(aws_cloudwatch_log_group.this[0].name, null)
}
