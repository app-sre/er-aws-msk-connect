# External Resources MSK Connect Module

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

External Resources module to provision and manage MSK Connect connectors in AWS with app-interface.

## Resources Managed

| Resource | Terraform Type | Notes |
|---|---|---|
| Custom Plugin | `aws_mskconnect_custom_plugin` | One plugin per connector. Users combine JARs into one ZIP. |
| Worker Configuration | `aws_mskconnect_worker_configuration` | Optional. |
| CloudWatch Log Group | `aws_cloudwatch_log_group` | Conditional on log delivery config. |
| Connector | `aws_mskconnect_connector` | The core resource. IAM auth and TLS encryption are hardcoded. |

## Design Decisions

- **One connector per module invocation** -- matches the ERv2 pattern of one resource per invocation.
- **One custom plugin per connector** -- users must combine multiple JARs into a single ZIP file.
- **S3 bucket and plugin file are pre-existing** -- not managed by this module.
- **IAM authentication is hardcoded** -- the only valid auth type for MSK Connect.
- **TLS encryption is hardcoded** -- required for IAM auth.
- **`service_execution_role_arn` is required** -- the IAM role the connector assumes. Pre-existing, not managed by this module.

## Tech stack

* Terraform
* AWS provider
* Python 3.12
* Pydantic

## Development

Prepare your local development environment:

```bash
make dev
```

See the `Makefile` for more details.

### Update Terraform modules

To update the Terraform modules used in this project, bump the version in [versions.tf](/terraform/versions.tf) and update the Terraform lockfile via:

```bash
make providers-lock
```

### Development workflow

1. Make changes to the code.
1. Build the image with `make build`.
1. Run the image manually with a proper input file and credentials. See the [Debugging](#debugging) section below.
1. Please don't forget to remove (`-e ACTION=Destroy`) any development AWS resources you create, as they will incur costs.

## Debugging

To debug and run the module locally, run the following commands:

```bash
# Get the input file from app-interface
$ qontract-cli --config=<CONFIG_TOML> external-resources --provisioner <AWS_ACCOUNT_NAME> --provider msk-connect --identifier <CONNECTOR_IDENTIFIER> get-input > tmp/input.json

# Get the AWS credentials
$ qontract-cli --config=<CONFIG_TOML> external-resources --provisioner <AWS_ACCOUNT_NAME> --provider msk-connect --identifier <CONNECTOR_IDENTIFIER> get-credentials > tmp/credentials

# Run the module
$ podman run --rm -it \
    --mount type=bind,source=$PWD/tmp/input.json,target=/inputs/input.json \
    --mount type=bind,source=$PWD/tmp/credentials,target=/credentials \
    --mount type=bind,source=$PWD/tmp/work,target=/work \
    -e DRY_RUN=True \
    -e ACTION=Apply \
    quay.io/redhat-services-prod/app-sre-tenant/er-aws-msk-connect-main/er-aws-msk-connect-main:latest
```
