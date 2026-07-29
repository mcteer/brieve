# Conformance: The Portal Surface

**Feature**: `specs/012-conversational-portal` | **Date**: 2026-07-29 | **Status**: **In force** (as of 012's merge)

The portal's obligation is **containment, not equivalence** (spec clarification,
2026-07-29): the parity row keeps binding API↔MCP, and the portal's rows assert it adds
nothing. These rows are blocking from the moment this feature lands (ADR-0047).

---

## Containment rows *(new: `tests/conformance/portal/` — wired into the Makefile in the same change that creates it; 010's invisible-directory lesson)*

| Row | Asserts | How |
| --- | --- | --- |
| One egress module | `surfaces/portal/relay.py` is the only portal module importing an HTTP client | The `test_no_live_dependencies` pattern, applied to the portal package |
| Catalogued operations only | Every request the portal makes to the platform is a catalogued operation | Instrumented relay under a scripted session covering every page and action; the request log maps 1:1 onto `operations.snapshot.json` entries |
| Token relay, no service identity | Every relayed request carries the session's token; the portal holds no credential of its own | Assembly inspection + relay assertion; no Vault access, no static key, no client secret anywhere in `surfaces/portal` |
| SSE is cadence, not capability | The event stream's content is sourced solely from catalogued reads made with the requesting person's token; a 403 ends the stream | Scripted session with narrowed authority mid-stream |
| Thin client is structural | Served JS contains no fetch target beyond the portal origin, no model endpoint, no decision logic; total served-script surface is enumerable | Reads the actual served bytes — SC-006 "verified against the delivered client" |
| Nothing survives the session | Browser storage holds only the opaque session cookie; served JS never touches localStorage/IndexedDB; sessions die with process or token expiry | Playwright storage inspection after a full scripted session (FR-020b) |

## Evidence rows *(in `tests/component` + `tests/conformance/api`)*

| Row | Asserts |
| --- | --- |
| Evidence first | The `TURN_RECORDED` event exists for every **accepted** turn — dispatched, declined, scope-refused — written before dispatch; pre-acceptance refusals produce `TURN_REFUSED` (size, never content) |
| Reconstruction | A thread with dispatched, declined, and refused turns is reconstructed **completely** from the trail alone; then the thread is deleted and the reconstruction is unchanged (SC-004, SC-009a) |
| Deletion masks nothing | `THREAD_DELETED` is in the chain; every run the thread started remains explainable — rationale, subject, order — from the trail |
| Verbatim context | The second run's received context is byte-identical to the first run's recorded result (SC-002); the bound's drops appear on the turn and in its event |
| No inherited authority | A turn dispatched after the subject's roles narrowed is authorized against the narrowed roles (FR-008); the earlier turn's authority is nowhere consulted |

## Break fixtures — run, not described

All six were applied to the tree, the row watched to fail, and the change reverted.
**Every one was detected**, which is worth recording because 011's equivalent exercise
found one fixture in four survivable — and that one guarded the defect the feature was
most likely to reintroduce. The list below is what was run.

| Fixture | Caught by |
| --- | --- |
| Dispatch before record (decline branch) | `test_every_accepted_disposition_is_recorded_with_the_message` |
| Carried context truncated by one byte | `test_carried_context_is_byte_identical_to_what_was_recorded` |
| A page handler reaching past the relay | `test_row_only_declared_modules_can_reach_the_network` |
| The token written into the cookie | `test_the_cookie_carries_an_opaque_id_and_never_the_token` |
| A refusal record carrying the message | `test_an_oversized_message_is_refused_and_its_content_is_not_recorded` |
| An unconditional client reload | `test_row_the_client_does_not_reload_unconditionally` |

**Two defects were found by running the gates rather than by these fixtures**, and both
were in code no hermetic row executes:

- **The session cookie was unusable in a browser.** `__Host-` requires `Secure`; a
  `secure_cookies=False` development flag made a real browser reject the cookie outright.
  The flag is gone — `Secure` is no longer configurable.
- **The client reloaded on every stream close**, which on a settled thread is an infinite
  loop. The accessibility gate ran in 117 seconds while looping and 1.9 after the fix.

Both are the argument for a lane that drives a real browser, stated as evidence rather
than as a preference.

## Break fixtures worth naming

- **A turn that dispatches before it records.** Reorder steps 4 and 5 of `send_turn`; the
  evidence-first row must fail. The plausible defect is an early-return decline path that
  skips the event — so the fixture breaks the *decline* branch specifically, where the
  event is the only copy.
- **A summarizing context carrier.** Truncate one carried result by a byte; the verbatim
  row must fail on byte-comparison, not on length heuristics.
- **A portal fetch that bypasses the relay.** Add a direct `urllib` call in a page
  handler; the one-egress-module row must fail.
- **A session that persists.** Write the token into the cookie instead of the opaque id;
  the nothing-survives row must fail on cookie-content inspection.

## The accessibility gate *(new lane: `tests/a11y/`, `make a11y`, dedicated CI job)*

Automated: Playwright renders every page state — thread list (empty, populated), thread
with all three run dispositions, decline, scope-refusal, delete confirmation,
API-unreachable — and a **pinned, vendored axe-core** run fails the build on any WCAG 2.2
AA violation (FR-020a).

**What the automated gates assert (FR-020a-i)** — this list was once "what needs a
human", and that was wrong. A browser can walk a tab order, read the accessibility tree,
measure a focus ring, and re-render under the criteria's own conditions. A checklist
nobody has run is worse than a row that runs on every commit.

`tests/a11y/test_keyboard_and_screenreader.py` covers what the scanner cannot:

| Criterion | How it is asserted |
| --- | --- |
| 2.4.3 Focus Order | Walks the real tab sequence and compares it against **visual** reading order by bounding box — the actual criterion, not "an order exists" |
| Screen-reader flow | Chrome DevTools Protocol `Accessibility.getFullAXTree` — the same tree the browser hands assistive technology — asserting every interactive node has an accessible name |
| Status announcement | Asserts the run-state element sits in an `aria-live` region, so a person is told the run progressed rather than the page changing silently |
| 2.4.13 Focus Appearance | Reads the **computed** style of each focused element; a stylesheet rule proves nothing if a later one removes it |
| 2.4.11 Focus Not Obscured | Checks the focused element is in the viewport and that `elementFromPoint` returns it rather than something painted over it |
| 2.5.8 Target Size | Measures every interactive element against 24×24 CSS px |
| 1.1.1 Non-text Content | Catches the failures that actually occur: missing alt, filename alt, and the literal word "image" |
| 2.5.7 Dragging Movements | Asserted as an absence: no `draggable` elements |
| 1.4.10 Reflow | Re-renders at 320 px and asserts no horizontal scrolling |
| 1.4.12 Text Spacing | Applies the criterion's own spacing values and asserts nothing is clipped |
| 1.3.1 / 2.4.2 / 3.1.1 | Landmarks, one `h1`, a skip link, a document language, a title |

**Three real defects were found the first time this harness ran**, all of which the
"needs a human" version would have shipped:

- **No live region.** The client updated a run's state in place, so a screen-reader user
  was never told anything had happened — on a surface whose entire purpose is watching
  work.
- **A 174×18 delete control**, under the 24 px minimum.
- `page.accessibility` no longer exists in Playwright 1.58, which is why the harness reaches
  for CDP instead — a stronger source, arrived at by the API being gone.

### What is still not automated

Narrow, and stated so the boundary stays visible:

- **Whether the words are good.** Whether "Send" is the right label, whether a decline's
  explanation actually helps, whether the reading level suits the audience. That is content
  review, not conformance testing.
- **Any specific screen reader's behaviour.** These rows assert against the accessibility
  tree, which is what assistive technology consumes — but JAWS, NVDA, and VoiceOver differ,
  and a page that satisfies every row here can still read oddly in one of them. Finding that
  out needs the software itself.

**No named runner is owed.** The gate runs in CI on every commit; there is no pending
manual pass, and nothing about this feature's accessibility is waiting on somebody
remembering to look.

## Eval gates — scoped absence

Constitution eval gates (must-decline suites, citation accuracy) bind **packs, prompts,
models, and policies**. This feature ships none — the decline path is deterministic and
the answering classes are split out — so no eval gate binds here. Recorded so the absence
reads as scoped rather than forgotten; the answering feature inherits this paragraph as
its starting obligation.

## Gate run at 012 (T060)

Against a live enclave, on a clean tree:

| Gate | Result |
| --- | --- |
| `make check` | 532 passed |
| `make conformance` — hermetic | 92 passed |
| `make conformance` — in-allocation durability | 81 passed, under an attested workload identity, no token anywhere |
| `make conformance` — enclave-marked | 10 passed |
| `make conformance` — host lane | 15 passed (12m30s; the divergence rows wait for real allocations) |
| `make conformance` — portal containment | 8 passed |
| `make a11y` | 8 passed |

Exit status 0 for both `make conformance` and `make a11y`.

**One defect was found by this run and nothing before it**: every dispatched allocation
died with `relation "run_inputs" does not exist`. The entrypoint reads its input at run
start, and the table had been left to the API service's migrate-on-boot — but the API had
never been deployed before this feature, so on an enclave brought up beforehand it did not
exist. `infra/bin/enclave-up` now applies the thread schema in the same pass as the others,
and its comment — which already said this rule had bitten three times — says four.

## Sealed-core review

One sealed-core change: three additive `AuditEventType` members (`TURN_RECORDED`,
`TURN_REFUSED`, `THREAD_DELETED`). Approved spec: this feature's. Security-maintainer review: Dan.
