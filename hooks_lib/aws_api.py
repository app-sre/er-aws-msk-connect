from __future__ import annotations

from typing import TYPE_CHECKING, Any

from boto3 import Session
from botocore.config import Config as BotocoreConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from mypy_boto3_ec2.client import EC2Client
    from mypy_boto3_ec2.type_defs import SecurityGroupTypeDef, SubnetTypeDef
    from mypy_boto3_iam.client import IAMClient
    from mypy_boto3_s3.client import S3Client


class AWSApi:
    """AWS Api Class"""

    def __init__(self, config_options: Mapping[str, Any]) -> None:
        self.session = Session()
        self.config = BotocoreConfig(**config_options)
        self.region_name: str = (
            config_options.get("region_name") or self.session.region_name or ""
        )

    @property
    def ec2_client(self) -> EC2Client:
        """Gets a boto EC2 client"""
        return self.session.client("ec2", config=self.config)

    @property
    def s3_client(self) -> S3Client:
        """Gets a boto S3 client"""
        return self.session.client("s3", config=self.config)

    @property
    def iam_client(self) -> IAMClient:
        """Gets a boto IAM client."""
        return self.session.client("iam", config=self.config)

    def get_subnets(self, subnets: Sequence[str]) -> list[SubnetTypeDef]:
        """Retrieve subnet list"""
        data = self.ec2_client.describe_subnets(
            SubnetIds=subnets,
        )
        return data["Subnets"]

    def get_security_groups(
        self, security_groups: Sequence[str]
    ) -> list[SecurityGroupTypeDef]:
        """Retrieve security group list"""
        data = self.ec2_client.describe_security_groups(
            GroupIds=security_groups,
        )
        return data["SecurityGroups"]

    def simulate_principal_policy(
        self, role_arn: str, action_names: Sequence[str], resource_arns: Sequence[str]
    ) -> dict[str, str]:
        """Simulate IAM policy for a principal.

        Returns a dict mapping action names to their evaluation decision
        (e.g., "allowed", "implicitDeny", "explicitDeny").
        """
        results: dict[str, str] = {}
        paginator = self.iam_client.get_paginator("simulate_principal_policy")
        for page in paginator.paginate(
            PolicySourceArn=role_arn,
            ActionNames=list(action_names),
            ResourceArns=list(resource_arns),
        ):
            for result in page["EvaluationResults"]:
                results[result["EvalActionName"]] = result["EvalDecision"]
        return results

    def check_s3_vpc_endpoint(self, vpc_id: str) -> bool:
        """Check if an S3 Gateway VPC Endpoint exists in the given VPC."""
        response = self.ec2_client.describe_vpc_endpoints(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {
                    "Name": "service-name",
                    "Values": [f"com.amazonaws.{self.region_name}.s3"],
                },
                {"Name": "vpc-endpoint-type", "Values": ["Gateway"]},
            ]
        )
        return len(response.get("VpcEndpoints", [])) > 0

    def validate_s3_bucket_exists(self, bucket: str) -> bool:
        """Validate that an S3 bucket exists and is accessible."""
        try:
            self.s3_client.head_bucket(Bucket=bucket)
        except Exception:  # noqa: BLE001
            return False
        return True

    def validate_s3_object(
        self, bucket: str, key: str, version: str | None = None
    ) -> bool:
        """Validate that an S3 object exists."""
        try:
            if version is not None:
                self.s3_client.head_object(Bucket=bucket, Key=key, VersionId=version)
            else:
                self.s3_client.head_object(Bucket=bucket, Key=key)
        except Exception:  # noqa: BLE001
            return False
        return True
