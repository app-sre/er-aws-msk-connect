# Known Limitations

## Immutability Constraints

Most MSK Connect resources force replacement on any change:

- **`aws_mskconnect_custom_plugin`**: ALL arguments force replacement. Any change destroys and recreates.
- **`aws_mskconnect_worker_configuration`**: ALL arguments force replacement.
- **`aws_mskconnect_connector`**: Only `capacity` and `connector_configuration` can be updated in-place. Everything else (name, kafka_cluster, plugins, worker_config, service_execution_role, encryption, auth) forces replacement.

Both the custom plugin and worker configuration resources use `create_before_destroy` lifecycle rules and identifier-prefixed naming to handle replacements safely.

## Single Plugin Per Connector

AWS MSK Connect supports multiple plugins per connector, but this module only supports one. Users must combine multiple JARs into a single ZIP file before uploading to S3.

## No S3 Bucket Management

This module does not create S3 buckets or upload plugin artifacts. The S3 bucket and plugin ZIP must exist before the connector is created.

## No IAM Role Management

This module does not create IAM roles. The `service_execution_role_arn` must reference a pre-existing IAM role with appropriate permissions.
