+++
title = 'Terraform Module Input Summary Pattern'
date = 2026-06-27T00:00:00-05:00
draft = false
description = 'Field note on documenting Terraform AWS module inputs using a concise summary table to improve module usability, security review, governance, and reuse across platform teams.'
tags = ['terraform', 'aws', 'documentation', 'platform-engineering', 'governance', 'modules']
categories = ['field-notes']
+++

Terraform modules are easier to consume when engineers can understand their inputs without reading every line of source code. While reviewing an AWS Terraform Kinesis module, I created an input summary table with six columns: **Input**, **Type**, **Default Value**, **Required**, **Notes**, and **Recommendation**. The goal was simple: make the module safer and faster to use by turning variable definitions into an operator-friendly interface.

## The Problem This Solves

Terraform modules often start clean and become harder to consume over time. Inputs are added for new capabilities, defaults change, conditional behavior grows, and security-sensitive options become mixed with ordinary configuration. The source code still contains the truth, but consuming the module requires reading `variables.tf`, resource blocks, locals, conditionals, and sometimes provider documentation.

That creates friction for several audiences:

- **Application engineers** need to know which inputs are required and what safe defaults look like.
- **Platform engineers** need to explain intended usage without becoming the help desk for every module invocation.
- **Security and governance reviewers** need to understand encryption, IAM, tagging, alarms, and data retention behavior quickly.
- **Technical managers** need a readable view of what the module allows and where the risk is concentrated.

The input summary table acts as a thin translation layer between Terraform implementation detail and practical module consumption.

## Why Module Input Documentation Matters

Terraform module inputs are the module's public interface. If that interface is unclear, users make assumptions. Some assumptions are harmless. Others affect encryption, IAM access, retention, observability, and cost.

Good input documentation helps answer questions before the module is used:

- Which values are truly required?
- Which defaults are safe for production?
- Which inputs are conditionally required?
- Which settings affect security posture?
- Which settings affect cost?
- Which values should normally be left alone?
- Which values require coordination with another team?

Without that context, engineers may copy a minimal example, accept defaults blindly, or cargo-cult values from another workspace. The module may still deploy successfully, but success at `terraform apply` time does not mean the configuration is operationally sound.

## The Input Summary Format

The table format I used was intentionally simple:

| Column | Purpose |
|---|---|
| Input | Variable name exposed by the module |
| Type | Terraform type, such as `string`, `bool`, `list(string)`, `map(string)`, or `object` |
| Default Value | Default from `variables.tf`, or `-` when no default exists |
| Required | Whether the caller must provide a value, including conditional requirements |
| Notes | Plain-language behavior and constraints |
| Recommendation | Practical guidance for normal usage |

A small excerpt from the Kinesis module summary looked like this:

| Input | Type | Default Value | Required | Notes | Recommendation |
|---|---|---|---|---|---|
| `name` | `string` | `-` | Yes | Unique stream name. Final resource name is built from `{name_prefix}{name}`. | Use a descriptive name that identifies workload and purpose. |
| `stream_mode` | `string` | `"ON_DEMAND"` | No | Valid values are `PROVISIONED` or `ON_DEMAND`. `PROVISIONED` requires `shard_count`. | Use `ON_DEMAND` unless throughput is predictable and intentionally provisioned. |
| `shard_count` | `number` | `null` | Conditional | Required only when `stream_mode` is `PROVISIONED`. | Size according to expected throughput and AWS Kinesis guidance. |
| `encryption_type` | `string` | `"KMS"` | No | Valid values are `NONE` or `KMS`. | Keep `KMS`; avoid `NONE` unless there is an approved exception. |
| `firehose_encryption_enabled` | `bool` | `true` | No | Controls server-side encryption for the Firehose S3 target. | Keep enabled and clarify whether AWS-managed or customer-managed keys are required. |

This format is not complicated, which is the point. A useful module interface summary should be easy to scan, easy to review, and easy to paste into a design document or onboarding guide.

## How The Format Improves Usability

The table makes the module easier to consume because it separates caller-facing decisions from implementation details.

Instead of asking engineers to infer behavior from Terraform expressions like this:

```hcl
kms_key_id = var.encryption_type == "NONE" ? null : var.kms_key_id
```

The table states the operational behavior directly:

```text
kms_key_id is used only when encryption_type is KMS. Prefer a customer-managed key for production workloads.
```

That shift matters. Most module consumers do not need to understand every internal expression on first pass. They need to know what to provide, what the default does, and what decision they are making by overriding it.

## Security And Governance Value

The Kinesis module exposed several inputs with security or governance impact:

- `encryption_type`
- `kms_key_id`
- `firehose_encryption_enabled`
- `policy_write_roles`
- `policy_read_roles`
- `tags`
- `retention_period`
- `alarm_sns_topics`
- `alarm_metric_thresholds`

Documenting these inputs in a summary table made review easier because the risky decisions were visible in one place.

For example, the module defaulted `encryption_type` to `KMS`, which is a good baseline. But `kms_key_id` defaulted to `alias/aws/kinesis`, while the description recommended a customer-managed key. That distinction matters for governance. The module is encrypted by default, but the default may not satisfy stricter key ownership, rotation, audit, or separation-of-duties requirements.

Likewise, `firehose_encryption_enabled` defaulted to `true`, but the implementation used S3-managed encryption (`AES256`) when enabled. The input description said the default was encrypted with an AWS-owned CMK. That wording is worth tightening because AWS-owned, AWS-managed, customer-managed, and S3-managed encryption are not interchangeable governance terms.

The table made those gaps easier to discuss without turning the review into a line-by-line Terraform walkthrough.

## Risks And Gaps Discovered

Documenting the inputs surfaced several areas worth improving.

### Encryption Wording

The module differentiated Kinesis stream encryption and Firehose/S3 output encryption, but the descriptions could be clearer.

For Kinesis:

- `encryption_type = "KMS"` enables KMS encryption.
- `kms_key_id = "alias/aws/kinesis"` uses the AWS-managed Kinesis key by default.
- Production guidance may require a customer-managed key instead.

For Firehose output:

- `firehose_encryption_enabled = true` enabled S3 server-side encryption.
- The implementation used `AES256`, which is S3-managed encryption.
- If customer-managed KMS is required for S3, the module would need additional inputs for KMS key selection.

### Conditional Requirements

`shard_count` is not always required. It becomes required when `stream_mode` is `PROVISIONED`. This is exactly the kind of condition that should be explicit in the `Required` column.

Without that note, callers may either provide unnecessary values for `ON_DEMAND` streams or omit required values for provisioned streams.

### Defaults Need Interpretation

Defaults are not automatically recommendations. Some defaults are safe. Some are placeholders. Some are low-friction starting points but not production standards.

Examples:

- `retention_period = 24` is valid but may be too short for replay or incident recovery needs.
- `tags = {}` is technically valid but may violate tagging policy if required tags are not supplied elsewhere.
- `alarm_metric_thresholds = {}` means no alarms are provisioned unless thresholds are configured.

The `Recommendation` column is useful because it explains whether the default should be accepted, reviewed, or overridden.

### Alarms Are Opt-In

The Kinesis module included `alarm_sns_topics` and `alarm_metric_thresholds`, but alarms were not enabled unless thresholds were configured. That is a reasonable module pattern, but it needs to be obvious.

Otherwise, a caller may provide SNS topics and assume alerting exists, when no alarm resources are created because thresholds are empty.

### Tagging Depends On Merge Behavior

The module merged caller-provided tags with tags from a shared variable module:

```hcl
tags = merge(var.tags, module.eits_vars.tags)
```

That behavior should be documented because tag precedence matters. If shared tags override caller tags, that is one governance outcome. If caller tags override shared tags, that is another. The input summary should identify the merge pattern or link to the module's tagging standard.

### Validation Is Uneven

`encryption_type` had validation for `NONE` or `KMS`, which is good. Other inputs could benefit from similar validation or stronger typing guidance.

Potential improvements:

- Validate `stream_mode` as `ON_DEMAND` or `PROVISIONED`.
- Validate `retention_period` between 24 and 8760.
- Validate `stream_consumer_names` count at or below the Kinesis limit.
- Validate IAM role ARN format for read/write role lists.
- Add validation or preconditions for `shard_count` when `stream_mode = "PROVISIONED"`.

## Reusable Pattern Across AWS Modules

This documentation pattern can be reused across other AWS Terraform modules with very little change.

Good candidates include:

- S3 bucket modules
- Lambda modules
- SQS and SNS modules
- DynamoDB modules
- IAM role modules
- VPC and subnet modules
- RDS modules
- CloudWatch alarm modules
- EKS add-on modules

The same six columns work because most module consumption questions are consistent across AWS services:

- What do I have to provide?
- What happens if I provide nothing?
- Which defaults are safe?
- Which values affect security?
- Which values affect cost?
- Which settings are conditional?
- What does the platform team recommend?

For security-sensitive modules, the summary can be extended with additional columns such as **Security Impact**, **Cost Impact**, or **Policy Requirement**. I would avoid adding those by default unless they are consistently maintained. A small table that stays current is more valuable than a large table nobody trusts.

## Practical Recommendations

For future Terraform module documentation, I would standardize on this approach:

1. **Generate the first pass from `variables.tf`.** Capture variable name, type, default, and description.

2. **Manually add operational context.** The `Notes` and `Recommendation` columns should be written by someone who understands how the module is used.

3. **Call out conditional requirements explicitly.** Avoid hiding important behavior in prose.

4. **Separate default from recommendation.** A default tells users what Terraform does. A recommendation tells users what they should normally do.

5. **Review security-sensitive wording carefully.** Encryption, IAM, logging, retention, and tagging language should match governance terminology.

6. **Add validation where documentation reveals ambiguity.** If the table needs a long warning for an input, the module may need validation or preconditions.

7. **Keep the table close to the module.** Store it in `README.md` or generated documentation so it changes with the module.

8. **Reuse the pattern across modules.** A consistent input summary format lowers cognitive load for every engineer consuming platform modules.

## Next Steps

The Kinesis module input table was useful as documentation, but it also acted as a review tool. It exposed unclear encryption wording, conditional requirements, observability defaults, and validation opportunities.

The next step is to make this repeatable:

- Add the input summary table to the module README.
- Review encryption language with security/governance stakeholders.
- Add validation for `stream_mode`, `retention_period`, and conditional `shard_count` behavior.
- Clarify alarm behavior when SNS topics are set but thresholds are empty.
- Document tag merge precedence.
- Apply the same summary format to the next AWS Terraform module.

The broader lesson is simple: module documentation is not just user assistance. It is part of the module interface, and it is one of the cheapest ways to improve platform usability, security review, and operational consistency.
