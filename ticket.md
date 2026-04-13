# ERv2 Module: AWS MSK Connect

## Problem Statement

Teams need to provision and manage AWS MSK Connect connectors via app-interface. No
ERv2 module exists for MSK Connect today. All existing Kafka Connect deployments in the
organization are self-managed Strimzi on OpenShift — this would be the first use of
AWS-managed MSK Connect.

---

## Resources

- Reference implementation: `app-sre/er-aws-msk` (MSK cluster module — same ERv2 patterns)
- AWS docs: `aws_mskconnect_connector`, `aws_mskconnect_custom_plugin`, `aws_mskconnect_worker_configuration`

---

## Implementation Ideas

- Follow `er-aws-msk` module structure exactly (Python + Pydantic + Terraform + hooks)
- One connector per module invocation (standard ERv2 pattern)
- Hardcode IAM auth and TLS — no other valid options for MSK Connect
- Post-plan hook validates subnets, security groups, and S3 plugin object before apply
- S3 bucket, plugin artifact, and IAM role are pre-existing (managed by other modules)

---

## Acceptance Criteria

- [ ] Module provisions `aws_mskconnect_connector` and `aws_mskconnect_custom_plugin`
- [ ] Optional `aws_mskconnect_worker_configuration` support
- [ ] Optional CloudWatch and/or S3 log delivery support, including CloudWatch log group creation
- [ ] Capacity supports both autoscaling and provisioned modes (mutually exclusive)
- [ ] Post-plan validation: subnets exist + same VPC, security groups exist + same VPC, S3 plugin object exists
- [ ] Outputs synced as Kubernetes secrets: `connector_name`, `connector_version`, `custom_plugin_path`, `worker_configuration`, `log_group_name`
- [ ] app-interface module definition created (`data/external-resources/modules/msk-connect-1.yml`)
- [ ] app-interface defaults schema created (`/aws/msk-connect-defaults-1.yml`)
- [ ] `msk-connect` added to `terraformResourcesProviderExclusions` in app-interface settings

---

## Default Acceptance Criteria

- [ ] All existing/affected SOPs have been updated
- [ ] New SOPs have been written
- [ ] The feature has both unit and end to end tests passing in all test pipelines and through upgrades
- [ ] If the feature requires QE involvement, QE has signed off
- [ ] The feature exposes metrics necessary to manage it (VALET/RED)
- [ ] The feature has had a security review
- [ ] Contract impact assessment
- [ ] Documentation is complete
