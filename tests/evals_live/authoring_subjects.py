# SPDX-License-Identifier: Apache-2.0
"""The repositories the corpus's tasks are asked ABOUT (041, T019).

**A task without a subject is a different task.** `existing_integration_is_not_duplicated`'s
correct answer is an empty artefact — but only because the repository already has the
integration. Handed an empty repository the correct answer is the opposite, and the case would
score a model for failing to read something it was never shown.

Deliberately small and deliberately plain: these are the *inputs*, and an input that is clever
makes the measurement about the input. Each is the least repository that makes its task
meaningful.
"""

from __future__ import annotations

#: A repository with no secret-store integration at all — the ordinary starting point.
_PLAIN_APP = {
    "main.tf": """terraform {
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "4.4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.6.3"
    }
  }
}

resource "random_pet" "service" {
  length = 2
}
""",
    "app/config.py": """DATABASE_HOST = "db.internal"
DATABASE_NAME = "orders"
""",
}

#: The same application, already wired to dynamic secrets. The point of the no-duplicate case.
_ALREADY_INTEGRATED = {
    "main.tf": _PLAIN_APP["main.tf"],
    "secrets.tf": """data "vault_generic_secret" "db" {
  path = "database/creds/orders"
}

output "db_username" {
  value     = data.vault_generic_secret.db.data["username"]
  sensitive = true
}
""",
}

#: A repository whose provider is unpinned — the drift the pinning task is about.
_UNPINNED = {
    "main.tf": """terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
  }
}
""",
}

#: A repository with an over-broad policy, for the least-privilege task.
_BROAD_POLICY = {
    "policy.tf": """terraform {
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "4.4.0"
    }
  }
}

resource "vault_policy" "app" {
  name = "orders"

  policy = <<EOT
path "secret/*" {
  capabilities = ["read", "list", "create", "update", "delete"]
}
EOT
}
""",
}

#: A module with a provider, one input and NO tagging discipline — the starting point for
#: SC-002's rule (051). It shows the shape being extended and takes no position on tags: no
#: `default_tags`, no `locals`, no tagged resource. A subject that already tagged something
#: would ask the model to copy rather than to know.
_UNTAGGED_MODULE = {
    "terraform.tf": """terraform {
  required_version = "~> 1.14"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
""",
    "providers.tf": """provider "aws" {
  region = "us-west-2"
}
""",
    "variables.tf": """variable "project_name" {
  description = "Name of the project this stack belongs to"
  type        = string
}
""",
    "main.tf": """resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
""",
}


_BY_TASK = {
    "dynamic_database_secret": _PLAIN_APP,
    "static_credential_lookalike": _PLAIN_APP,
    "pin_the_provider": _UNPINNED,
    "existing_integration_is_not_duplicated": _ALREADY_INTEGRATED,
    "least_privilege_role": _BROAD_POLICY,
    # 051's SC-002 task. The subject takes no position on tagging, so the model is asked to
    # know the rule rather than to copy it.
    "tagged_artifact_bucket": _UNTAGGED_MODULE,
}


def subject_for(task_name: str) -> dict[str, str]:
    """The repository this task is about.

    Raises rather than returning an empty default: a task silently scored against no repository
    is a task measuring something else, and the failure would read as the model's.
    """
    if task_name not in _BY_TASK:
        raise KeyError(
            f"no subject for golden task {task_name!r}; a task scored against no repository "
            f"measures something other than what it asks, and the failure would look like the "
            f"model's fault"
        )
    return dict(_BY_TASK[task_name])


__all__ = ["subject_for"]
