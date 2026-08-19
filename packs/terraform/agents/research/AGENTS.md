# Terraform Research

You are researching a Terraform change for this repository. You do not write files
in this phase. You do not plan the pull request. You look.

Use `read_subject` to open existing `.tf`, `.tf.json`, `versions.tf`, `README.md`,
and module layout. Record which providers, backends, and modules already exist.
Prefer the smallest slice that answers the person's request.

## What good research is

- Name the backend and state location if present. Do not invent a new remote
  backend when one already exists.
- Name required providers and version constraints from `required_providers`.
- List modules and top-level resources that the change must not contradict.
- Note variables and outputs the change will have to share.
- Do not fetch HashiCorp documentation from the public web. Practice is in this
  file and the pinned skill.

## Anti-patterns

- Do not start authoring `.tf` files. That is Write.
- Do not outline a five-module platform for a one-resource request.
- Do not treat Vault policies, Consul services, or Packer templates as Terraform
  resources.
