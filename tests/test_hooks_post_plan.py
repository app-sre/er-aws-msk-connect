from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from external_resources_io.terraform import Action, ResourceChange

from er_aws_msk_connect.app_interface_input import AppInterfaceInput
from hooks.post_plan import MskConnectPlanValidator, TerraformJsonPlanParser


@pytest.fixture
def mock_terraform_plan_parser() -> MagicMock:
    """Mock TerraformJsonPlanParser for testing."""
    mock_plan = MagicMock()
    mock_plan.resource_changes = []
    parser = MagicMock(spec=TerraformJsonPlanParser)
    parser.plan = mock_plan
    return parser


@pytest.fixture
def mock_aws_api() -> Iterator[MagicMock]:
    """Mock AWSApi for testing."""
    with patch("hooks.post_plan.AWSApi") as mock:
        yield mock


def _make_connector_change(subnets: list[str], security_groups: list[str]) -> MagicMock:
    """Helper to create a mock connector resource change."""
    return MagicMock(
        spec=ResourceChange,
        type="aws_mskconnect_connector",
        change=MagicMock(
            after={
                "kafka_cluster": [
                    {
                        "apache_kafka_cluster": [
                            {
                                "vpc": [
                                    {
                                        "subnets": subnets,
                                        "security_groups": security_groups,
                                    }
                                ]
                            }
                        ]
                    }
                ],
            },
            actions=[Action.ActionCreate],
        ),
    )


def test_msk_connect_plan_validator_validate_success(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test the full validate method with valid data."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-123"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = True

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert validator.validate()
    assert not validator.errors


def test_msk_connect_plan_validator_validate_failure_invalid_subnets(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test validation failure with missing subnets."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-missing"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in ["subnet-aaa", "subnet-bbb"]
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = True

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert "subnet-missing" in validator.errors[0]


def test_msk_connect_plan_validator_validate_failure_security_group_vpc(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test validation failure with security group in wrong VPC."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-456"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = True

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert (
        "Security group sg-111 does not belong to the same VPC as the subnets"
        in validator.errors[0]
    )


def test_msk_connect_plan_validator_validate_failure_s3_object_missing(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test validation failure when S3 plugin object is missing."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-123"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = False

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert "S3 object" in validator.errors[0]
    assert "my-plugins-bucket" in validator.errors[0]


def test_msk_connect_plan_validator_validate_failure_s3_object_with_version(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test validation failure with S3 version info in error message."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-123"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = False

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert "version: abc123" in validator.errors[0]
