# Agent Instructions for er-aws-msk-connect

## What This Project Is

This is an **ERv2 (External Resources v2) module** that provisions and manages **AWS MSK Connect** resources (custom plugins, worker configurations, and Kafka connectors) via **app-interface**. It is owned by the AppSRE team at Red Hat.

## Reference Implementation

This project is modeled directly after [`app-sre/er-aws-msk`](https://github.com/app-sre/er-aws-msk), which provisions AWS MSK clusters. The local copy lives at `~/code/er-aws-msk`. **Always consult that repo when unsure about patterns, conventions, or framework usage.** The two projects share identical architecture -- only the AWS resources and data models differ.

## Relationship to app-interface

This module is tightly coupled to **app-interface** (`~/code/app-interface`), which is the configuration-as-code system where users declare the resources this module provisions. Understanding the app-interface side is essential for end-to-end context.

### How ERv2 modules are registered in app-interface

Each ERv2 module has a **module definition** file in `data/external-resources/modules/`. For the existing MSK cluster module, this is `data/external-resources/modules/msk-1.yml`:

```yaml
$schema: /external-resources/module-1.yml
provision_provider: aws
provider: msk
module_type: terraform
reconcile_drift_interval_minutes: 1440
reconcile_timeout_minutes: 120
outputs_secret_sync: true
channels:
- name: stable
  image: quay.io/redhat-services-prod/app-sre-tenant/er-aws-msk-main/er-aws-msk-main
  version: 0.7.0-36
```

This module will need an equivalent file (e.g., `data/external-resources/modules/msk-connect-1.yml`) with `provider: msk-connect` pointing to the `er-aws-msk-connect` container image.

### How users declare resources in namespace files

Resources are declared in namespace YAML files under `data/services/<team>/<service>/namespaces/`. The pattern is:

```yaml
managedExternalResources: true
externalResources:
- provider: aws
  provisioner:
    $ref: /aws/<account>/account.yml
  resources:
  - provider: msk              # this would be "msk-connect" for connectors
    identifier: <unique-id>
    managed_by_erv2: true
    defaults: /terraform/resources/path/to/defaults.yml
    output_resource_name: <k8s-secret-name>
```

### How defaults files work

The actual resource configuration lives in **defaults files** under `resources/terraform/resources/`. For MSK clusters, these use `$schema: /aws/msk-defaults-1.yml` and contain all the Terraform-level config (kafka version, instance type, subnets, etc.). This module will need a new schema (e.g., `/aws/msk-connect-defaults-1.yml`) with fields matching the `MskConnectData` Pydantic model.

### Where MSK resources currently exist in app-interface

The primary MSK clusters are declared in the **Insights/ConsoleDot strimzi** service:

- **Stage**: `data/services/insights/strimzi/namespaces/stage-platform-mq-stage.yml` (identifier: `consoledot-stage`)
- **Prod**: `data/services/insights/strimzi/namespaces/platform-mq-prod.yml` (identifier: `consoledot-prod`)
- **Perf**: `data/services/insights/strimzi/namespaces/perf-platform-mq-perf.yml` (identifier: `consoledot-perf`)

Defaults files live under `resources/terraform/resources/insights/{production,stage,perf}/`.

Assisted Installer also has MSK clusters in `data/services/assisted-installer/namespaces/`.

### Current Kafka Connect usage (Strimzi-based, not AWS MSK Connect)

All existing Kafka Connect deployments in app-interface are **self-managed Strimzi/AMQ Streams KafkaConnect** running on OpenShift -- not AWS MSK Connect. Key deployments:

- **Kessel Kafka Connect**: `data/services/insights/kessel/` -- runs Debezium connectors (e.g., `kessel-inventory-api-connector`, `hbi-host-migration-connector`). Connects to MSK using SASL/SCRAM.
- **xjoin-kafka-connect**: Strimzi-based, in the platform-mq namespaces.

**This module would be the first use of AWS-managed MSK Connect in the organization.** There are zero existing references to `mskconnect` or `msk-connect` in app-interface.

### What needs to happen in app-interface for this module

When this module is ready for deployment, the following must be added to app-interface:

1. **Module definition**: `data/external-resources/modules/msk-connect-1.yml` (registers the container image and provider)
2. **Defaults schema**: A new JSON schema for MSK Connect defaults (e.g., `/aws/msk-connect-defaults-1.yml`)
3. **Defaults files**: Per-environment configuration under `resources/terraform/resources/`
4. **Namespace declarations**: Add `provider: msk-connect` resources to the appropriate namespace files
5. **Provider exclusion**: Add `msk-connect` to `terraformResourcesProviderExclusions` in `data/app-interface/app-interface-settings.yml` (ensures ERv2-only handling)

## Architecture Pattern

The ERv2 module pattern works as follows:

1. A user declares a connector in **app-interface** (a configuration-as-code system).
2. `qontract-cli` generates an `input.json` file describing the desired state.
3. This module's Python code (`er_aws_msk_connect/__main__.py`) parses that input using Pydantic models and generates Terraform backend config and variable files.
4. The `er-base-terraform` base image runs `terraform plan` and then the **post-plan hook** (`hooks/post_plan.py`) validates the plan against live AWS APIs.
5. If validation passes, `terraform apply` creates the resources.
6. Terraform outputs are fed back as secrets to the target Kubernetes namespace.

### Key Framework: `external-resources-io`

All ERv2 modules depend on the [`external-resources-io`](https://pypi.org/project/external-resources-io/) library. It provides:

- `parse_model()` / `read_input_from_file()` -- input parsing
- `AppInterfaceProvision` -- base Pydantic model for provisioning metadata
- `create_backend_tf_file()` / `create_tf_vars_json()` -- Terraform config generation
- `TerraformJsonPlanParser` / `Action` / `ResourceChange` -- plan parsing for hooks
- `Config` -- configuration management
- CLI tool for generating `variables.tf` from Pydantic models (`external-resources-io tf generate-variables-tf`)

### How Pydantic Models Map to Terraform

The Pydantic models in `app_interface_input.py` define the input schema. The `MskConnectData` model fields are serialized to JSON and passed as Terraform variables. **The field names and nesting in the Pydantic models must exactly match the Terraform variable structure.** The `variables.tf` file is auto-generated from the Pydantic models via `make generate-variables-tf` -- never hand-edit it.

When `create_tf_vars_json()` is called with `exclude_none=False`, fields with `None` values are serialized as `null` in JSON. Terraform code must handle these nulls correctly (e.g., using `count` conditionals or `try()`).

## AWS Resources Managed

| Resource | Terraform Type | Notes |
|---|---|---|
| Custom Plugin | `aws_mskconnect_custom_plugin` | Single plugin per connector. Users combine JARs into one ZIP. |
| Worker Configuration | `aws_mskconnect_worker_configuration` | Optional. |
| CloudWatch Log Group | `aws_cloudwatch_log_group` | Conditional on log delivery config. |
| Connector | `aws_mskconnect_connector` | The core resource. IAM auth and TLS encryption are hardcoded. |

## Critical Design Decisions

1. **One connector per module invocation.** Do not add support for multiple connectors in a single Terraform state.
2. **One custom plugin per connector.** Users must combine multiple JARs into a single ZIP. Do not add support for multiple plugins.
3. **S3 bucket and plugin files are pre-existing.** This module does not create S3 buckets or upload plugin artifacts.
4. **IAM authentication is hardcoded.** It is the only valid auth type for MSK Connect. Do not make this configurable.
5. **TLS encryption is hardcoded.** Required for IAM auth.
6. **The `service_execution_role_arn` is required and pre-existing.** This module does not create IAM roles.

## Immutability Constraints (Important)

Most MSK Connect resources force replacement on any change:

- **`aws_mskconnect_custom_plugin`**: ALL arguments force replacement. Any change destroys and recreates.
- **`aws_mskconnect_worker_configuration`**: ALL arguments force replacement.
- **`aws_mskconnect_connector`**: Only `capacity` and `connector_configuration` can be updated in-place. Everything else (name, kafka_cluster, plugins, worker_config, service_execution_role, encryption, auth) forces replacement.

Both the custom plugin and worker configuration resources use `create_before_destroy` lifecycle rules and identifier-prefixed naming to handle replacements safely.

## Development Workflow

```bash
# Set up local dev environment
make dev

# Run linting, type checking, and tests locally
uv run ruff check
uv run ruff format
uv run mypy
uv run pytest -vv

# Build and test in container (uses podman)
make test

# Build prod image
make build

# Regenerate variables.tf from Pydantic models (after changing app_interface_input.py)
make generate-variables-tf

# Update terraform provider lock after bumping versions.tf
make providers-lock
```

## Testing Conventions

- All AWS API calls in hooks are mocked via `unittest.mock.patch`
- Shared fixtures live in `tests/conftest.py` with a `raw_input_data` dict and parsed `ai_input`
- Tests run inside the container during CI via `make in_container_test`
- Static analysis: ruff (ALL rules enabled), mypy (strict with Pydantic plugin), terraform fmt

## Container Build

The Dockerfile is a multi-stage build based on `er-base-terraform-main`:
- `base` -- sets up paths and venv
- `builder` -- installs deps, syncs terraform providers, copies source
- `prod` -- minimal runtime
- `test` -- adds dev deps, runs `make in_container_test`

Uses `uv` for Python dependency management. The `uv.lock` file must stay in sync with `pyproject.toml` (enforced by `uv lock --locked` in the build).

## CI/CD

Tekton pipelines in `.tekton/` via Konflux (Pipelines as Code):
- PRs build the `test` stage (runs all tests)
- Pushes to `main` build the `prod` stage and push to quay.io

## Common Pitfalls

- **Never hand-edit `terraform/variables.tf`** -- it is auto-generated from Pydantic models.
- **Never hand-edit `uv.lock`** -- use `uv lock` or `uv add` to modify dependencies.
- **Pydantic model field names must match Terraform variable nesting exactly** -- mismatches cause silent failures where Terraform receives null for fields it expects to be set.
- **Use `podman` instead of `docker`** -- this is a Fedora/RHEL environment.
- **The `capacity` block uses two mutually exclusive dynamic blocks in Terraform** (autoscaling vs provisioned_capacity). The mutual exclusion is enforced at the Pydantic layer via a `@model_validator`.
