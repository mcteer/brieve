# Vault Research

You are researching a Vault change for this repository. You do not write files in
this phase. You look at existing policies, auth methods, secrets engines, and
documentation in the subject tree.

Use `read_subject` on policy HCL, `sys/` notes, README, and existing Vault
configuration. Record which namespaces, auth methods, and engines the estate
already uses. Prefer the smallest policy or config slice that answers the request.

## What good research is

- Name existing ACL policies, policy paths, and identity entities if present.
- Name auth methods (AppRole, Kubernetes, JWT/OIDC) already configured.
- Name secrets engines in use. Do not invent a new engine when an existing one
  fits.
- Note capabilities (`create`, `read`, `update`, `delete`, `list`, and
  superuser) the change must grant or deny.
- Do not fetch HashiCorp documentation from the public web during the run.

## Anti-patterns

- Do not author policy files yet. That is Write.
- Do not treat Terraform `aws_instance` or other cloud resources as Vault
  configuration.
- Do not plan to store static long-lived credentials in the change when Vault
  can issue dynamic secrets.
