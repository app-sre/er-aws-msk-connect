import pytest
from external_resources_io.input import parse_model

from er_aws_msk_connect.app_interface_input import AppInterfaceInput


@pytest.fixture
def raw_input_data() -> dict:
    """Fixture to provide test data for the AppInterfaceInput."""
    return {
        "data": {
            "region": "us-east-1",
            "identifier": "my-test-connector",
            "output_resource_name": "creds-msk-connect",
            "output_prefix": "my-test-connector-msk-connect",
            "connector_configuration": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "tasks.max": "1",
                "database.hostname": "my-db.example.com",
                "database.port": "5432",
                "database.user": "connect_user",
                "database.dbname": "mydb",
                "topic.prefix": "my-prefix",
            },
            "kafka_cluster_bootstrap_servers": "b-1.msk.us-east-1.amazonaws.com:9098,b-2.msk.us-east-1.amazonaws.com:9098",
            "kafka_connect_version": "2.7.1",
            "service_execution_role_arn": "arn:aws:iam::123456789012:role/my-msk-connect-role",
            "capacity": {
                "autoscaling": {
                    "max_worker_count": 4,
                    "min_worker_count": 1,
                    "mcu_count": 1,
                    "scale_in_policy": {"cpu_utilization_percentage": 20},
                    "scale_out_policy": {"cpu_utilization_percentage": 80},
                },
            },
            "vpc": {
                "subnets": ["subnet-aaa", "subnet-bbb", "subnet-ccc"],
                "security_groups": ["sg-111"],
            },
            "custom_plugin": {
                "name": "debezium-plugin",
                "content_type": "ZIP",
                "location": {
                    "s3_bucket_arn": "arn:aws:s3:::my-plugins-bucket",
                    "s3_file_key": "plugins/debezium-connector-postgres-2.5.0.zip",
                    "s3_object_version": "abc123",
                },
            },
            "worker_configuration": {
                "name": "my-worker-config",
                "properties_file_content": "key.converter=org.apache.kafka.connect.storage.StringConverter\nvalue.converter=org.apache.kafka.connect.storage.StringConverter",
                "description": "Custom worker configuration",
            },
            "log_delivery": {
                "worker_log_delivery": {
                    "cloudwatch_logs": {
                        "enabled": True,
                        "retention_in_days": 7,
                    },
                },
            },
            "tags": {
                "managed_by_integration": "external_resources",
                "cluster": "appint-ex-01",
                "namespace": "example-msk-connect",
                "environment": "production",
                "app": "msk-connect-example",
            },
        },
        "provision": {
            "provision_provider": "aws",
            "provisioner": "app-int-example-01",
            "provider": "msk-connect",
            "identifier": "my-test-connector",
            "target_cluster": "appint-ex-01",
            "target_namespace": "example-msk-connect",
            "target_secret_name": "creds-msk-connect",
            "module_provision_data": {
                "tf_state_bucket": "external-resources-terraform-state-dev",
                "tf_state_region": "us-east-1",
                "tf_state_dynamodb_table": "external-resources-terraform-lock",
                "tf_state_key": "aws/app-int-example-01/msk-connect/my-test-connector/terraform.tfstate",
            },
        },
    }


@pytest.fixture
def ai_input(raw_input_data: dict) -> AppInterfaceInput:
    """Fixture to provide the AppInterfaceInput."""
    return parse_model(AppInterfaceInput, raw_input_data)
