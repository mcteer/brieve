# Provenance — adopted Terraform skills

**This content was not written here.** It is adopted from upstream under ADR-0004, which is
the whole reason the Terraform pack exists: a supply chain needs a genuine subject, and two
authored packs would have given it none — no real provenance to check, no real version to
pin, nothing anyone else wrote to review for injection.

## Where it came from

| Field | Value |
| --- | --- |
| Repository | [`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills) |
| Commit | `8c6573abbd21e8094fab8f538eb5f97db63133fd` |
| Licence | MPL-2.0 (`skills/LICENSE`, copied verbatim) |
| Retrieved | 2026-07-29 |
| Upstream path | `terraform/code-generation/skills/terraform-style-guide/` |

Content is **unmodified**. The digests in `../pack.toml` are over these exact bytes, and
loading verifies them — a skill whose content changed without its pin changing is the
ungated drift Principle VIII exists to stop, and it is invisible without a hash.

## What was adopted, and what was not

Upstream ships 94 files across four plugins (`code-generation`, `module-generation`,
`provider-development`, `policy`). **One skill was adopted**, deliberately.

Adoption is a reviewed act, and the review is only meaningful at a size a person actually
reads. Vendoring 94 files and recording "reviewed" against all of them would be the passing
stub ADR-0047 forbids, wearing a supply chain's name. The remaining skills are adopted the
same way when someone reviews them — the mechanism is built and the corpus grows through it,
which is the state ADR-0004 describes rather than a gap.

## Injection-lens review

**Performed at vendoring, on 2026-07-29, over the full text of both files.**

This is deliberate and it is not what `promote_skill()` does. That path governs **bumps** —
content that was reviewed once and changed. Content arriving for the *first* time has never
been reviewed by anything, and treating first-import as a bump would let it in unread.

**Result: clear.** Neither file contains instruction-shaped text targeting the agent. There
are no attempts to override system instructions, no requests to reveal or transmit context,
and no redirection of tool use. Both read as what they claim to be — Terraform style and
security guidance addressed to whoever is writing HCL.

**One observation, recorded rather than treated as a refusal.** `SKILL.md` advises: *"Use
the latest major version of each provider and the latest minor version of Terraform."* In
this platform's vocabulary "latest" is a moving target and FR-011 forbids auto-tracking —
but the two are about different subjects. That sentence is guidance to a person writing
Terraform about *their* provider constraints; it is not a directive to this platform about
*its own* artifacts, and nothing reads it as one. It is noted here because a review that
found nothing at all would be worth less than one that says what it looked at and where it
had to think.

**The honest limit.** This review is a human reading two files. The automated lens in
`core/evals/promotion.py` is pattern-based by necessity and catches known shapes rather than
novel phrasing — it is a floor, not a guarantee, and ADR-0004's human review is what covers
the rest. This document is that review for this import.
