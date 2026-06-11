from external_resources_io.input import parse_model

from er_aws_msk_connect.app_interface_input import AppInterfaceInput


def test_custom_plugin_s3_bucket_arn_normalized_for_govcloud_region(
    raw_govcloud_input_data: dict,
) -> None:
    """Reconcile may supply arn:aws:s3:::; module rewrites it for us-gov regions."""
    ai_input = parse_model(AppInterfaceInput, raw_govcloud_input_data)

    assert ai_input.data.region == "us-gov-west-1"
    assert (
        ai_input.data.custom_plugin.s3_bucket_arn
        == "arn:aws-us-gov:s3:::my-plugins-bucket"
    )


def test_custom_plugin_s3_bucket_arn_unchanged_for_commercial_region(
    raw_input_data: dict,
) -> None:
    """Commercial regions keep the standard aws S3 bucket ARN."""
    ai_input = parse_model(AppInterfaceInput, raw_input_data)

    assert ai_input.data.region == "us-east-1"
    assert ai_input.data.custom_plugin.s3_bucket_arn == "arn:aws:s3:::my-plugins-bucket"
