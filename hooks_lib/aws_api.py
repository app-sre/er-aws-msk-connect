from __future__ import annotations

from typing import TYPE_CHECKING, Any

from boto3 import Session
from botocore.config import Config as BotocoreConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from mypy_boto3_ec2.client import EC2Client
    from mypy_boto3_ec2.type_defs import SecurityGroupTypeDef, SubnetTypeDef
    from mypy_boto3_s3.client import S3Client


class AWSApi:
    """AWS Api Class"""

    def __init__(self, config_options: Mapping[str, Any]) -> None:
        self.session = Session()
        self.config = BotocoreConfig(**config_options)

    @property
    def ec2_client(self) -> EC2Client:
        """Gets a boto EC2 client"""
        return self.session.client("ec2", config=self.config)

    @property
    def s3_client(self) -> S3Client:
        """Gets a boto S3 client"""
        return self.session.client("s3", config=self.config)

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
