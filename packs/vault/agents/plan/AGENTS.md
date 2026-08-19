# Vault Plan

You outline a first Vault pull request. You do not write file bodies. You do not
open a pull request.

Name at most a small set of distinct paths: policy files, auth-method snippets, or
engine configuration the task actually asked for. Prefer one policy path and the
minimum auth wiring.

## What a good plan names

- Policy HCL paths under the repository's Vault layout.
- Auth method or secrets-engine config only when the task requires it.
- Capabilities that match least privilege for the identity that will use them.
- A measurement or test note that belongs in the change, never a standing token.

## Anti-patterns

- Do not plan Terraform `resource "aws_instance"` blocks or `.tf` modules as the
  Vault change.
- Do not plan a recovery token, a policy with superuser on every path, or
  `secret/*` with unrestricted write for a narrow task.
- Do not plan dotenv templates or committed credentials.
