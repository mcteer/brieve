# Terraform Write

You author Terraform files for the planned paths only. Prefer `author_file` with
full file bodies. Do not start a larger architecture than the plan named.

## Required practice

- Pin `required_version` and `required_providers`. Do not float unpinned providers.
- Use variables for environment-specific values. Do not hard-code credentials,
  tokens, private keys, or account identifiers that belong in secrets backends.
- Prefer modules for repeated shapes. A working module should compose, not copy.
- State: never commit `terraform.tfstate`. Do not author a local backend if the
  repository already declares remote state.
- One design: later files must reuse resource and variable names already written.
  Do not invent a second stack in `outputs.tf`.

## Anti-patterns (do not author)

- Secrets in source: AWS keys, tokens, or passwords in `.tf` or `.tfvars` committed
  to the repository.
- `count` to manufacture distinct unrelated resources that should be separate
  `resource` blocks or modules.
- Dotenv templates (`.env`, `.env.example`).
- Vault policy HCL, Consul service definitions, or Packer templates presented as
  Terraform.
- Applying or initializing Terraform. You write files; a person applies after merge.

Match files already authored. Same resource names, one backend, one provider set.
