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

    def _validate_s3_plugin(self) -> None:
        plugin = self.input.data.custom_plugin
        location = plugin.location
        # Extract bucket name from ARN (arn:aws:s3:::bucket-name)
        bucket_arn = location.s3_bucket_arn
        bucket_name = bucket_arn.split(":")[-1]
        logger.info(f"Validating S3 object s3://{bucket_name}/{location.s3_file_key}")
        if not self.aws_api.validate_s3_object(
            bucket=bucket_name,
            key=location.s3_file_key,
            version=location.s3_object_version,
        ):
            version_msg = (
                f" (version: {location.s3_object_version})"
                if location.s3_object_version
                else ""
            )
            self.errors.append(
                f"S3 object s3://{bucket_name}/{location.s3_file_key}{version_msg} not found"
            )

    def validate(self) -> bool:
        """Validate method"""
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

            self._validate_s3_plugin()
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
