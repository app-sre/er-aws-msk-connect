from __future__ import annotations

from typing import Literal, Self

from external_resources_io.input import AppInterfaceProvision  # noqa: TC002
from pydantic import BaseModel, model_validator


class CustomPluginLocation(BaseModel):
    """aws_mskconnect_custom_plugin.location.s3"""

    s3_bucket_arn: str
    s3_file_key: str
    s3_object_version: str | None = None


class CustomPlugin(BaseModel):
    """aws_mskconnect_custom_plugin"""

    name: str
    content_type: Literal["ZIP", "JAR"]
    location: CustomPluginLocation


class WorkerConfiguration(BaseModel):
    """aws_mskconnect_worker_configuration"""

    name: str
    properties_file_content: str
    description: str | None = None


class ScaleInPolicy(BaseModel):
    """aws_mskconnect_connector.capacity.autoscaling.scale_in_policy"""

    cpu_utilization_percentage: int = 20


class ScaleOutPolicy(BaseModel):
    """aws_mskconnect_connector.capacity.autoscaling.scale_out_policy"""

    cpu_utilization_percentage: int = 80


class AutoscalingCapacity(BaseModel):
    """aws_mskconnect_connector.capacity.autoscaling"""

    max_worker_count: int
    min_worker_count: int
    mcu_count: Literal[1, 2, 4, 8] = 1
    scale_in_policy: ScaleInPolicy = ScaleInPolicy()
    scale_out_policy: ScaleOutPolicy = ScaleOutPolicy()


class ProvisionedCapacity(BaseModel):
    """aws_mskconnect_connector.capacity.provisioned_capacity"""

    worker_count: int
    mcu_count: Literal[1, 2, 4, 8] = 1


class Capacity(BaseModel):
    """aws_mskconnect_connector.capacity"""

    autoscaling: AutoscalingCapacity | None = None
    provisioned_capacity: ProvisionedCapacity | None = None

    @model_validator(mode="after")
    def exactly_one_capacity_type(self) -> Self:
        """Validate that exactly one capacity type is set."""
        if (self.autoscaling is None) == (self.provisioned_capacity is None):
            msg = "Exactly one of 'autoscaling' or 'provisioned_capacity' must be set"
            raise ValueError(msg)
        return self


class CloudwatchLogsLogDelivery(BaseModel):
    """aws_mskconnect_connector.log_delivery.worker_log_delivery.cloudwatch_logs"""

    enabled: bool
    retention_in_days: int


class S3LogDelivery(BaseModel):
    """aws_mskconnect_connector.log_delivery.worker_log_delivery.s3"""

    enabled: bool
    bucket: str
    prefix: str | None = None


class WorkerLogDelivery(BaseModel):
    """aws_mskconnect_connector.log_delivery.worker_log_delivery"""

    cloudwatch_logs: CloudwatchLogsLogDelivery | None = None
    s3: S3LogDelivery | None = None


class LogDelivery(BaseModel):
    """aws_mskconnect_connector.log_delivery"""

    worker_log_delivery: WorkerLogDelivery


class VpcConfig(BaseModel):
    """aws_mskconnect_connector.kafka_cluster.apache_kafka_cluster.vpc"""

    subnets: list[str]
    security_groups: list[str]


class MskConnectData(BaseModel):
    """Data model for AWS MSK Connect"""

    # app-interface
    region: str
    identifier: str
    output_resource_name: str | None = None
    output_prefix: str

    # connector config
    connector_configuration: dict[str, str]
    kafka_cluster_bootstrap_servers: str
    kafka_connect_version: str
    service_execution_role_arn: str
    capacity: Capacity
    vpc: VpcConfig

    # sub-resources
    custom_plugin: CustomPlugin
    worker_configuration: WorkerConfiguration | None = None

    # optional
    log_delivery: LogDelivery | None = None
    tags: dict[str, str] = {}


class AppInterfaceInput(BaseModel):
    """Input model for AWS MSK Connect"""

    data: MskConnectData
    provision: AppInterfaceProvision
