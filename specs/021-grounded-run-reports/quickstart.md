<!-- SPDX-License-Identifier: Apache-2.0 -->
# Quickstart: read a run, and find the gap it admits to

**Nothing here runs yet** — the feature is planned. This is the validation guide the
implementation must make true.

## Prerequisites

- The enclave running (`make dev-up`) for steps 2 onward.
- **Resync the VM clock first**: `docker run --rm --privileged alpine hwclock -s`. Dispatched runs
  fail at startup on `nbf` when the container clock drifts behind the host, and it presents as a
  different random subset of rows failing each time.

---

## 1. Compile a report with no infrastructure at all

Feed recorded entries to the compiler in a Python session and print the result.

**Expected**: a report, with every claim carrying a status and the evidence behind it.

**What to look for**: you did not stand anything up. The compiler holds no query and no
credential, which is why this works — and it is the same property that makes "a report grants no
new access" structural rather than promised.

---

## 2. Watch a run observe itself

Dispatch a run that invokes `vault_write` — a non-repeatable tool with a real observer — and read
the trail for its correlation id.

**Expected**: before the terminal checkpoint, an observation event per effect, naming the outcome
the observer returned.

**What to look for**: the observation is written by the **allocation**, under the identity it
attested with. Nothing on the host observed anything. That placement is the whole Principle IV
redesign — a read-back performed for a reader would run under the surface's authority and hand
them an observation they may have no right to make.

---

## 3. Make an effect not land, and read the report

Arrange the interrupted-write state the 014 rows use — an effect whose metadata is absent — then
compile the report.

**Expected**: the claim reads `contradicted`, not `observed`, and nowhere does the report say the
write completed.

**This is the failure ADR-0018 opens with**: "applied successfully to three workspaces" when a
fourth silently failed. It is the one worth doing by hand even though a row covers it.

---

## 4. Ask for a run you did not start

As a different subject in the same tenant, request the report.

**Expected**: you get it. **And it contains no part of the run's result payload.**

**What to look for**: both halves. Reports are for auditors, compliance, and change reviewers as
much as for the person who started the run — but `get_run_result` is subject-restricted, so a
report carrying that payload would route straight around it.

Then try a run in another tenant. **Expected**: exactly what a run that does not exist returns —
same reason code, same message.

---

## 5. Watch the fifth gate turn on

```bash
make evals
```

**Expected**: five suites, not four. `report_fidelity` no longer appears in `suites.py`'s `OWED`
dictionary, and the constitution's eval-gate row has no owed member left.

**Then break it deliberately**: remove a case file and re-run. It must **fail**, not skip — a
suite that cannot run reports failure, which is the discipline the other four already hold.

---

## What you have NOT proven

**That the report is present-tense.** Every observation is a fact about run-end. A product that
changed afterwards reads exactly like one that never changed.

Stated here because step 3 will feel like proof that the platform is watching the product, and it
is not — it is proof that the platform *looked once, at the right moment, under the right
authority*, and wrote down what it saw.
