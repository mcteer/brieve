<!-- SPDX-License-Identifier: Apache-2.0 -->
# The `write` role's qualification corpus (038)

The Qualified Model Matrix's third role, bound for the first time. Everything a `write` cell
is scored against lives here: golden tasks with **human-authored references**, and must-deny
cases covering secrets in output, exfiltration of analysed content, and injection resistance.

**This is not a per-pack suite.** `core.evals.suites.SUITES` is the per-pack list, and putting
authoring in it would demand a corpus from every pack for a capability most do not offer — the
mistake 037 made and the machinery caught. `AUTHORING_QUALIFICATION` sits beside
`INTAKE_QUALIFICATION` instead, required of a pack that **declares an authoring workflow** and
not asked of one that does not.

## What refuses when this directory is empty

`core.evals.authoring_corpus.load_corpus` raises `CorpusRefused` — it never warns and never
returns an empty tuple. A pack declaring an authoring workflow with no corpus is refused at
load. The floor is stated in numbers so "representative" is checkable at its edges:

- every golden task carries a **human-authored reference** with a **declared property set**,
  and records its **author** — so "human-authored" is a claim in the artefact rather than an
  intention in a review;
- at least one golden task is **syntactically valid and substantively wrong**, because a
  corpus that only catches malformed output has not measured integration correctness;
- must-deny cases span **all three** classes, and the injection class carries a **paired**
  subject, since it is scored by comparing artefacts with and without the injected text.

A task declaring neither a property set nor `expects_no_artifact` is refused: an empty
property set matches trivially, which is the vacuous pass `parse_cases` already refuses
elsewhere.
