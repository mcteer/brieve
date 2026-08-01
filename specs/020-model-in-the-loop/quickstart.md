<!-- SPDX-License-Identifier: Apache-2.0 -->
# Quickstart: watch a model choose, and watch a choice refused

**Nothing here runs yet** — the feature is planned. This is the validation guide the
implementation must make true.

## Prerequisites

- The enclave running (`make enclave-up`).
- A definition whose binding map names a qualified model, permitting **more than one** tool —
  a single-tool definition cannot show a choice being made.
- For step 4 only: a provider credential in `.env`.

---

## 1. Run a task and read the trail

Start a run through the surface 019 built, or by dispatch. Then read the evidence for its
correlation id.

**Expected**: a `tool_chosen` event per step, naming the model and the tool. Beside it, the
tool bracket that already existed.

**What to look for**: you can tell a chosen tool from a scheduled one. Before this feature you
could not — the trail recorded a tool running and said nothing about who picked it.

---

## 2. Watch a choice refused

Use a definition whose ceiling is narrower than the task suggests, so the model reaches for
something it may not have.

**Expected**: a `tool_chosen` event with the refusal recorded against it, then **another**
choice at the same step. The denial went back to the model and it tried again.

**Expected too**: the refusal came from the existing enforcement. Nothing in the choosing code
decided it.

---

## 3. Watch the bound hold

Narrow the ceiling until every reasonable choice is refused.

**Expected**: several recorded refusals, then a terminal run. **Not** an endless loop, and not
a run that quietly succeeded having done nothing.

This is the step worth doing by hand even though a row covers it: governance-as-a-signal is
only safe because of this bound, and it is the one property whose absence would look like the
feature working.

---

## 4. The real provider (FR-012)

Once, by hand, with a real model. Record what it chose and whether it was permitted.

**Everything above runs against the double.** This step is the one that proves the wiring
carries a real inference call, and it is why the double alone is not enough.

---

## What you have NOT proven

That the model chose **well**. A model picking the obviously right tool is persuasive and
proves only that the choice was governed — which is what this feature claims and the whole of
what it claims.

Stated here because step 1 will feel like more than it is, and that is exactly when it stops
being obvious.
