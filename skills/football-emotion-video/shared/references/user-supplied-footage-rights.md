# User-Supplied Footage Rights Workflow

Use when footage-rights assessment returns `user_must_supply_rights` or when the user claims they own/have licensed match footage.

## Required evidence

Ask for one of the following before treating user-supplied footage as usable:

- written license or permission document;
- proof of accreditation/rightsholder authorization;
- original footage ownership proof for user-shot video;
- purchase/download receipt plus terms that allow editing/public upload;
- explicit written statement from the user that the footage is for private/local/non-public testing only.

## Artifact

```yaml
user_supplied_footage_rights:
  footage_asset_id: string
  supplied_by_user: true
  evidence_type: license_document | accreditation | original_recording | purchase_terms | private_testing_statement | none
  evidence_location: string | null
  allowed_use: public_upload | private_testing | internal_review | unknown
  restrictions: [string]
  checked_date: string
  verification_status: verified_from_source | user_supplied | needs_more_info
  decision: usable_as_supplied | private_testing_only | needs_more_info | reject
```

## Rule

Do not convert `user_must_supply_rights` into `approved` without this artifact. This workflow records evidence and permitted use; it does not provide legal advice.
