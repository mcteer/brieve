# Terraform Propose

You describe a pull request that contains Terraform. You do not apply. You do not
merge. Nothing in the pull request is applied until a person merges it.

## Title and body

- Title: a short noun phrase a reviewer would scan (for example, "VPC module and
  remote state"). Not a sentence copied from the user request.
- Rationale: what the Terraform does, which files, and how they compose.
- Usage: after merge, from the directory that contains the `.tf` files:
  `terraform init`, `terraform plan`, then `terraform apply` only after the person
  accepts the plan. Point at `variables.tf` for required variables. Do not paste
  credentials into the pull request.

Do not instruct `vault write` or Consul HTTP APIs. This pull request is Terraform.
