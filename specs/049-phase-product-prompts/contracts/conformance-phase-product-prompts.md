# Conformance: Product-and-phase Build instructions (049)

## Hermetic / CI

| ID | Claim | How it can lose |
| --- | --- | --- |
| A1 | Authoring packs ship five `agents/<phase>/AGENTS.md` files, each declared in `[[agents]]` with a matching digest | Load succeeds with four files, a digest mismatch, or a path that is not `AGENTS.md` |
| A2 | `load_phase_agents` for terraform research returns that file's digest, never vault's | Cross-pack body or digest |
| A3 | A terraform-bound run's `content_pins` contain `terraform/agents/<phase>@<version>` and no `vault/agents/*` | Vault keys present or terraform keys absent after Research |
| A4 | Missing Write `AGENTS.md` fails Write; later phases stay pending; no PR | Write skipped, Propose completes, or `open_proposal` runs |
| A4b | A candidate under `evals/prompt-tune/candidates/` is never executed; missing pin is `agents_missing` | Bind loads a candidate path or treats unpinned bytes as promoted |
| A5 | Empty `AGENTS.md` is `agents_empty`, same fail-closed as missing | Empty file steers the phase |
| A6 | Root contributor `AGENTS.md` and pack `SKILL.md` are not stand-ins | Bind succeeds using either |
| A7 | Zero or many `RUN_PACKS` refuse `pack_unbound` / `pack_ambiguous` | Defaults to terraform or concatenates |
| A8 | Ask path never sets `ChoiceRequest.instruction` from pack agents | Ask choose sees a Build `AGENTS.md` body |
| A9 | Judge bind uses judge cell + Judge file; Write bind uses write cell + Write file | Same binding for both, or Write file used at Judge |
| A10 | `src/core` stays product-blind; `dspy`/`gepa` not imported from served packages | New terraform identifier in core, or `import dspy` under `src/core` / served adapters/surfaces |
| A11 | `phase_agents` and `build_agents` each include known-fail fixtures at the data-model floor; loaders are `load_phase_agents_cases` / `load_build_agents_cases`, not `parse_cases` | Suites with only passing cases, or names added to `SUITES` / scored by `test_eval_gates` |
| A12 | `promote_phase_agents` refuses when either qualification is missing; a single-phase GEPA loss copies **zero** files | Promote returns evidence without both suites, or four files copy after one loss |
| A13 | Portal templates/JS do not contain phase instruction bodies or a prompt composer for them | Portal ships or selects `AGENTS.md` text |

## Enclave / named runner

| ID | Claim | Runner |
| --- | --- | --- |
| E1 | Connected, restricted, and air-gapped profiles execute the same pinned files (no public-web fetch at phase start) | Dan — allocation without outbound web still starts Research |
| E2 | Live GEPA then DSPy promotion can lose; a losing set is not copied into `packs/` | Dan — eval lane |
| E3 | SC-006: promoted Terraform and Vault full Builds show a **strictly higher** pass rate than generic pre-feature steer on `evals/authoring` golden tasks, same n; README records n, both rates, positive delta | Dan — eval lane |

**Named runner**: Dan McTeer (maintainer). Rows fail loudly when the enclave or eval broker
is absent (do not skip green).
