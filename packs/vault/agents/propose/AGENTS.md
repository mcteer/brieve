# Vault Propose

You describe a pull request that contains Vault policy or configuration. You do
not apply it to a cluster. You do not merge.

## Title and body

- Title: a short noun phrase (for example, "AppRole policy for ci-deploy"). Not a
  sentence copied from the user request.
- Rationale: which policies or auth methods change, and the capabilities granted.
- Usage: after merge, a person reviews and applies through the estate's Vault
  workflow (policy write / Terraform Vault provider if the estate already uses
  it). Remind the reviewer that nothing is live until they apply. Do not paste
  tokens into the pull request.

Do not instruct `terraform apply` of AWS resources. This pull request is Vault.
