#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from external_resources_io.config import Config
from external_resources_io.input import parse_model, read_input_from_file
from external_resources_io.log import setup_logging
from external_resources_io.terraform import (
    Action,
    ResourceChange,
    TerraformJsonPlanParser,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

from er_aws_msk_connect.app_interface_input import AppInterfaceInput
from hooks_lib.aws_api import AWSApi

logger = logging.getLogger(__name__)

# Minimum required kafka-cluster IAM actions for MSK Connect
REQUIRED_KAFKA_ACTIONS = [
    "kafka-cluster:Connect",
    "kafka-cluster:DescribeCluster",
    "kafka-cluster:AlterCluster",
    "kafka-cluster:ReadData",
    "kafka-cluster:WriteData",
    "kafka-cluster:DescribeTopic",
    "kafka-cluster:CreateTopic",
    "kafka-cluster:DescribeGroup",
    "kafka-cluster:AlterGroup",
]

REQUIRED_S3_ACTIONS = [
    "s3:GetObject",
]

REQUIRED_CLOUDWATCH_ACTIONS = [
    "logs:CreateLogStream",
    "logs:PutLogEvents",
]

REQUIRED_S3_LOG_ACTIONS = [
    "s3:PutObject",
]


class MskConnectPlanValidator:
    """The plan validator class for MSK Connect resources."""

    def __init__(
        self, plan: TerraformJsonPlanParser, app_interface_input: AppInterfaceInput
    ) -> None:
        self.plan = plan
        self.input = app_interface_input
        self.aws_api = AWSApi(config_options={"region_name": self.input.data.region})
        self.errors: list[str] = []

    @property
    def connector_creates(self) -> list[ResourceChange]:
        """Get the connector create actions."""
        return [
            c
            for c in self.plan.plan.resource_changes
            if c.type == "aws_mskconnect_connector"
            and c.change
            and Action.ActionCreate in c.change.actions
        ]

    def _validate_subnets(self, subnets: Sequence[str]) -> str | None:
        """Validate that all subnets exist and belong to the same VPC.

        Returns the VPC ID if valid, None otherwise.
        """
        logger.info(f"Validating subnets {subnets}")

        vpc_ids: set[str] = set()

        data = self.aws_api.get_subnets(subnets)
        if missing := set(subnets).difference({s.get("SubnetId") for s in data}):
            self.errors.append(f"Subnet(s) {missing} not found")
            return None

        for subnet in data:
            if "VpcId" not in subnet:
                self.errors.append(
                    f"VpcId not found for subnet {subnet.get('SubnetId')}"
                )
                continue
            vpc_ids.add(subnet["VpcId"])
        if not vpc_ids:
            return None
        if len(vpc_ids) > 1:
            self.errors.append("All subnets must belong to the same VPC")
            return None
        return vpc_ids.pop()

    def _validate_security_groups(
        self, security_groups: Sequence[str], vpc_id: str
    ) -> None:
        """Validate that all security groups exist and belong to the expected VPC."""
        logger.info(f"Validating security group {security_groups}")
        data = self.aws_api.get_security_groups(security_groups)
        if missing := set(security_groups).difference({s.get("GroupId") for s in data}):
            self.errors.append(f"Security group(s) {missing} not found")
            return

        for sg in data:
            if sg.get("VpcId") != vpc_id:
                self.errors.append(
                    f"Security group {sg.get('GroupId')} does not belong to the same VPC as the subnets"
                )

    def _validate_iam_permissions(self, role_arn: str) -> None:  # noqa: C901
        """Validate that the service execution role has the required IAM permissions."""
        logger.info(f"Validating IAM permissions for role {role_arn}")

        # Check kafka-cluster actions (resource: *)
        kafka_results = self.aws_api.simulate_principal_policy(
            role_arn=role_arn,
            action_names=REQUIRED_KAFKA_ACTIONS,
            resource_arns=["*"],
        )
        for action, decision in kafka_results.items():
            if decision != "allowed":
                self.errors.append(
                    f"IAM role {role_arn} missing permission: {action} (result: {decision})"
                )

        # Check S3 plugin access
        plugin = self.input.data.custom_plugin
        bucket_name = plugin.s3_bucket_arn.split(":")[-1]
        s3_resource_arn = f"arn:aws:s3:::{bucket_name}/*"
        s3_results = self.aws_api.simulate_principal_policy(
            role_arn=role_arn,
            action_names=REQUIRED_S3_ACTIONS,
            resource_arns=[s3_resource_arn],
        )
        for action, decision in s3_results.items():
            if decision != "allowed":
                self.errors.append(
                    f"IAM role {role_arn} missing permission: {action} on {s3_resource_arn} (result: {decision})"
                )

        # Check CloudWatch log delivery permissions
        if (
            self.input.data.log_delivery
            and self.input.data.log_delivery.cloudwatch_logs
            and self.input.data.log_delivery.cloudwatch_logs.enabled
        ):
            cw_results = self.aws_api.simulate_principal_policy(
                role_arn=role_arn,
                action_names=REQUIRED_CLOUDWATCH_ACTIONS,
                resource_arns=["*"],
            )
            for action, decision in cw_results.items():
                if decision != "allowed":
                    self.errors.append(
                        f"IAM role {role_arn} missing permission: {action} (result: {decision})"
                    )

        # Check S3 log delivery permissions
        if (
            self.input.data.log_delivery
            and self.input.data.log_delivery.s3
            and self.input.data.log_delivery.s3.enabled
        ):
            log_bucket_arn = f"arn:aws:s3:::{self.input.data.log_delivery.s3.bucket}/*"
            s3_log_results = self.aws_api.simulate_principal_policy(
                role_arn=role_arn,
                action_names=REQUIRED_S3_LOG_ACTIONS,
                resource_arns=[log_bucket_arn],
            )
            for action, decision in s3_log_results.items():
                if decision != "allowed":
                    self.errors.append(
                        f"IAM role {role_arn} missing permission: {action} on {log_bucket_arn} (result: {decision})"
                    )

    def _get_execution_role_arn(self) -> str | None:
        """Get the execution role ARN."""
        # Fallback: look up the role ARN via AWS IAM API
        role_name = self.input.data.service_execution_role
        try:
            role = self.aws_api.iam_client.get_role(RoleName=role_name)
            return role["Role"]["Arn"]
        except Exception:  # noqa: BLE001
            logger.warning(f"Could not look up IAM role '{role_name}'")
            return None

    def _validate_s3_plugin(self) -> None:
        """Validate that the custom plugin S3 object exists."""
        plugin = self.input.data.custom_plugin
        bucket_name = plugin.s3_bucket_arn.split(":")[-1]
        logger.info(f"Validating S3 object s3://{bucket_name}/{plugin.s3_key}")
        if not self.aws_api.validate_s3_object(
            bucket=bucket_name,
            key=plugin.s3_key,
            version=plugin.s3_object_version,
        ):
            version_msg = (
                f" (version: {plugin.s3_object_version})"
                if plugin.s3_object_version
                else ""
            )
            self.errors.append(
                f"S3 object s3://{bucket_name}/{plugin.s3_key}{version_msg} not found"
            )

    def _validate_s3_vpc_endpoint(self, vpc_id: str) -> None:
        """Warn if no S3 Gateway VPC Endpoint exists in the MSK VPC.

        MSK Connect connectors run inside the VPC and need an S3 Gateway
        Endpoint to reach S3 (e.g., for S3 Sink/Source connectors or S3
        log delivery). Without it, S3 connections will time out.
        """
        logger.info(f"Checking for S3 VPC Gateway Endpoint in VPC {vpc_id}")
        if not self.aws_api.check_s3_vpc_endpoint(vpc_id):
            logger.warning(
                f"No S3 Gateway VPC Endpoint found in VPC {vpc_id}. "
                f"MSK Connect connectors may need an S3 VPC Endpoint to access S3 "
                f"(for S3 Sink/Source connectors, S3 log delivery, etc.)."
            )

    def _validate_s3_log_bucket(self) -> None:
        """Validate that the S3 log delivery bucket exists."""
        if not (
            self.input.data.log_delivery
            and self.input.data.log_delivery.s3
            and self.input.data.log_delivery.s3.enabled
        ):
            return
        bucket = self.input.data.log_delivery.s3.bucket
        logger.info(f"Validating S3 log delivery bucket '{bucket}'")
        if not self.aws_api.validate_s3_bucket_exists(bucket):
            self.errors.append(
                f"S3 log delivery bucket '{bucket}' does not exist or is not accessible"
            )

    def validate(self) -> bool:
        """Validate all connector creates in the plan.

        Checks subnets, security groups, and S3 plugin existence.
        Returns True if all validations pass.
        """
        for u in self.connector_creates:
            if not u.change or not u.change.after:
                continue

            subnets = u.change.after["kafka_cluster"][0]["apache_kafka_cluster"][0][
                "vpc"
            ][0]["subnets"]
            security_groups = u.change.after["kafka_cluster"][0][
                "apache_kafka_cluster"
            ][0]["vpc"][0]["security_groups"]

            if vpc_id := self._validate_subnets(subnets=subnets):
                self._validate_security_groups(
                    security_groups=security_groups,
                    vpc_id=vpc_id,
                )
                self._validate_s3_vpc_endpoint(vpc_id=vpc_id)

            self._validate_s3_plugin()
            self._validate_s3_log_bucket()
            if role_arn := self._get_execution_role_arn():
                self._validate_iam_permissions(role_arn=role_arn)
            else:
                self.errors.append("Execution role ARN not found in terraform plan")
        return not self.errors


if __name__ == "__main__":
    setup_logging()
    app_interface_input = parse_model(AppInterfaceInput, read_input_from_file())
    logger.info("Running MSK Connect terraform plan validation")
    plan = TerraformJsonPlanParser(plan_path=Config().plan_file_json)
    validator = MskConnectPlanValidator(plan, app_interface_input)
    if not validator.validate():
        logger.error(validator.errors)
        sys.exit(1)

    logger.info("Validation ended successfully")
