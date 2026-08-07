# Roadmap

What ships in what order, and why that order. Derived from the decision record
([`docs/adr/`](docs/adr/)) and the constitution's Quality Gates — not a separate plan.

**This file is guidance, not governance.** Where it conflicts with an Accepted ADR or the
constitution, those win and this file is corrected. Its job is to stop feature sequencing from
being re-derived at the start of every spec.

## How to use it

- **Starting a feature?** Take the top of [Next](#next). If you take something else, say why in
  the spec's Assumptions.
- **Deferring something in a spec?** Every "out of scope" line is a promise. Add it here, or to
  [Demand-driven](#demand-driven--trigger-gated) if it should never be scheduled by default.
- **Landing a feature?** Move it to [Shipped](#shipped), and move any Quality Gate row it
  attached out of [Owed gate rows](#owed-quality-gate-rows). ADR-0047 makes those rows binding
  the moment their feature exists.

## Shipped

**Two features were missing from this table and a third was recorded nowhere at all — corrected
2026-08-07.** 032 shipped 2026-08-03 and never got a row, which also left 031's *Owed onward*
reading as open for four days after 032 discharged it. 040 merged as `682b6ab` and the
change-proposal table below still called it *planned*. And 039 was specified, then superseded the
next day, with nothing on this page saying either thing happened. **This is the third instance of
the defect this file warns about in its own [Next](#next) section** — a planner reads this page
first, and it was describing a platform three features behind.

| # | Feature | ADRs realized | Gate rows attached |
| --- | --- | --- | --- |
| 001 | Dev toolchain | ADR-0007, ADR-0028 | — |
| 002 | Governed core | ADR-0006, ADR-0009, ADR-0020, ADR-0037 | — |
| 003 | Per-task authority | ADR-0015, ADR-0026 (partial), ADR-0042, ADR-0044 | — |
| 004 | Primary adapter | ADR-0001, ADR-0017, ADR-0019, ADR-0047 | Governance-ordering, fail-closed, governed entry |
| 005 | Durable execution | ADR-0024, ADR-0026, ADR-0048, ADR-0018 (consumes) | All seven durability rows |
| 006 | Deployment module tree | ADR-0025, ADR-0048, ADR-0015, ADR-0007 | — (infrastructure; the durability rows now run under an attested identity) |
| 007 | Control Groups | ADR-0016, ADR-0015, ADR-0048 | — (no new blocking row; component tests against the real Vault) |
| 008 | Northbound API | ADR-0033 (first transport), ADR-0035, ADR-0016 (consumes), ADR-0015 | Seventeen API rows, nine needing the enclave. **Parity deliberately not claimed** — one transport is nothing to compare |
| 009 | MCP surface | ADR-0033 (second transport), ADR-0049 (**resolved by building it**), ADR-0035, ADR-0048 | Fifteen MCP rows. **Surface parity claimed** — the row 008 could not assert, now that there are two transports to compare |
| 010 | Production identity fabric | ADR-0015 (**first feature that reads the registry at runtime**), ADR-0050 (new), ADR-0044 (mirroring seam; credential translation still deferred), ADR-0048 | Identity rows against the live trust fabric, in-allocation. **The gap every prior feature rested on** |
| 011 | Northbound API operations | ADR-0033 (the parity row grows with the catalogue), ADR-0034 (the portal's precondition), ADR-0035, ADR-0016, ADR-0049 (stop as withdrawal, not the pause it removed) | Sixteen operation rows, plus verdict parity over the grown catalogue |
| 012 | The conversational portal | ADR-0034 (**built**), ADR-0051 (new — a turn is evidence, a thread is a view), ADR-0033 (the portal is a consumer, so parity still binds one pair), ADR-0032 (the ungoverned loop, made structurally impossible), ADR-0049 (no pause, asserted as an absence) | Eight containment rows, eight accessibility rows, and the API's first deployment |
| 013 | Capability packs and eval gates | ADR-0004, ADR-0022, ADR-0030, ADR-0031, ADR-0039, ADR-0045 (**built** — the toolset line 008–012 signposted, replaced by product knowledge a definition opts into), ADR-0018 (consumed) | Four of five eval gates blocking against both shipped packs; the fifth (report fidelity) an explicit skip citing ADR-0018, per ADR-0047 |
| 014 | Dispatched resume | ADR-0026 (**the durable half built** — `resume_run` gets its first `src/` caller), ADR-0048 (a resume is a new allocation with a new attested identity), ADR-0049 (grant expiry stops terminally), ADR-0047 (FR-020 re-scoping — 005's rows now asserted through a dispatch) | Ten dispatch-level rows in the durability lane. **Closed ROADMAP gap 0a**, and uncovered four latent defects — the missing grant store, an index with no writer, a sweeper that had never dispatched since 009, an observer that could not be called |
| 015 | Audit egress for tamper-evidence | ADR-0055 (**built** — the rule was settled and nothing existed), ADR-0020 (unchanged — this adds a NEAR destination, not a far one), ADR-0035 (reconciliation runs through the governed read path and is itself audited) | Thirteen rows against a live second store under the collector administrator's credential. **Closed ROADMAP gap 0**, the most consequential gap on this page. Found a reconciler that compared the two copies' hash *claims* rather than their contents — an administrator who rewrote a payload and left `entry_hash` alone passed the comparison |
| — | Federated sign-in and the surface that serves it | ADR-0033 (the API's first *working* deployment), ADR-0016 (claim mappings become readable, so the gate has an effect), ADR-0048 (the API gets its own attested identity), ADR-0057 (the phrasing it left owed, amended) | No new gate class. Three component suites and one conformance row on the real Vault path, plus a unit gate over the API assembly. **Not a numbered feature** — direct work off 016's parking, PRs #76–#80, recorded here because the ROADMAP's own rule is that deferrals and landings are written down where the next planner will see them |
| 018 | Registry isolation | ADR-0025 (**the row it was owed** — a registry the run cannot reach), ADR-0047 (amended the same day: *deferred by decision* is not *not yet applicable*) | **Closed the registry-isolation gate row**, which the constitution had named while no ADR deferred it and no feature claimed it. A run is *observed* being refused when it writes what bounds it, rather than the isolation being argued from structure |
| 019 | The MCP surface gets a server | ADR-0033 (the transport that had a catalogue and no process), ADR-0049 (the resume sweeper and dependency health get a long-lived home) | **Found a defect four features old.** Until this, MCP existed as an operation catalogue nothing served — the shape ROADMAP gap 0d names, caught by giving it a process |
| 020 | A model chooses, and the choice is governed — **the model chose WHICH tool; the platform supplied every tool's arguments from a fixture constant until 040** | ADR-0022/ADR-0039 (**the Qualified Model Matrix binding path exercised for real** — 013 built the reader and the validation, and nothing had ever written a cell), ADR-0052 (the judge chain) | **Closed ROADMAP gap 0e**, the largest instance of a capability correct, tested, and wired to nothing. A model now names each step's tool and the choice passes the same governed entry a scripted one would — refused when it must be, recorded either way, durable across a kill |
| 021 | Grounded run reports | ADR-0018 (**built**, four months after it was Accepted), ADR-0035 (a report is a governed, audited evidence read), ADR-0032 (attestation states its scope), ADR-0033 (the parity row grows by one operation), ADR-0055 (a report says whether its own basis verified) | **The last owed row: report fidelity.** `OWED` is empty for the first time since the constitution named five eval suites. Its Constitution Check **failed** on Principle IV — read-back at report time would have run under the API surface's identity — and the redesign put observation in the allocation, where an identity bounded by the run already exists. Four analysis passes, 11 → 6 → 6 → 3 findings; the fourth found `research.md` still describing the rejected architecture, which three passes over spec/plan/tasks could not see |
| 017 | Deployment lane | ADR-0047 (**the inverse case it governs** — gates that PASSED while the guarantee was absent, because they asserted about the wrong object), ADR-0048 (a surface's identity is attested, and an assembly asking for the wrong role fails at login), ADR-0033, ADR-0025 | Twenty-one rows against the served surfaces, in a lane that stands them up. **Closed ROADMAP gap 0d.** A gate class no prior lane could run: every other asserts about a process the test constructs, this about the one a deployment constructs. Eight analysis passes before implementation, six of which found something in the surfaces' lifecycle; running it then found two more |
| 022 | The trail records who looked | ADR-0035 (**amended** — the governed-read discipline extends past the audit plane to records about runs and threads), ADR-0009 (a read is now a step in the walk that carries an entry), ADR-0033 (parity held at zero coverage; it now holds at seven), ADR-0018 (the asymmetry that made this urgent) | **Found by connecting an editor and asking the platform what it had just done.** The answer came back; the question left no trace. Nine of seventeen operations wrote nothing while both surfaces claimed every operation was recorded. Ten analysis passes, 8 → 4 → 2 → 1 → 1 → 1 → 0 → **1 CRITICAL** → 3 → 2: the zero at pass 7 was misleading, and switching from comparing artifacts to each other to comparing them **against the code** immediately found that `stop_run` recorded nothing — which this spec had asserted was covered, marked *measured*, without measuring it |
| 023 | A browser login for the dev lane | ADR-0033 (unchanged — the surface's OAuth half already worked), ADR-0016/0057 (a browser login resolves to the same claims a minted token does) | **Five defects, all found by connecting a real editor and none by any check.** A 404 on the discovery path clients probe; a document missing `response_types_supported`, which a client validates and refuses; a single-threaded `HTTPServer` that a browser's keep-alive blocks; default claims the deployed surface does not map; and `resource` — required by MCP — being swallowed as an identity claim, which defeated the default and refused every login after it appeared to succeed. That last one survived four rounds because the test kept being written without `resource`, a shape no real client uses. Nineteen served-surface rows were green throughout |
| 024 | Grounded guidance — a question gets an answer | ADR-0039 (**built** — *ask answers, it never acts*, decided before the feature existed and satisfied structurally: the path holds no tool registry and no authority grant), ADR-0034 (answering is an API operation, so the portal stays thin), ADR-0033 (the parity row grows), ADR-0022/0039 (the `ask` binding), ADR-0004 (the corpus is the supply chain's second subject) | **Four eval suites for answering were in force and green over a capability that did not exist.** They scored `recorded` strings described as *"what a previously-observed run produced"* — for runs that had never happened, because neither scorer touched a product path: `FixtureScorer` replays, `LiveModelScorer` asks a vendor directly. `AnsweringScorer` drives the real path with the recording as the model's output, so the suites score what the product produced. Reauthoring the cases exposed the finding underneath: they cited `developer.hashicorp.com` product docs while the pinned corpus is `/validated-patterns/` — **disjoint sets, so every case cited a document the platform does not have**. **Two deferrals, both recorded rather than dropped**: estate-state answering, and the portal's own answering surface — the feature is named for a surface it does not touch, and analysis pass 3 found SC-001 reading "through the portal" while no task did. **A third deferral, raised during implementation and recorded rather than absorbed**: the pin has no refresh schedule and no staleness signal. `corpus_sync` re-discovers the document list upstream on every run, so a NEW pattern page is picked up without editing a list — but nothing runs it, and an answer cannot say its pin is forty days old. The intent is latest-available content; pinning serves that rather than fighting it (sync often, answer from the newest sync, and the citation still provably resolves), but the scheduling half does not exist. FR-014 says pinned and says nothing about how often, which is the gap. Same for `packs/*/skills`, vendored from hashicorp/agent-skills by hand. Four analysis passes, 3 → 2 → 1 → 3; the uptick is honest, since passes 2 and 3 changed the feature's shape |
| 025 | Estate-state answering — the answer is bounded by who is asking | ADR-0035 (**executed** — its central sentence, *"everyone asks in the same place, and the answer is bounded by the asker's own entitlements"*, decided 2026-07-01 and implemented by nothing until now), ADR-0039 (never-acts, inherited structurally from 024), ADR-0018 (evidence with citations, never verdicts), ADR-0034/0033 (an API operation, so parity grows — by **zero operations**, since asking stays one place) | **The last prompt-scoring suite stopped scoring authored recordings.** `estate_state` now drives the product path and is scored by precision and recall over surviving references; the `match` substring it used could not fail an answer that reproduced the record AND invented a workspace. **FR-012 named the 2026-08-01 live failure before replacing the suite that failed**: `vault-estate-state-004`, and the cause was the grounding — the lane built its 'estate' from five unlabelled sentences and the model correctly refused to guess which one answered the question. **A fail-closed inversion was found in merged code**: both `EvidenceQuery` implementations tested `event_types` for truthiness, so an empty scope meant *no filter* rather than *nothing* — a subject with no roles would have seen the entire tenant's trail. Observable by nobody, since no caller had ever set the field since 008. **Owed and deferred, recorded rather than dropped**: ADR-0035's team granularity (needs a subject attribute the platform lacks — not approximated by role scope, which is a different thing with a similar shape), the portal's answering surface, and corpus refresh scheduling. Four analysis passes, 8 → 4 → residue → 3 |
| 026 | Asking binds to the Qualified Model Matrix | ADR-0022/0039 (**consumed** — `ask` was already in the closed role vocabulary and `resolve_with_fallback` already had the no-third-branch property; this feature adds no resolver and no ADR amendment), ADR-0033 (both surfaces refuse identically, through one shared function), ADR-0047 (the rule US3 enforces on 024's contract) | **A merged contract asserted a refusal that nothing performed.** 024's conformance contract said *"an unqualified cell refuses before any provider call"*, backed by FR-009 and SC-006; measured against `main`, no module on the answering path referenced the matrix and the matrix record held no `ask` cell for any pack. Principle VIII is a MUST, so this was a constitutional gap in shipped code — **found by checking a claim rather than by a failure**, which is the only reason it surfaced at all. The binding is an operator-authored trust-fabric record naming a cell per source; deployment config was rejected because *where* a model is reachable from is assembly while *which* model is permitted is governance. **Governance now precedes availability**: an unconfigured surface refuses `unbound`, not `provider_unavailable`, because "nobody decided" is what an operator needs before "nothing is wired". Two spec-invented names turned out to exist already (`fabric_unreachable`); only `unbound_ask_source` was new. **Owed and deferred**: real served answering (the served surface holds no vendor credential and wiring one is an undecided posture — the served check proves resolution by disposition progression instead), portal answering, corpus freshness, team-granularity scope. Three analysis passes, 5 → 0 → 3 |
| 027 | How the platform holds a model credential | ADR-0058 (**new** — brokered per task, on the first exception's pattern), constitution **v1.4.0** (Principle IV: one named exception → two; *static API keys are prohibited without exception* → *prohibited as workload credentials*, bounded by store, identity, delivery and non-persistence), ADR-0044 (**the rule that already decided it** — federate where the product validates external identity, broker where it cannot; a model vendor validates none), ADR-0022/0039 (consumed, not revisited — the matrix governs WHICH model, this governs how the credential to call it is obtained), ADR-0033 (both surfaces broker through one shared function) | **Three features built an answering capability no person could use.** 024 built it, 025 extended it, 026 governed it — and every ask through the served surface refused before reaching a model, because a vendor key in a service would have been a second standing credential and Principle IV named exactly one. Each feature recorded the deferral rather than resolving it, which is correct for a feature and wrong for a platform: the deferral was becoming permanent by accumulation. **The doctrine had already decided it** — ADR-0044's federate-or-broker rule routes a vendor with no workload-identity validation to the broker branch; only the constitution's wording had not caught up, and it is amended in the open rather than read around. **Two measurements reshaped the design**: `BrokeredMaterialSource` has no production implementation, so this is the platform's FIRST broker and its shape becomes the precedent the TFE path inherits; and a vendor key is not derivable — there is no credential API to mint lesser material from — so the posture is *never persisted*, not *short-lived derived material*, and the record says so rather than overpromising. **Two corrections found while building**: the planned two-method reader would have let a rotation land between the fetch and the version read, recording a generation the call did not use (one read now yields both); and `LiveEstateProvider` with no id mapping offered every record as `id: ?` and resolved every citation to `unresolvable:?`, so a deployed estate answer would have dropped every claim and read as *the records do not support an answer*. **Two gates amended in the open, at the same grain as the constitution**: `test_no_static_credentials.py` gets exactly one named module exemption (the rejected alternative — renaming the KV field so the matcher would not see it — would have left the gate green while the credential existed), and the conformance-lane marker check now parses decorators after matching `mark.enclave` **in a docstring** — the fourth check in this repository to match prose instead of code. **Owed and deferred**: per-tenant model scope (new here), portal answering, corpus freshness, ADR-0035's team granularity |
| 028 | The portal learns to ask | ADR-0034 (**the thin-client rule, tested where it was most likely to break** — the portal renders four response shapes and decides nothing), ADR-0039 (never-acts, inherited structurally), ADR-0035 / ADR-0018 (consumed) | **The deferral four features carried.** 024 built answering and recorded *"not through the portal, and that is a scope decision rather than an oversight"*; 025 extended it, 026 governed it, 027 made it work in a deployment and demonstrated it — reachable only by someone with an MCP client or a bearer token and a command line. **The finding that decided the design**: the refusal *codes* live in the trail, not the HTTP body; what the body carries is prose five features made precise. So the portal renders the API's words verbatim and classifies nothing — which is how FR-009 (three refusals distinguishable) and FR-014 (the API unchanged) hold at once, and is the ADR-0034-correct shape, since a portal-authored cause mapping would drift the first time a reason code moved. A row pins it. **Two decisions taken rather than defaulted**: per-operation patience (the ask waits 180s, every other call keeps the 10s that exists because a hanging page teaches people to reload — both halves asserted); and its own page rather than a turn in a thread, because a thread is where turns act and one surface holding both would make never-acts a property of which button was pressed. Streaming was rejected on **correctness**, not cost: citations resolve against the pin after the model finishes, so streamed text would show claims the pin may yet reject. **Two gates caught what reading did not**: the containment session's *every page and every action* claim would have excluded the newest page (analysis), and the new nav links failed WCAG 2.2's 24px minimum target at their 18px text height (the browser lane, first run). **No sealed core, no amendment — the first feature in five with no Principle V review.** **Owed and deferred**: submit-then-poll (needs the API to hold an in-flight ask, recorded as the next shape rather than dismissed), corpus refresh, team granularity, per-tenant model scope |
| 029 | Estate answering at real volume | ADR-0035 / ADR-0018 / ADR-0039 (**consumed, none amended** — the read's *bound* changes, not its governance) | **Three defects found by the first person to use the portal 028 shipped**, all merged since 025 and green the whole time, all invisible at test volume: 025's rows exercise tens of records and the deployed tenant holds 236,581. **(1)** The router knew the trail's verbs and not its nouns — 4 of 12 estate-shaped questions declined without reading a record, a false negative wearing an honest decline's page. **(2)** The read bounded by row count over undifferentiated types, so *"What ran today?"* was answered from 1,000 of 63,947 entries containing 60 run records under 940 pieces of step machinery — **the defect is competition, not size**, and raising the limit would not have helped at any value. **(3)** A truncated read returned the *oldest* window, three days stale; nothing caught it because both implementations were wrong identically, and agreement is evidence only when the implementations could have disagreed. **Two rules emerged from building it.** The singular/plural discriminator (how-to questions name things in the singular, what-happened questions in the plural) belongs to **routing and not focus** — focus is consulted after routing has already chosen the estate, so it carries none of routing's risk. And `ESTATE_TERMS` split from `ESTATE_NOUNS` when an **existing row** caught *"the recommended pattern for dynamic secrets"* — documentation using a plural — proving the plural rule alone insufficient. **The window note lands on the answer, never on `ASK_ANSWERED`**: the trail's access record serves the investigator, the note serves the asker about to act on *"3 runs failed"* without knowing whether that is 3 of 3. No sealed core, no Principle V review — **third feature running**. **Owed and deferred**: whether `operator` should see authority records, and whether 025's `estate_state` eval suite scores a question no operator can ask |
| 030 | The estate eval scores the real path | **ADR-0059 (new)** — a cell's estate evidence spans the asker roles its cases declare; qualification requires every declared role's subset to pass; matrix schema untouched. ADR-0022/0039/0035/0018 consumed | **024's finding, one layer in.** The estate scorer handed the answering function the fixture's records whole — role scoping never narrowed, the governed read never ran, windows never resolved, 029's bound never applied — and six of ten estate cases across two packs expect authority records no `operator` can see. That evidence qualified the platform's first two live cells. **The tag follows the expected set, not the prompt — measured, twice**: vault-002 and terraform-004 both read operator-shaped while expecting an `authority_denied` reference, and the second was caught by the analysis pass after the plan skimmed it. **The naive mutation check is recorded as vacuous** (tagged cases pass with and without narrowing); the rows with teeth observe the provider's input and the load-time refusal, and deleting the narrowing fails exactly one row. Cases now declare `asker_role` from the platform's own vocabulary, never defaulted; a case expecting the invisible refuses loudly. **Owed**: the live re-run deciding the two cells (named runner), and 029's operator-visibility question, still open |
| 034 | The portal gets a visual identity | ADR-0034 (the portal stays thin — this is presentation, and the one payload field it adds is display-only), ADR-0039 (the never-acts distinction stays *visible*, which is partly a design job), ADR-0004 (**applied to a font** — adopted content is adopted content) | **The portal had no character and, worse, no way to tell an argument from an identifier.** Three type roles now do what one face could not: serif headings, Roboto prose, monospace for anything a person carries to an auditor — a record hash stops needing to be explained as "the technical bit" because it already looks like one. Saturated colour is scarce and always means something: a product or a verdict. Verdicts became pills carrying a border and the word, so meaning survives greyscale. **The a11y lane doubled** — every axe state and every keyboard criterion, in both themes, 53 rows — because a dark theme nothing exercised would be the untested surface this repository refuses. **That doubling immediately found the platform being right about something**: RATE_LIMIT_ACTS is 30 per five minutes per SUBJECT, so running every row twice as one person blew the budget and the rows failed far from the cause — a composer that never rendered reads as a missing label, not a refused act. Fixed by giving each theme its own subject; widening a real control for a lane's convenience was the alternative and was refused. **Two planning assumptions died at the licence file**: Roboto is SIL OFL 1.1 and not Apache-2.0 (stale rather than invented — it was Apache for years), and upstream ships no static weights at all, so one variable woff2 carries every weight at 222 KB against an estimated 90. Both were caught by reading the artifact instead of trusting the plan, which is the second time in one day a confidently-stated upstream fact turned out to be assumption. Two analysis passes, 4 → 0 |
| 033 | The corpus refresh | ADR-0004 (**consumed twice over** — the corpus as the supply chain's second subject, and the `[upstream]` pin as provenance that is *checkable rather than asserted*, which turned out to already be the record this feature needed), ADR-0039/0034/0033 (the note reaches all three surfaces through the shared payload; no operation added) | **024's deferral, closed: the pin now says when it was made, and every guidance answer says how old its ground is.** The manifest carried no timestamp of any kind, so no layer above it could compute an age even if it wanted to — answers made a currency claim nothing was checking. `synced_at` moves on every sync including one that finds nothing changed, and that one-line diff IS the 'we checked' record the weekly proposal exists to produce. Six ways of not knowing (absent, empty, unparseable, wrong type, naive, future-from-skew) map to ONE state, disclosed as unknown rather than raising — the failure being guarded is an answer claiming currency it has not earned, so returning None fails toward more disclosure while refusing to load would take answering down over metadata. **The note never suppresses itself and never declines**: a disclosure that appeared only past a threshold would train readers that silence means recent, and declining would punish the asker for an operator's omission. **Three analysis passes, converging** (3 → 5 → 3, all resolved): pass 1 caught the artifacts inventing a `[skills.provenance]` table while the loader's `[upstream]` pin already existed and the invented name would have collided with `[[skills]]`; pass 2 caught the CI half's operational reality — a token-created PR triggers no checks, and the obvious fix (a PAT) is the standing credential Principle IV exists to refuse, so the proposal explains its own missing checks instead; pass 3 caught the dated-branch pile and the unassertable 'no network step'. **Run against real upstream during implementation**: hashicorp/agent-skills HAS moved since the 2026-07-29 vendoring, reported with a compare link and not one byte vendored — adoption stays a reviewed act through the promotion path |
| 031 | A real model drives a governed run | ADR-0058 (**closed its owed half** — the first dispatched run with a non-fixture model brokered the vendor credential under the allocation's own attested identity, 027 T016b observed live), ADR-0059 (**applied to its first new cell** — plan-role evidence earned by scoring the tool-choice pair under a `plan` subject), ADR-0049 (terminal stops honoured, observed), ADR-0048/0022/0039 consumed | **The founding promise, executed: `TOOL_CHOSEN` naming `anthropic/claude-opus@5` on a dispatched allocation, from a live plan cell that exists for the demonstration and never for the gates** (seeded out of band by `infra/bin/model-run-demo`, trap-restored, restoration proven byte-for-byte, choice lane green before and after; the merge-lane row untouched). Operator visibility decided: `AUTHORITY_DENIED`/`AUTHORITY_REFUSED` and only those — and the loop closed over the wire, an operator token asking *"Which runs were denied?"* and the answer citing the demonstration's own refusal record. **Six executions to one clean run, each failure a real property**: an over-scoped run cannot start (manufacture refuses before any model exists); **an aligned model does not over-reach** — three samples, two wordings, NONE every time, so the over-reach scenario as spec'd is undemonstrable without adversarial injection and Run 2 became the user's design (one permitted tool, always refused — the model behaves perfectly and governance still says no); a machine credential is refused where a person's is expected (`subject_kind_mismatch`, the API's own defense); and 24 MHz of enclave cannot place dispatches under three surfaces. One live-lane variance row (terraform/must_decline case 001) recorded as it happened and re-run green the same day. **Owed onward — discharged by 032, four days later** (this row read as open until 2026-08-07): the estate switches to Sonnet 5 for future lane runs — a governed re-qualification, not a config edit |
| 032 | The live lane and the estate switch to Sonnet 5 — **the harness earned it, not the thresholds** | ADR-0049 (the deny/decline boundary, **stated rather than assumed**), ADR-0052/ADR-0059 (the cells are earned on evidence, and the Opus cells are retained because evidence does not expire when a cheaper subject arrives), ADR-0022/0039 (the ask binding repoints; the matrix schema is untouched) | **No gate row moved, and that is the claim.** A second vendor model is the reason: customers will bring models this harness has never met, so **the harness carries the burden of platform vocabulary** — not the gate, and not per-model branches. Measured before: Sonnet 5 refused every `must_deny` case *correctly* and said "I can't" — semantically right, invisible to the platform's vocabulary, and twice drifting across the deny/decline line entirely. Measured after: with the verdict word required as the response's opening token, 10/10 deny samples open `Denied:`, **and the threshold did not move**. **Three further measurements, each a real property.** The same scorer serves subject and judge, so the judge inherited *"your response MUST begin with 'Denied:'"* and a judge whose whole output is a verdict word qualified above 90% before that instruction and **at 55% under it** — the prompt now branches on the subject's role. The last failing case was a *classification*, not a phrasing: asked to hardcode AWS credentials in `main.tf`, Sonnet opened `Declining:` three samples in four, reading credential handling as another product's concern — a defensible reading of a rule the prompt had left underspecified, fixed by one model-agnostic clause stating that **the request's subject decides** (1/4 → 4/4). And the anti-over-citing rule, written against Opus's failure mode, was obeyed harder than intended: Sonnet read the *same run's* resumption as "nearby" and recall failed two samples in three, so the instruction gained its symmetric half — *"nearby" means outside the subject, never inside it* (→ 3/3, all twelve estate cases green on fresh samples) |
| 035 | The ask becomes a conversation | ADR-0034 (**the thin-client rule under the hardest case yet** — a transcript the client appends to, where every word in it is still the server's), ADR-0039 (never-acts, held while the surface gained memory), ADR-0033 (three ask-conversation operations, on both surfaces) | **The spec deferred follow-up context and the maintainer put it back mid-specification**, which changes what the model is shown and therefore what a citation rests on — so the record had to carry it: `ask_answered` gains `conversation_id` and `carried_context`. Clarify settled the two questions that decides: an explicit routing signal always wins and only a signal-less follow-up inherits its predecessor's source, and a declined exchange carries its QUESTION forward but never its decline, because feeding a decline back invites a second one by agreement rather than by reading. **The plan was wrong about retrieval and SC-002 measured it**: 6/10 until the earlier questions widened the retrieval query, then 9/10. **Three pieces of 028's single-answer styling were correct then and defects once answers stacked** — a card around the response, a rule under each claim, and a button margin that read as a centring error. **A class name is a namespace whether or not anybody treats it as one**: naming the ask container `.composer` put ask styling on the thread page, caught by the 320px reflow rows on a page the change never meant to touch. Follow-on: #158 aligned the run surface on the same design principles and found a live 2.5.8 failure two a11y rows had never measured, because both walked one page; #159 withdrew the CLI |
| 036 | Deferred disclosure and code mode — **code mode later DECIDED AGAINST, [ADR-0065](docs/adr/0065-code-mode-is-decided-against.md), 2026-08-06** (the runtime is upstream pre-release with no timeline, and the capability was being conflated with the platform *writing code*, which is 038's subject; deferred disclosure is unaffected and stands) | ADR-0040 (**built**, and its "no audit change" clause amended by **ADR-0061 (new)** — a search is recorded, never refused), ADR-0041 (**the gate satisfied**: per-call hook parity demonstrated, not argued — the record itself is now **Superseded by ADR-0065**, which does not unmake the demonstration), ADR-0054 (**left Proposed** — the per-delegation boundary has no substrate and governing it would be a rule nothing exercises), ADR-0047, ADR-0026, ADR-0004 (a runtime adopted by identity) | **The owed parity gate row, owed since 2026-07, now asserts ADR-0040's own sentence.** **Three measurements killed three obvious designs**: the framework AUTO-INJECTS ToolSearch (so building the search layer by hand double-wraps and dies on its own reserved name); capability wrappers nest by list order so `position='outermost'` put governance OUTSIDE search and sent every search into `invoke_tool`; and ToolSearch implements no `wrap_tool_execute`, which is the fact that makes `wrapped_by` safe — the middleware chain is untouched, so Principle III still holds. The search exemption is POSITIONAL, never a name match: a genuinely registered tool called `search_tools` is governed like any other. **The sandbox does not enforce its own function table — the host does**, so `open`, `eval`, `__import__` and invented names all arrive shaped like tool calls and refuse via the registry, with no blocklist to forget to update. **C5 is the load-bearing row**: a rigged seam that skips `invoke_tool` must make the parity assertion FAIL, because a suite that cannot lose proves nothing. **Three defects found by building rather than reading**: `value_of` read a `result` binding out of a namespace attribute that does not exist (every program returned None); the credential-free-checkpoint scanner inspects TOP-LEVEL KEYS ONLY, so the ledger's natural nested shape hid every credential one level down; and my own discovery row searched audit payloads for a tool name the trail never carries — it asserted nothing and passed. **Two repo gates rejected the first implementation and both were right**: the adapter was writing audit directly (moved to `core/disclosure.py`) and had grown a fifth behavioural module (folded into `governance.py`). **SC-002a's threshold moved 25% → 35% in the contract, carrying its measurement** (937 vs 2832 bytes over 24 tools = 33.1%): the harness's tools are schema-poor so the catalog line dominates, and binding to the pessimistic case catches a regression without claiming a saving the corpus does not show |
| 037 | The intake gauntlet | ADR-0053 (**Proposed → Accepted**, amended on acceptance: the range is purpose-built, the analyzer's floor is its own, the manual path survives with a record — plus the named trigger Principle VI requires for an operated component), **ADR-0038 (the hardened untrusted-content tier it named in 2026-07 and nothing had built)**, ADR-0052 (mechanism inherited, floor not), ADR-0043, ADR-0021, ADR-0004 | **Three analyze passes, three clusters, one pattern — the gap between what a row ASSERTS and what a task BUILDS.** Pass 1 found a CRITICAL: the task list built a narrow *ceiling* where FR-006 required a *tier*. A ceiling bounds what a definition may CALL; a tier bounds what the process can REACH — so US2 would have passed every containment row while ADR-0038's premise went unimplemented, with the plan's own Constitution Check citing the tier as built. Pass 2 found nothing opened the proposal US1 exists to produce, and that the package shape contradicted the MVP, which produces none of its verdict/comparison/canary fields. Pass 3 found the golden corpus had no floor and nothing authored the canary-exfiltrating candidate. **The finding that shaped the artifact**: FR-027's reassurance failure arrives through the SHAPE of the evidence package, not its wording — an omitted section and one reading "not run" are identical to a grep and opposite to a reader, so a package with no verdict now says so *where a verdict would appear*, and a fully-run package still names ADR-0053's residual. **The seed floor gained a clause ADR-0052 did not need**: benign cases, without which the false-positive budget has nothing to measure against and a corpus of purely hostile content qualifies an analyzer that flags everything — passing every must-flag check and useless. Two rows exist to prove the others can lose: Q4 (a weakened analyzer must FAIL) and D5 (no candidate-authored content reaches the observer, refused at the seam by type). `OWED` stayed empty: the analyzer's suite landed with the analyzer |
| 038 | The agent authors, and a person merges | **ADR-0038 realized** (the family it named in 2026-07 and nothing had built; its pack-tool-target clause **amended by ADR-0064**), **ADR-0062** (Principle IV's THIRD standing-credential exception — constitution 1.5.0 → 1.6.0), **ADR-0063** (a mechanical scorer may qualify a cell, amending ADR-0052), ADR-0037, ADR-0022/0039, ADR-0047 | **Eight analyze passes: 4, 2, 2, 2, 3, 2, 1, 1 CRITICALs — and after pass two, most findings were defects in the REMEDIATIONS rather than in the plan.** The sharpest: the two-tree design makes the file SET unforgeable, and that was written up as containment being "not expressible" — true of paths, **false of bytes**, since an authored file is agent-controlled content and nothing scanned it for two drafts. A guarantee airtight over a narrow subject is the easiest kind to over-generalise: the confidence transfers and the reasoning does not. **Nothing was going to run in the hook pipeline** — two refusals sat in modules a caller must remember to call, which reads identically to enforcement in a task list; fixing it surfaced the need for a governed `read_subject` path that FR-014, FR-005b and FR-004 were all written against and none of them had. **The handoff went through four wrong forms** (no transfer → lease-fenced → revival-burning → no entry mode) before landing on checkpoint + `RUN_CONTINUE`, which re-authenticates because `resume_run` was the only place authority was re-manufactured. **The `github` pack could not be gated** — the eval suites are answering-shaped and a pack with one PR-opening tool has no expertise to measure, so publishing became a platform tool and ADR-0038 was amended rather than departed from. Implementation added three more the repo's own guards caught: product knowledge in `core` (`terraform_apply` hardcoded in a hook), an undeclared fake-fabric row, and two vacuous assertions mypy called out. And Q1 found a **pre-existing defect**: `resolve_with_fallback`'s pinned branch never checked the role its docstring promised, so a `plan` cell resolved for `write`. `OWED` stayed empty; the `write` corpus landed with the capability |
| 041 | Authoring becomes reachable | **ADR-0066 (new)** — version control is reached through adopted CLIs (`git`, `gh`), not an MCP server; the Principle II registry-review determination recorded **with its reversal**, since MCP was chosen first and rejected on measurement. **ADR-0038/0064 realized** (the tier 038 built and nothing could reach), **ADR-0062** (its credential path implemented — `token_for` had raised `NotImplementedError` since 038), **ADR-0063** (the mechanical write-cell gate, run at last), ADR-0026/0049 (the checkpoint-and-continue handoff), ADR-0047 | **The gap was five layers, and only the first was known.** Registration had zero callers anywhere; the derived vocabulary refused a correct ceiling `unknown_ceiling_entry`; the dispatch entrypoint never read the `HARNESS_AUTHORING_ROLE` the jobspec had set since 038; **both tier tasks declared `/bin/sh -c` and no command**, so each started a shell and exited successfully; and the App-key exchange raised. 038's rows were green through all five because they construct the handlers directly and synthesize the ceiling. **A real proposal was opened, verified and closed** by the E-rows against a live forge — published bytes hashing to the artefact's own digest. **Four findings the rows produced rather than the plan**: the refusal discriminator was planned for the authority hook and belongs at the pipeline's scope gate, because the hook only fires when policy narrows *after* issuance; a run may not request more than its ceiling, so two of FR-019's three layers cannot both be per-call denials; the jobspec guard found **two more instances of the same defect in 037's tiers** (recorded in `KNOWN_UNEXECUTABLE`, not silently fixed); and FR-030's guard found `plan` and `apply` carrying the same wait-forever suspension shape. **Three guards were extended rather than worked around** — `WRITE_CALLS` gained `rmtree`, the fake-fabric scanner stopped crashing on any `global` statement, and `core/authoring/credential.py` stopped naming the substrate. **Owed**: a live `write` cell, which needs a property detector that does not exist — the `properties_of` callable is caller-supplied and its only implementations are literal maps in rows, so building one hastily would be the un-loseable gate this repository refuses |
| 040 | A model says what to do, not only what to use | **ADR-0026** (the intent/result bracket — an intent must now carry enough to *repeat* the act it precedes), **ADR-0051** (the tool-argument redaction rule, **broken exactly once and no further** — a model's own words rest durably in the control plane for the first time, and still never reach the trail), **ADR-0065** (why this is its own feature: it was planned as a consequence of code mode, which was decided against, and the finding was independent of it), ADR-0022/0039 (consumed — *which* model may answer is unchanged; only the shape of the answer moves), ADR-0047 (a passing stub is worse than a missing one, and this feature had an unusually available one) | **020 put a model in the loop for *which* capability runs and left *what it runs with* to a constant.** `_PROBE_ARGUMENTS` was passed as the arguments for every tool a model named, so a model could choose `vault_write` and could not say what to write — a platform whose model picks the verb and never the object automates almost nothing. Eighteen rows (M1–M18), hermetic and merge-blocking except **M18, which is enclave-marked and fails rather than skips**. `OWED` stayed empty. **The enclave then failed three things the green hermetic lane could not see**: a bare-name recording stopped meaning what it meant once the platform no longer supplied `cas`, breaking five dispatched rows; M9's no-secret-leak assertion was **vacuous**, reading a payload key that does not exist behind an `if` that was never true; and M18 hardcoded its run id, reading events from every earlier attempt. **And the method that hid them for three rounds**: baselines taken with `git stash` stashed nothing, because the work was already committed — so they compared identical code and reported parity, **the same defect as a row that cannot fail**. The real baseline came from `git checkout main` and showed the five broken rows immediately. **The local lane had to be repaired before any of it could run**: Nomad read an M5 Pro's clock as 4 MHz rather than 4 GHz, advertising a **24 MHz** budget for an 18-core machine, so six ordinary allocations filled it exactly and the merge-blocking durability job was *unplaceable* — and had been for as long as anyone had run here. It went absent, not red. **T023 outlives the feature**: `tests/unit/capability_inventory.py` sweeps `src/core` for every capability the platform defines against every one a run can reach, so *built and unreachable* now **fails a merge** instead of being found by accident — the shape that shipped twice (036's `run_program`, 038's authoring trio). Its `DELIBERATELY_UNREACHABLE` entries each name the record that decided them, so a reader can tell *"nobody got to this"* from *"somebody decided this, here is why"*. **Owed and deferred, recorded rather than dropped**: argument-level policy (the platform carries the request through; each capability enforces its own rules as it does today), and a **retention policy for kept requests** — kept indefinitely today, which is why the feature leaves the request removable rather than load-bearing, so the successor is a decision and not a migration |
### How the shape got here

Three entries that sat under **Next** long after they shipped. The reasoning in them is still
the reasoning — why the API went first, why packs had to precede answering, what the parity
gate cost — so they are kept rather than deleted, and collapsed rather than left where they
read as work outstanding. Each summary says what actually closed it.

<details>
<summary>Northbound surfaces — closed by 008, 009, 012, and ADR-0060</summary>


**Planned as four, shipped as three.** ADR-0033 enumerated four transports and required every
one to yield the same verdict and equivalent audit events, with parity asserted *between*
them. Building them in one pass would have meant getting parity right across four things all
still moving, so each got its own feature and landed against a settled core. The fourth, a
CLI, was never started and is now withdrawn (ADR-0060) — the table below keeps its row so the
plan and the outcome can be read together.

**The API goes first**, because the others consume it rather than reimplementing the
authorization path. A transport that talks to the core directly is a second authorization
path wearing a different name — the argument that ruled out a standalone CLI before anything
else did.

| # | Transport | Notes |
| --- | --- | --- |
| 008 | **API** | ✅ Shipped. The surface the others consume. Carries the audit plane as a governed read path |
| 009 | **MCP** | ✅ Shipped. The persistent service coding IDEs talk to. Carries the dependency health checks and the resume sweeper decided in ADR-0049 — both needed a long-lived home, and this is it — plus the continuous evidence-stream verification 008 deferred here, and the second CI lane |
| — | ~~CLI~~ | **Withdrawn** (2026-08-05, ADR-0060) — see below. Tabled 2026-07-28, withdrawn when holding the place proved to cost more than the option was worth |
| 012 | **Portal** | ✅ Shipped. Threads, the client, and the API's first actual deployment — 008 built `create_app` and nothing had ever served it. **Answering is not here**: estate-state and grounded guidance need an eval-gated model binding, and follow capability packs |

**Gate row, no longer owed:** surface parity. It stayed owed through 008 because parity
cannot be asserted against a single surface. **009 amended the row and satisfied the amended
version** — it was worded "across all four transports", which two cannot satisfy, so it now
binds across every pair of implemented transports (constitution v1.2.0). That makes it bind
at each transport rather than only at the fourth, which is the difference between catching
divergence when it starts and catching it long after.

**The CLI is withdrawn (ADR-0060, 2026-08-05).** API, MCP, and the portal cover
substantially every persona: services and automation reach the API, editors reach MCP, and
people who do not live in an editor reach the portal (ADR-0034). A CLI would be a fourth
way to reach the same four operations, for an audience already served by two of them.

**It was tabled first, on 2026-07-28, and the difference matters.** Tabling superseded no ADR
and deleted nothing — the position was that ADR-0033 still described how a CLI would work,
device authorization grant and all, should a demand appear the other three could not meet.
What ended that position was not a demand appearing but the cost of holding the place: the
constitution went on asserting *"exactly four transports — MCP, API, CLI, portal"* as a
normative clause, and that is the document every `/speckit.analyze` pass measures a
specification against. A governing document naming a surface nobody built is the failure mode
ADR-0047 named in tests, one level up.

ADR-0060 supersedes ADR-0033's transport enumeration and its CLI device-grant clause, and
nothing else: one authorization core, parity as a conformance-asserted test, OIDC-always and
no static API keys all stand. **Three is a ceiling, not a floor** — a fourth transport still
requires an ADR, which is the gate the enumeration existed to hold.

**What this costs, stated because it is easy to miss:** people who live in a terminal reach
this platform through the API, which means writing a client or using `curl` rather than being
handed one. That is a real ergonomic loss, and it is why this was tabled rather than declined
the first time.

The parity gate is unaffected, and only because 009 got there first. It binds across every
pair of **implemented** transports — three implemented is three real pairs. Had it stayed
worded "across all four", tabling one would have left the row permanently unsatisfiable, and
that scheduling decision would have been a constitutional change wearing a scheduling
decision's clothes. Withdrawing the fourth now makes the gate describe the whole inventory
rather than most of it.

**Why here:** the first features that ship something a user touches directly. They need the
authorization core (002/003) and the approval gate (007) settled behind them; attempting them
earlier means building transports over guarantees still in motion.

</details>

<details>
<summary>Portal answering — closed by 024, 025, 026, 027, 028 (and 029, 033, 035 after)</summary>

**Shipped.** 024 built answering, 025 bounded it by the asker's entitlements, 026 bound it to
the Qualified Model Matrix, 027 gave it a credential it could actually use, and 028 put it on
the portal. 029 fixed it at real volume, 033 closed corpus freshness, 035 made it a
conversation. The dependency this entry named — packs before answering — held exactly as
written: 013 shipped the eval gates, and the `ask` binding was inexpressible until it did.


**Unnumbered, and after capability packs**, which is not a preference but a dependency:
ADR-0039 makes an `ask` binding inexpressible without a green Qualified Model Matrix cell,
and the eval gates that green a cell are that feature's. 012 split these out on exactly
that evidence — the platform installs zero model providers on purpose, so these would be
its first model call.

What it inherits, so it does not rediscover it: the corpus is settled (HashiCorp Validated
Patterns — 33 documents, stable per-section anchors, **no version metadata anywhere**, so
change detection must be content-based), and ADR-0039 has already decided the rule it will
be tempted to bend — *ask answers, it never acts*.

</details>

<details>
<summary>Capability packs and eval gates — closed by 013 (and the eval suites completed by 021, 029, 030)</summary>

**Shipped as 013**, which is why the Shipped table carries a row with this entry's exact ADR
list. Reading the two together was the drift: this text says *"the eval-gate machinery does not
exist"* and owes *"all Eval gates"*, and neither has been true for months. `src/core/evals/`
holds `promotion`, `judge`, `scoring`, `fidelity`, `estate_fixtures` and `injection_patterns`;
`src/core/packs/` holds the loader, manifest, isolation and workflows; the Qualified Model
Matrix is `src/core/choice/matrix.py`. `OWED` has been empty since 021 closed report fidelity —
the last of the five.


> Previously headed "009", which guessed a number this file's own rule says not to guess —
> and it was wrong the moment MCP was specified first. Unnumbered until its directory exists.

Packs, prompts, and skills as pinned, eval-gated artifacts; the Qualified Model Matrix; per-role
model bindings; competency tiers.

**Why here:** brings Principle VIII online, which no feature has needed yet — the eval-gate
machinery does not exist. It depends on nothing in 007/008 strictly, so it can move earlier if
content work becomes the priority; it sits here because a pack with no surface to invoke it and
no approval path is hard to evaluate end to end.

**Owed gate rows:** all Eval gates (must-deny safety, must-decline scope, citation accuracy,
estate-state fixtures, report fidelity).

</details>

## In progress

*Nothing in progress.*

<details>
<summary>021 grounded run reports — shipped 2026-08-01</summary>

**The last owed Quality Gate row.** ADR-0018 has been Accepted since 2026-04-08 and implemented
by nothing: `RunReport` appears nowhere in `src/`, and `core/evals/suites.py` carries report
fidelity in an `OWED` dictionary whose value says a gate over it "would assert something about a
thing that is not there".

020 is what makes it worth doing now rather than earlier. Before it, a report would have
described a scripted sequence — every tool the same, chosen by nobody, refused never. The first
run whose account is genuinely uncertain is the first run a report can get *wrong* in the way
ADR-0018 is about.

Three clarifications settled it, and the third was a correction: a report is scoped **as an
evidence read is** — by tenant, not to the run's subject — because many personas read these, and
because `EvidenceQueryRequest` carries no subject field at all. That measurement found a leak
worth naming here: `get_run_result` *is* subject-restricted, so a report carrying the run's result
payload would route around it. Forbidden by FR-008a before a line was written.

**Known consequence for the parity row**: a requestable report is an operation, so ADR-0033's
surface-parity row grows across API and MCP. Inherited work, not a discovery.

</details>

**016 task-scoped authority is PARKED** (`specs/016-task-scoped-authority`, tag
`archive/016-task-scoped-authority`, 19 of 51 tasks built). Specified, planned, and the
substrate built and demonstrated end to end — then stopped, because implementation established
that the narrowing it delivers is one the workload does not want.

These agents are HashiCorp experts who read widely before acting: skills, HVDs, internal
policy, prior art. Breadth of read is how the output gets informed, and an agent denied
context does not fail loudly — it advises badly. Meanwhile the property the narrowing was
meant to buy is already held: authority is manufactured per allocation from an attested
identity and expires in an hour.

[ADR-0057](docs/adr/0057-context-hungry-agents-want-breadth-not-narrower-reads.md) records the
decision and the three triggers for re-opening it. The research — Vault is the resource server
and cannot perform the exchange, the entity-alias binding, the `jti` trap — is kept in
`specs/016-task-scoped-authority/research.md`, alongside the spec and a README that says what
was pruned. The rest of that feature's planning artifacts were removed on 2026-08-03: a
fifty-one-item task list for work that was answered reads as fifty-one dropped obligations,
which is the opposite of what happened.

**039 code-mode reachability is SUPERSEDED, and was never built** (`specs/039-code-mode-reachability`,
planning merged as #168 on 2026-08-05, superseded the next day by
[ADR-0065](docs/adr/0065-code-mode-is-decided-against.md)). Code mode changes how a model
*invokes* tools — an efficiency optimization whose runtime is upstream pre-release with no
timeline — and it was being conflated with the platform **writing code**, which is 038's subject
and shares nothing with it beyond the word. Nothing has ever run a program outside a test.

**Its analysis outlived its subject, which is why the directory stays.** The structure it worked
out — three layers, registration as the opt-in switch, the ceiling deciding, and one enclave row
proving the thing works where dispatched work actually runs — applies unchanged to `author_file`,
`read_subject` and `open_proposal`, which were **also registered nowhere**. And its FR-014 was
independent of code mode entirely: one hardcoded constant supplied as the arguments for *every*
tool a model names. That finding became 040. What did not survive is what was reachable only
through a program — a looping program's lost intent record, and nested programs.

> **A feature has no number until `/speckit-specify` creates its directory.** Refer to unstarted
> work by name. Guessing the next number reads as a fact, propagates into merged documents, and
> is wrong the moment anything is specified out of order.
>
> **Numbers are identifiers, not sequence.** 005 was assigned to durable execution before the
> local environment was understood to precede it — and then 005 shipped first anyway, because
> the blocking part of the environment turned out to be one Makefile target. The order of work
> here does not match numeric order and is not meant to. Renaming a merged spec directory would
> churn every reference to it for no gain.

## Next

Ordered by dependency first, then by which owed gate row it closes. Each entry names what it
unblocks — that is the argument for its position, and the thing to challenge if you disagree.

**Three entries were removed from here on 2026-08-05 because they had shipped** — northbound
surfaces, portal answering, and capability packs. The last of them described the eval-gate
machinery as not existing and owed all five eval gates, months after 013 built it and 021
emptied `OWED`. They are kept under **Shipped → How the shape got here**, collapsed, because
the reasoning in them is still the reasoning; only the framing was wrong.

This is the same defect ADR-0060 closed in the constitution — a document asserting a shape the
platform does not have — in the file a planner reads *first*. It produced two wrong
recommendations in a single session before anyone checked it against `src/`.

**Integration and uplift left this section on 2026-08-05**, shipped as 038. The `write` role is no longer unbound — 026 bound `ask`, 031 bound `plan`, and the matrix's third role now carries a cell with a corpus behind it.

### Multi-tenancy (ADR-0046)

One platform, isolated tenants, using the products' own isolation primitives.

**Unnumbered, per this file's own rule** — it had been headed `011`, which 011 then went to. Guessing a number reads as a fact and is wrong the moment anything is specified out of order, which is exactly what happened.

**Why last of the scheduled set:** it multiplies every guarantee above it. Isolating tenants
before the things being isolated are stable means doing the work twice.

### The change-proposal workflow, end to end — Terraform first, Vault the same shape (unnumbered)

The product shape the current feature sequence builds toward, stated 2026-08-06 so the pieces
are aimed at it rather than discovered to almost compose later. **A user defines a workspace, a
Git repo, and the scope of their need. The agent reads what exists in Terraform and in context,
decides what should be built, runs `terraform plan` to prove the proposal is sound, and opens a
PR back to the declared repo with the recommended changes.**

Measured against merged main, most of the machinery exists and none of it composes yet:

| Step of the workflow | What exists | The gap |
| --- | --- | --- |
| user declares workspace / repo / scope | definitions, ceilings, dispatch; 038's `SubjectMount` and `target_repository` | no intake surface where a *user* declares these three; today they are operator-authored records |
| read what exists in Terraform | `terraform_plan` in `PLATFORM_HANDLERS` | **a fixture** — its own payload says so: *"Returns a shape, not a plan… Terraform is not deployed in the enclave"* |
| read what exists in context | pinned corpus; estate answering | the customer's own context is the entry below this one |
| decide what should be built | a model in the loop (020), and **040 — the model now states what to do with the tool it names** | **closed 2026-08-07.** What remains is argument-level policy, deferred by 040 on purpose: the platform carries the model's request through and each capability enforces its own rules |
| author the changes | 038's `author_file` / `read_subject`, containment, provenance, **registered and reachable by 041** | **closed 2026-08-07.** The trio moved out of `DELIBERATELY_UNREACHABLE` into a declared per-run record naming the registrar, kept honest by a row that drives the registering construction |
| PR back to the declared repo | `open_proposal` has its production handler — `git` push plus `gh pr create` ([ADR-0066](docs/adr/0066-version-control-is-reached-through-adopted-clis.md)) — and a proposal carries its provenance | **closed 2026-08-07**, proven against a real forge: 041's E-rows opened, verified and closed a real pull request. What a proposal does **not** yet carry is **plan evidence**, which is this workflow's own feature |
| `terraform plan`, twice — as **context** and as **gate** | the plan tool; the matrix already binds `plan` as its own role, distinct from `write` (038 narrowed exactly this: a `plan` cell no longer resolves for `write`) | plan is a fixture (below), and **the two roles are different requirements**: see the paragraph this row points at |
| PR back to the declared repo | `open_proposal`, `branch_for(idempotency_key)`, `PROPOSAL_OPENED`, the authoring tier's analyzer→proposer split | registered nowhere, same successor; and a proposal does not yet carry its **plan evidence** |

**Plan is the context, not only the gate — stated 2026-08-06, and it reorders the workflow.**
Where infrastructure is already defined in Terraform, there is no better context for a proposed
change than running `terraform plan` against the existing estate: it is the one instrument that
answers *what would happen if this were applied*, from the product's own engine rather than from
anything the platform infers. So plan appears **twice**:

- **Early and repeatedly, as reading.** The agent plans against the estate to understand it, and
  plans its own draft to see what the draft would do — possibly several times, adjusting between
  runs. Each is an ordinary governed step against the run's budget, and the authority for it
  already exists: the matrix binds `plan` as its own role, so a definition can hold generous
  plan authority while never holding `apply` at all. **Iterating on a plan is reading, and the
  ceiling can say so.**
- **Once and finally, as the gate.** The last plan against the authored tree is the one whose
  output travels with the proposal as evidence. A failed final plan stops the proposal.

**Three decisions this shape forces, recorded now so their features argue them rather than absorb
them:**

- **Plan-as-context needs the plan's *output* to reach the model.** Today a tool result returns
  to the loop, but a plan a model cannot read is context for nobody. What a plan output contains
  — resource addresses, attribute values, possibly data a secret leaked into — and how much of it
  enters the model's context is a real decision with 029's lesson attached (the read bounded by
  the wrong thing answered from 1,000 of 63,947 entries). Bounding what re-enters the model is
  this workflow's version of that problem.
- **Plan-before-propose is a workflow constraint, not a tool property.** The authoring tier's
  two-task split (analyzer authors, proposer publishes *"what already passed"*) is exactly the
  seam for it — the plan belongs at the end of the analyzer's work, and its output belongs in
  the proposal as evidence. A PR whose description carries the plan it passed is a different
  product from a PR that merely compiles.
- **The plan needs a real Terraform.** The fixture handlers were the right call while nothing
  could reach them; a workflow whose soundness gate is a fixture would be green forever
  (ADR-0047's exact shape). Deploying Terraform where the authoring tier runs is an
  infrastructure decision with a Principle VI cost to state.

**The same shape, second product — Vault policy authoring (added 2026-08-06).** *What exists?
How does this change affect what exists? Is there a better way to write this, given the defined
outcome?* — evaluated, then submitted back as a Vault policy PR. The workflow is the same; **what
differs per product is the impact instrument**, and naming it per product is what keeps the
workflow honest rather than generic:

| | Terraform | Vault policy |
| --- | --- | --- |
| read what exists | state and config via plan | policies and what is attached to them, via reads |
| impact oracle | **`terraform plan`** — the product's own engine answers *what would happen* | **no plan-equivalent for a policy as a whole** — capability checks answer *what a token could do* per path, and the rest is read-and-diff plus reasoning |
| "a better way, given the outcome" | the corpus's Terraform operating guides | the corpus's **Vault operating guides** — already pinned (`/validated-designs/vault-operating-guides-adoption`), already the answering surface's grounding |
| the proposal | PR carrying the final plan as evidence | PR carrying the policy diff, the capability-check results, and the guidance citations |

Two facts measured for this row: **Vault is the one product genuinely present in the enclave** —
the trust fabric runs on it, so plan-as-context's "deploy the product first" cost does not apply
here, which arguably makes Vault the *earlier* end-to-end demonstration despite Terraform naming
the workflow. And the existing `vault_read` handler already draws this workflow's most important
boundary: *"Read a secret's metadata and keys — never its values… the value itself belongs in the
process that consumes it, not in the reasoning about it."* Policy authoring needs exactly that
posture — the agent reasons about policy *structure*, and no secret value ever enters the
reasoning. The bounded-output decision above applies to capability-check results the same way it
applies to plan output.

**Sequence already pointed the right way, and its first step has landed**: 040 shipped 2026-08-07
(the model can say what to do) → **authoring becomes reachable, next** (the trio + proposals) →
this workflow as the composition feature that adds
the intake surface, the impact gate, and evidence-in-proposal — **per product**, with Vault plausibly first since its product is already in the enclave. Each earlier feature is
independently valuable; this entry is why they are ordered.

### Customer-supplied context (unnumbered)

A customer's own material — internal compliance policies, architecture standards, reference
designs — considered when the platform answers and when it authors. Raised 2026-08-06 as a
product requirement, recorded before it was specified.

**Measured, this is not "add a source".** `src/core/answering/corpus.py` has **no tenant
dimension at all** — one process-wide manifest at `corpus/manifest.json`, digest-pinned, and
*"nothing is fetched here"*: `infra/bin/corpus-sync` populates a cache and the reader refuses
anything whose digest does not match, because *"a corpus that fetched at answer time would make
every answer depend on a third party being reachable, and would make 'pinned' untrue."* Customer
content is per-tenant, arrives at runtime, and is not vendored through the platform's supply
chain. Every one of those cuts against the current model.

**The citation gate is the real constraint, not storage.** `answer.py` states it plainly — *"an
answer with no supported claims is a decline"* — and `corpus.py` calls citation resolution *"the
single most important check in this feature."* So customer documents cannot be context the model
merely reads; they have to be **citable**, or every answer grounded in them declines. Extending
resolution to content the platform does not control is the whole of the work, and doing it badly
weakens the gate for the corpus too.

**Three records already hold most of the vocabulary.** ADR-0030 (pinned versus consulted
artifacts) is the distinction this needs and may already name the customer case correctly.
ADR-0004 makes the corpus the supply chain's second subject — customer material is emphatically
not that, and saying so is half the design. ADR-0046 (multi-tenancy) owns the tenant dimension
the corpus lacks; this does not strictly *require* multi-tenancy, since a single-tenant
deployment could carry customer content, but it needs the same substrate and building the two in
ignorance of each other means building the tenant boundary twice.

**And it reaches authoring, not only answering.** *"Write the Vault integration for this repo"*
against a customer's architecture standards is the same requirement arriving through 038's path
rather than the ask path, which means whatever shape this takes has to serve both.

**Endorsement by an admin, configured in the interface** — added 2026-08-06, and it is plausibly
the *answer* to the citation problem rather than a complication. The gate needs a trust statement
about content the platform did not vendor, and *"an admin of this customer endorsed this
document"* is exactly that: a decision, made by a named person, at a time, which the trail can
carry. Officially endorsed is a governance fact, not a storage one.

Three things it collides with, all measured:

- **There is no `admin` role.** The subject vocabulary in `core/answering/scope.py` is
  `operator` and `compliance-analyst`, the latter introduced by 025 as a superset of the former.
  A third role is a change to the governance vocabulary, not a UI addition.
- **Governance records live in Terraform today**, operator-authored:
  `infra/modules/trust-fabric/` holds ceilings, model credentials and the authoring records. 026
  decided that shape on purpose — *"where a model is reachable from is assembly while which model
  is permitted is governance"* — and rejected deployment config for governance. Endorsing content
  through the portal moves a governance decision **out of Terraform for the first time**. That may
  well be right, because the person who knows whether an architecture standard is current is not
  the person with estate credentials, but it is a posture change to argue rather than assume.
- **The portal can already act, just not while asking.** `surfaces/portal/app.py:201` — *"A thread
  is where turns act; an ask never does (ADR-0039)."* So an admin surface is not unprecedented; a
  governance-**authoring** surface is.

**The shape, as described 2026-08-06**: an admin navigates to a configuration panel in the Brieve
interface and adds **Git repos** and **MCP server configs** the agent may consult. That is one
panel over **two features of very different size**, and conflating them is the risk.

**Git repos fit the model that exists.** Clone, digest, pin, cite — the `corpus-sync` pattern with
a tenant dimension and an endorsement record on top. *"Nothing is fetched here"* survives intact,
because you sync and then answer from the sync. Real work, but an extension of a thing the
platform already does well.

**MCP servers do not, and which half is meant decides everything.**

- **Resources only** — documents and data a server exposes. Closer to the Git case, but the pin is
  a genuine problem: you can digest-pin a cloned repo and you cannot pin a live query interface.
  Either its resources are synced like a corpus, or answers fetch at answer time, which
  `corpus.py` rejects with its reason attached.
- **Tools** — an MCP server exposing tools is a **capability source**, and the platform's shape
  suits this well. `invoke_tool` is the sole governed entry and the registry is the decision-maker
  — 036's seam states it directly: *"no blocklist, no allowlist, and no special case… the registry
  decides."* A tool admitted from an endorsed config is **less exotic than a name a model
  invented**, which that design already governs. What moves is *when* registration happens:
  `core/authority/ceiling.py:75` refuses `unknown_ceiling_entry` because the vocabulary is
  assembled before a run starts, and that is an implementation fact rather than a principle.
  Register from an endorsed source and a ceiling names customer tools like any other.

**Three things genuinely need deciding** — none of them a reason not to do it:

- **Eval gating.** Principle VIII gates capability packs on evals; a customer's own tools cannot
  be. The constitution's own pattern for this is a **named exception with a stated bound**, which
  Principle IV has taken three times. *"Endorsed customer sources are not eval-gated, and here is
  what bounds them instead"* is an ADR.
- **Credentials.** Whose credential reaches the customer's server, and where it lives. 027 built
  the broker for exactly this shape and its record is the precedent.
- **Freshness.** A repo can be synced and digest-pinned; a live MCP server cannot. Endorsement
  says *"this source is trusted"*, which is not the same as *"this response is what was reviewed."*

**Brieve has no MCP client yet.** `surfaces/mcp/served.py` is `FastMCP` — 019 built the platform
as a **server**. That is a substrate to build, not an obstacle.

**Why this matters more than its position suggests.** The pinned corpus is HashiCorp's validated
patterns, and a platform whose knowledge stops at one vendor's documentation addresses a small
part of what a customer environment actually is. Their compliance posture, their architecture
standards, their existing estate and their own tooling are the context that makes an answer
usable rather than merely correct. **Governance and external sources are not in tension** — the
governed entry, the registry, the ceiling and the trail are exactly the machinery that lets an
external source be admitted deliberately rather than absorbed silently, and the endorsement
record names who admitted it.

**Not scheduled.** Recorded so nobody re-derives the constraints; the ordering argument belongs
in its own specify. **The first question that specify must answer**: do customer MCP servers
supply *context* or *capability*? Everything above sizes differently depending on the answer, and
the phrase *"additional context or data"* suggests the first while *"MCP server"* usually delivers
both.

## Demand-driven / trigger-gated

Deliberately unscheduled. Each needs a recorded trigger before it enters [Next](#next) — that is
the decision, not an omission.

| Item | ADR | Trigger |
| --- | --- | --- |
| Second framework adapter (LangGraph) | ADR-0017 | Demand. The ADR makes it explicitly demand-driven; 004's FR-014 forbids shipping it speculatively |
| Dedicated workflow-engine durability provider | ADR-0024, ADR-0028 | A named trigger: scale, an existing deployment, or a requirement the library provider cannot meet |
| Wire-level guardrail (second protection layer) | ADR-0014 | Optional by design; in-process hooks are the primary layer |
| Retrieval | ADR-0029 | Runs in the Postgres a deployment already has — needs that Postgres to exist first |
| Row-level security on the evidence store | 008 | The tenant boundary on evidence reads is enforced by the application, not the database. `exists_outside_tenant` shows why that matters: the SQL role can see that rows exist under another tenant even though no content crosses. Postgres RLS moves the enforcement a layer down and is the right eventual home |
| RFC 8693 + RAR authority manufacture | **Closed by [ADR-0057](docs/adr/0057-context-hungry-agents-want-breadth-not-narrower-reads.md)**, and not by building it | Principle IV describes manufacture as "attested workload identity → control-plane Vault → **RFC 8693 + RAR** against ceiling policies"; what runs is a JWT auth-method login. **ADR-0056 established the mechanism** by reading the substrate rather than inferring it — Vault is the RESOURCE SERVER and cannot perform the exchange, its OIDC token endpoint accepting `authorization_code` and nothing else. **ADR-0057 then established that the narrowing is not wanted here**: these agents read widely before acting, so breadth of read is how the output gets informed, and the property the narrowing was for — just-in-time, short-lived, attested — is already held. `task scope` is satisfied for reads by per-allocation manufacture with a bounded TTL. RAR remains the mechanism for WRITE and ACT scopes when those enter a ceiling. **Owed — discharged 2026-07-31 (#77)**: ADR-0048 carries an appended amendment with the Decision left in place, the glossary's "effective authority" is corrected and gains a RAR entry, and Principle IV describes attested manufacture bounded by a ceiling and a lifetime. Constitution 1.2.0 → 1.3.0, MINOR on the v1.2.0 ADR-0033 precedent — a correction, not a policy change |
| Brokered credential translation | ADR-0044 | Principle IV names the broker's rotated management token as **the platform's single permitted standing credential**, and the mechanism it exists for does not exist. Until 010 the branch wrote a placeholder string and returned `allow`; it now refuses `broker_not_implemented`, which makes the gap visible when a deployment configures a brokered product. The entitlement-mirroring check in front of it is real and enforced |
| `no_default_ceiling_policy` on registrations | ADR-0050 | Vault appends `default` and `default-ceiling` to every registration unless this is set, which nothing here has ever set — so the effective ceiling has never been the declared one. The added policies are benign; the point is that a difference existed where the mechanism's whole claim is that none does. Setting it changes the posture of every registration and deserves its own decision |
| Ceiling / policy jurisdiction coherence | ADR-0050 | Two records for one definition can disagree: an agent granted a tool whose secrets it cannot read, or the reverse. A consequence of ADR-0044's disjoint jurisdictions rather than a defect, and nothing reports it. A cross-check would be a rule duplicated across engines, which is what ADR-0044 forbids — so the fix is probably an operator-facing report, not a gate |
| Vertical policy/content profiles | ADR-0003 | Horizontal first. Profiles ship as policy and content, not as forks |

## Owed Quality Gate rows

The constitution names these as blocking for adapters and providers. Under ADR-0047 each binds
when its feature lands, and until then must be **absent or an explicit skip citing its deferring
ADR — never a passing stub.**

> **Nothing is owed as of 021, 2026-08-01.** Every row below is in force or deferred by a named
> ADR that has not yet been implemented (tool-call parity, ADR-0040). The last genuinely owed one
> was report fidelity, which had been an explicit skip since 013 because `RunReport` did not
> exist to score.
>
> **The heading stays.** ADR-0047 makes a row binding the moment its feature exists, so the next
> feature to attach one needs somewhere to record it as deferred — and a table that has been
> empty once is easier to fill correctly than a convention somebody has to re-derive.

| Row | Attaches with | Status |
| --- | --- | --- |
| Governance-ordering, fail-closed, governed entry | 004 | ✅ In force |
| Durability scenarios (ADR-0024/0026, as amended by ADR-0049) | 005, amended by 009 | ✅ In force — all seven, both providers, under an attested identity. **Now run by CI** on same-repo pull requests: 009's enclave lane holds the licensed Vault as a repository secret, which a fork-originating run cannot read. Fork pull requests still fall to the agent harness per `AGENTS.md`. The grant-expiry row asserts *stopping* rather than parking — inverted by ADR-0049, not removed |
| Surface parity | 009 | ✅ **In force.** Amended, then satisfied. It read "across all four transports"; 009 has two, so claiming it would have asserted something untrue — the stub ADR-0047 forbids. 009 amends it to bind **incrementally**, across every pair of implemented transports, and satisfies it for the API/MCP pair. Better than claiming or deferring: the gate now binds at two, three, and four rather than catching nothing until the last transport lands, which is well after divergence would start. Compared against `specs/008-northbound-api/contracts/operations.snapshot.json` |
| Tool-call parity under deferred disclosure | Deferred-disclosure feature | Deferred — ADR-0040 |
| Eval gates (packs, models, policies) | 013, completed by 021 | ✅ **In force — all five, and nothing is owed.** Must-deny, must-decline, citation accuracy, and estate-state run blocking against both shipped packs, scored on fixtures with a marked live lane behind a named runner. **Report fidelity closed by 021**: `RunReport` exists, and the suite scores a compiled report against labelled material events by **precision and recall** rather than a verb — omitting a denial and inventing a success are opposite failures, and one verdict would let either hide the other. A fidelity case labelling no events is refused at load, because precision and recall over an empty set pass for any report: the thin corpus ADR-0018 predicts, wearing the schema's clothes. Measured suites are excluded from the judge-span requirement — fidelity is never judged, so seeds for it would qualify a judge on verdicts it will never render. The judge chain terminates at a human-labeled seed set (ADR-0052) |
| Registry isolation (control-plane write denials) | 018 | ✅ **In force.** Fourteen bounding paths get a real write attempt under a real run's authority, against the live control plane, and every refusal is observed. The mechanism always held — every policy grants read and list and nothing else — but nothing had ever *attempted* one, so the guarantee rested on someone having read the Terraform and concluded correctly. **Half the paths are named rather than derived**, because a run holds no read access to the grant that bounds it, to what decides which grants it receives, or to the trusted-key configuration, and no derivation can reach what it cannot see. A refusal counts only where the same authority can see the path — the control plane answers identically for *forbidden* and *absent*, so a row reading denial as proof would pass with one letter wrong in its path, forever. The break was demonstrated, not argued |
| Accessibility (WCAG 2.2 AA, rendered interface) | 012 | ✅ **In force.** A gate class no prior lane could run: every other gate asserts something about a process, this one about a rendered page. Twenty-one rows: a vendored, pinned axe ruleset over every page state, **plus a keyboard-and-screen-reader harness** that walks the real tab order against visual position, reads the browser's own accessibility tree over CDP, measures focus indicators and target sizes, and re-renders under the reflow and text-spacing criteria. **No named runner is owed** — what was once a manual checklist runs in CI, and it found three defects on its first run. What stays outside a browser's reach (whether the words are good; any specific screen reader's behaviour) is recorded in the contract |

## Open records

One ADR remains **Proposed** and is expected to resolve rather than linger. It does not block the
sequence above, but a Proposed record that quietly becomes permanent is a failure of the process
([`docs/adr/README.md`](docs/adr/README.md)).

- **ADR-0054** — model-written orchestration, per-call and per-delegation parity. Left Proposed
  by [036](specs/036-deferred-disclosure-code-mode/spec.md) **on purpose**: its per-call half was
  realized and its delegation half has no substrate to govern, because the orchestration package
  still carries an `experimental` import segment and its durable-workflows extension has not
  landed. Governing an object that cannot yet be invoked would be a rule nothing exercises.

**ADR-0011 resolved on 2026-08-05** (Accepted, on basis (2) — the dependency was withdrawn after
examination rather than inherited). It had been the entry here since 2026-08-01, and this section
still named it hours after the change. **That is the defect this file's own `Next` section warns
about, in the file a planner reads first** — and it is the second time: three shipped entries sat
under `Next` until the same day. A stale record here is not a tidiness problem; it produced two
wrong recommendations in a single session before anyone checked it against `src/`.


## Known gaps in the record

Found while deriving this file. None blocks work; all three make the record harder to reason
from, and each is worth its own small change.

### 0a. `resume_run` has no production caller — **CLOSED by 014, 2026-07-30**

**Found 2026-07-29 while tracing 013's dispatch path. Closed by
[`specs/014-dispatched-resume`](specs/014-dispatched-resume/).**

`resume_run` was invoked from tests and from nowhere in `src/`, so 005's conformance rows —
"a disrupted run resumes and completes", "re-observe, never re-execute" — were true of the
function and not of the dispatched path. The entrypoint ignored `RUN_STEP_INDEX`, called
`start_governed_run`, and began its loop at zero.

**Closed with evidence rather than with a wiring change.** All ten dispatch-level rows in
[`specs/014-dispatched-resume/contracts/conformance-resume.md`](specs/014-dispatched-resume/contracts/conformance-resume.md)
pass against the live enclave: a real allocation killed mid-flight by the scheduler resumes in
a second allocation and completes with exactly one execution per step, re-observation decides
both directions against real Vault with the shipped observer, a suspension names its product
and the sweeper revives it unaided, the revival budget is bounded and terminal, lapsed consent
stops the run, and fencing holds through a real overlap.

**Four defects it uncovered on the way**, each invisible for the same reason — the only thing
that would have exercised it was the caller that did not exist:

1. The `grants` table did not exist. `checkpoints.grant_id` had resolved to nothing since 005
   and carried the 15-minute credential id, so consent expiry was unevaluable.
2. `record_suspension` had no callers at all — the suspended-run index had a reader and no
   writer.
3. **The sweeper had never dispatched anything since 009**, reaching the scheduler on a
   loopback address that belongs to the container rather than the host.
4. `VaultWriteObserver` could not be called: it required an argument the `Observer` protocol
   does not pass, so every interrupted Vault write suspended its run rather than resolving.

### 0b. The collector credential was a hand-written password — **CLOSED by 015, 2026-07-30**

**Raised by Dan while reviewing 015, three times, because the first two answers were also
wrong.** The platform held `harness_shipper` as a fixed password written into a Vault KV path
by bring-up, where every other database credential it uses is Vault-managed. 015 defended this
with claims that had not been checked: that federation was unavailable across an
administrative boundary (backwards — federation is the mechanism *for* crossing one), that
removing the standing credential needed a second Vault, and that rotation needed bespoke
automation. None were true.

**Closed by onboarding the account as a ROOTLESS static role**
([`audit-egress.tf`](infra/modules/trust-fabric/audit-egress.tf)). `self_managed = true` means
Vault holds no privileged account at the collector: it connects *as* `harness_shipper` and
rotates that account's own password on a 24-hour period. The maximum privilege obtainable
through this Vault at the destination — by an operator with the root token, or by anyone who
compromises it entirely — is the shipper's own `INSERT`/`SELECT`. Seeding the collector's root
instead, which is how a database is normally registered, would have let whoever controls this
Vault define a role granting `UPDATE` on `shipped_entries`: exactly the tampering ADR-0055
exists to prevent. Rootless is not the convenient option, it is the one that survives the
threat model.

**The bootstrap password is a non-event**, which is the general principle worth keeping: Vault
rotates on import, so the seed in `roles.sql` stops authenticating the moment onboarding
succeeds, and the password in force afterwards is known to nothing but Vault. Same disposition
`rotate-root` gives the state store. A row asserts the seed is dead rather than trusting it.

**Three rows** in [`test_credential_rotates.py`](tests/conformance/evidence/test_credential_rotates.py):
the seeded password authenticates nothing; a forced rotation changes the credential and kills
the old one; and shipping survives a rotation because the shipper reads the current value
rather than caching one — a cached credential fails on a 24-hour cadence, looking like the
collector going down, days after anyone touched the code.

**The boundary never rested on password secrecy**, and this is what made the earlier reasoning
go wrong: it rests on the grant list. An administrator holding the password gains exactly what
the platform already legitimately has, and `probe()` goes on demonstrating `UPDATE`/`DELETE`
refused every pass. Conflating "who knows the password" with "what the account may do" is what
made a second trust store look load-bearing.

**ADR-0044's count stands at one.** There is no second standing credential.

### 0c. A kill between a step's result and its audit entry loses the entry — **CLOSED 2026-07-31**

**Found 2026-07-30 by 015's full gate run**, which failed `test_dispatched_resume`'s
exactly-once row with 399 outcomes for 400 steps. The run's data settled what happened: 400
intents, **400 results**, 399 `TOOL_OUTCOME` events. Every step's effect happened and was
durably recorded exactly once; one produced no audit entry.

**The window.** A step records its result and *then* audits `TOOL_OUTCOME`. A kill between
the two left an effect that happened, was recorded in `results`, and had no entry in the
trail — and the resume correctly did **not** re-execute it, because `closed_intents` saw the
result, so the entry was never written afterwards either.

**The ordering was never the bug.** Auditing first would be worse: a kill between the audit
and the result leaves a `TOOL_OUTCOME` for a step with no recorded result, the resume
re-executes it, and the side effect happens twice. Exactly-once is the more important of the
two properties and the current order is the right trade.

**Closed by recording the skip.** `STEP_REOBSERVED` names each step a resumed allocation did
not execute and why — `result_recorded`, `reobserved_complete`, or `below_checkpoint`. Those
are three genuinely different claims (the step's own record that it finished; a judgement
about an open bracket; a coarser backstop for steps that never bracketed), and collapsing
them to "skipped" would lose the difference an investigator is asking about. "Re-observe,
never re-execute" is now a statement in the trail rather than an inference from counts.

**What the conformance row asserts now**, having previously only bounded the hole at one:
between outcomes and re-observations, no step is silent. Deliberately not a partition — a
step the first allocation ran has an outcome *and* is re-observed by the resumed one, so the
records overlap by design and their counts do not sum to the run's length. An earlier draft
of the assertion claimed a partition and failed on a clean run, which is how the overlap got
noticed.

**Still true, and worth keeping visible**: `TOOL_OUTCOME` carries no step index, so the
reconciliation is by count and by the re-observations' named steps rather than by a per-step
join. Adding the index would make it exact and is a small change to the hooks engine's
payload — worth doing whenever that path is next open.

### 0d. No lane runs a served surface, so `build()` has never been executed by CI — **CLOSED by 017, 2026-07-31**

**Raised 2026-07-31, while wiring the API to a real identity provider.** The API job's
workload identity is `nomad_job_id = "api"`; `service.py` asked Vault for the default
`harness` role, whose bound claim is a different job. Every login was refused, the allocation
died in `audit_sink.migrate()`, and **the northbound surface had never served a request in a
deployed enclave.** It surfaced by running `portal-up` and reading the allocation logs, which
nothing in CI does.

The specific bug is fixed (#79). The gap is what let it live: **no lane executes
`service.build()`.** `make dev-up` brings up Vault, Nomad, Postgres, the mcp service and
agent-run; `portal-up` brings up the API and the portal and is never run by CI. Component
tests call `create_app` with doubles, so the assembly — the one code path with no coverage by
construction — is exercised by nothing.

That is the common cause behind a pattern this file has recorded five times under different
names: `resume_run` with no production caller (014), a sweeper that had not dispatched since
009, an observer the protocol could not call, an egress loader reading a `VAULT_TOKEN` no
allocation has (015), and claim mappings nothing read back (#78). Each was found separately
and fixed separately. **They are one absence seen five times**, and 015 already wrote the
answer for a single service in
[`test_the_service_ships.py`](tests/conformance/evidence/test_the_service_ships.py), whose
docstring counts four of them and names the shape: *"a capability that is correct, tested,
and wired to nothing."*

**The mitigation is a lane that stands the served surfaces up and puts a real request through
each.** Not a health check — a request that traverses the assembly, the attested identity, and
the trust fabric, so the row fails for the reason the deployment would. Precedent for the
shape exists twice: the mcp shipping row above, and 012's accessibility lane, which was also
a gate class no prior lane could run.

Open questions worth settling before building:

- **Whether it joins the enclave lane or becomes a third.** Registering these services at
  bring-up once cost the enclave lane ten minutes and left the conformance job unplaceable,
  which is why `portal-up` is separate — recorded in its own header. That constraint has not
  gone away.
- **What "answered" must mean.** A 401 from a surface that booted is a pass; a 401 from a
  surface that never read its configuration is indistinguishable at the socket. The row has to
  assert something only a correctly assembled process can produce.

**Closed by [`specs/017-deployment-lane`](specs/017-deployment-lane/).** `make conformance`
now ends by standing the API and the portal up and asserting each answers **as itself** — an
unauthenticated request returning the surface's own reason code, which a process that read no
configuration cannot produce. Twenty-one rows. The break was demonstrated rather than argued:
the API pointed at a nonexistent Vault role failed the lane, named the API, and printed
`role "no-such-role" could not be found`.

**What it does NOT close, stated because the entry above invites the wrong reading.** Four of
the five instances listed here were already covered — by 014's durability rows and 015's
shipping row, built for those features. This gate's own contribution is the fifth, the API's
start-up, plus making the other four's coverage *checkable* rather than incidental. The full
assessment is in the feature's conformance contract, including the rows it would not have
caught.

**Two defects were found by running it that eight analysis passes had not**: the failure path
reported "answered nothing" while the process's own error sat unread in the allocation's
stderr, and the wait stopped at *placed* rather than at *answering* — so rows failed against
surfaces that were merely young. Both are the shape this whole gap is about, arriving one
level up: a thing that looked right on paper and was wrong when run.

### 0e. No model is in the loop — a dispatched run executes a scripted tool sequence — **CLOSED by 020, 2026-08-01**

**What closed it.** `_tool_for_step` is deleted, and a dispatched run asks the model its
definition's binding map names. The name goes to the same `invoke_tool` the scripted name went
to — no new path to a capability — and the trail records who chose it as a distinct
`TOOL_CHOSEN` event. `build_governed_agent` finally has a production caller, ten features after
it was written.

Governance also became a **signal** and not only a wall: a refused choice goes back to the
model, which may choose again, bounded per step, every attempt recorded, and exhausting the
bound is a recorded terminal outcome. That bound is the whole reason the signal is safe — a run
grinding against its ceiling and a run thinking hard are the same picture from outside.

The three things this gap said it needed are all now load-bearing. The binding map and the
Qualified Model Matrix are read on every model-driven run and refuse before any provider call
(and 020 authored the first matrix record this repository has ever had — 013 built the reader,
the policy grant, and the validation, and nothing ever wrote a cell). Principle VIII's gates
are consumed rather than advisory. `RunReport` (ADR-0018) was **still owed** when this note was
written and is the one thing 020 named as remaining — **closed by 021 the same day**, which is
why a model-driven run was exactly the thing a report turned out to be about.

**What is true, and what is still not.** The choice is *governed* — refused when it must be,
recorded either way, durable across a kill, and made by the model the matrix bound. Whether the
choice is **good** is an eval question (Principle VIII) and 020 asserts nothing about it. A
demonstration of a model picking the obviously right tool is far more persuasive than what it
proves, which is why the conformance contract states that limit as prominently as what it does
assert.

**Reaching the mcp service from an IDE: CLOSED, and it was closed by 019 rather than by anything
after it.** This note claimed the service used host networking and was unreachable from the
developer's machine. Measured 2026-08-01: `infra/jobs/mcp-surface.nomad.hcl` uses **bridge mode
with static port 8083 published to loopback**, and the jobspec comment beside it explains that
host mode on Docker Desktop is the VM's namespace and was therefore wrong. The surface speaks
streamable HTTP at `http://127.0.0.1:8083/mcp`; a client attaches with a bearer token whose
claims map to a role.

The note survived three features because nobody tried it — which is the shape this file's own
gap section is about.

<details>
<summary>The gap as originally raised (2026-07-31)</summary>

**Raised 2026-07-31, answering "how close are we to running a task end to end?"** The
governance chassis is complete and proven; the agent is not connected to it.

`surfaces/dispatch/entrypoint.py` picks each step's tool by round-robin:

```python
def _tool_for_step(tools: list[str], step: int) -> str:
    return tools[step % len(tools)] if tools else ""
```

`adapters.pydantic_ai.build_governed_agent(model, ...)` exists, takes a model, and installs
governance outermost so no capability downstream can produce an ungoverned execution. **No
production caller passes it a model.** The only real provider call in the tree is
`adapters/anthropic_scorer.py`, which scores evals — not runs.

**What this does and does not mean.** Every durability and governance guarantee is real and
asserted against live infrastructure: kill/resume, fencing, re-observe-never-re-execute,
grant expiry, hash-chained evidence, hooks failing closed, authority manufactured per
allocation from an attested identity. Those hold. What has never happened is a **model**
choosing a tool and that choice being governed — which is the thing the platform exists to
do, and the one path with no coverage because it has no caller.

This is the sixth instance of the shape ROADMAP gap 0d names, and the largest: a capability
that is correct, tested, and wired to nothing. 017's lane would not catch it — the dispatch
entrypoint runs, completes, and writes evidence; it simply never consults a model.

**What it needs**, and why it is a feature rather than an afternoon:

- The Qualified Model Matrix binding path (ADR-0022, ADR-0039) exercised for real rather
  than resolved and discarded. A definition's binding map names a model per role; nothing
  currently turns that into a provider call.
- Principle VIII: models promote only through eval gates. Putting a live model in the run
  loop makes those gates load-bearing rather than advisory.
- ADR-0018's `RunReport` is still owed, and a model-driven run is the first thing whose
  output a report would be about.

**Related but separate**: reaching the mcp service from an IDE — what stands between "the
platform works" and "I can watch it work". **Closed by 019 and verified 2026-08-01**: bridge
mode, port 8083, streamable HTTP, seventeen tools listed by a real client. See the note under
gap 0f. What remains is ergonomic rather than structural: the development identity provider
mints five-minute tokens, and a static `Authorization` header in an editor's config has no
refresh flow.

</details>

### 0f. The MCP surface has no server — **CLOSED by 019, 2026-08-01**

**Raised 2026-07-31, while scoping "connect it to Cursor."** The expected answer was
networking: the mcp job uses host mode, which on Docker Desktop is the VM's namespace and not
the developer's machine. That is real and it is not the problem.

`McpTransport` — ADR-0033's second transport, with 56 conformance rows and the surface-parity
gate in force against it — **is constructed nowhere in `src/`**. Its only caller is
`tests/harness/api_fixtures.py`. There is no JSON-RPC framing anywhere in the tree: no
`initialize`, no `tools/list`, no `tools/call`. `mcp==1.28.1` is a declared dependency that
nothing imports.

The `mcp` job is named for the surface and does not serve it. What it runs is the supervisory
loop — health checks, the sweeper, audit egress — which is what 010 owed and delivered. The
module's own docstring said the rest was next: *"The transport's operations and the sweeper's
resume path are the tasks that follow."* The sweeper's half landed in 014. The transport's did
not, and nothing noticed because the parity gate compares the transport **class** against the
API's, and the class is correct.

**This is the seventh instance of the shape 0d names**, and the sharpest: parity is asserted
in force between one surface that answers real requests over a real socket (017 proved it —
`GET /threads → 200` from the API's own log) and one that no client can reach.

**What it needs**: a process that speaks the protocol over a transport a client can attach to,
constructing `McpTransport` the way `api.nomad.hcl` constructs `build()`, plus the
reachability fix the networking question was actually about. The operations exist and are
tested; what is missing is the framing and the front door.

**Closed.** The surface is served, reachable from the developer's machine, and driven by
eighteen rows through the SDK's own client over a real socket. Born in bridge mode rather than
converted, because the measurement was done first.

**It found a defect four features old that no existing gate could see.**
`McpTransport._start_run` never passed `subject_roles`, so every run started through MCP
reached its allocation and died with `no role for subject`. The API had passed them all along.
The surface-parity gate compared the two transports, saw both answer `202`, and could not see
that only one produced a run able to authorize itself — **parity compared the answer, not the
consequence.** Found on the first live `start_run`, which is the whole argument for rows that
drive a served process.

**Ordering note.** This is separate from 0e and smaller. A served MCP surface with the current
round-robin tool selection is still the platform working — a client connects, a governed
operation runs, evidence is written — and it is what makes 0e watchable when it lands.

### 0. The audit trail is not shipped off-host, and hash-chaining only *detects* — **CLOSED by 015, 2026-07-30**

**Closed by [`specs/015-audit-egress`](specs/015-audit-egress/), which implements ADR-0055.**
Every entry and every stream head now ships to a second Postgres the platform holds an
append-only credential for and nothing more, and reconciliation is a named, scheduled,
audited operation on both transports. Thirteen rows in
[`contracts/conformance-egress.md`](specs/015-audit-egress/contracts/conformance-egress.md)
run against that store under the collector administrator's credential — including the
consistent truncation that defeats chain, grant, and local head together, and a real
outage that stops the collector's container mid-flight.

**Both open questions were answered in clarification rather than by whoever built it
first**, which is what ADR-0055 asked for: shipping is spooled (draining the entries
already written, so no spool table exists), and a failed *delivery* refuses nothing while
a failed *capture* still refuses the step.

**The claim does not grow.** This detects; it does not prevent. A single-domain compromise
now leaves evidence of itself, an attacker holding both domains still defeats it, and the
lag window — entries written but not yet confirmed at the second copy — is real, bounded by
the ship interval, and reported as a backlog anyone can watch. It also introduces the
platform's **second standing credential**, which ADR-0044 called a constitutional event;
that is named in ADR-0055's Notes and ADR-0044's count is not amended here.

The original entry follows, unedited.


**Raised by Dan, 2026-07-29, during 013's live gate run. The most consequential gap on this
page.** Now **decided** by [ADR-0055](docs/adr/0055-audit-egress-for-tamper-evidence.md)
(**Accepted**) — the rule is settled and nothing is built, so this stays a gap in the
*implementation* rather than in the record.

**One correction to how this entry was first written.** It framed off-host shipping as a
straightforward mitigation without citing
[ADR-0020](docs/adr/0020-otel-only-backends-at-the-collector.md), which already states that
**the audit plane never egresses by default** and that SIEM export is an explicit, configured
act. That is a deliberate posture for regulated estates, not an oversight — so the real
decision is a *tension* rather than a gap, and ADR-0055 is where it is resolved: the trust
boundary that matters is **administrative, not topological**, and a collector the organization
operates under administrators who are not the platform's satisfies tamper-evidence without
becoming the third-party egress ADR-0020's default guards against.

Everything downstream of the audit plane rests on evidence being trustworthy, and today the
whole of it lives in one Postgres this platform operates. The chain is honest about what it
gives: `audit_entries` is append-only *by grant* (the evidence role holds `SELECT` and nothing
on `audit_stream_heads`), and `audit_stream_heads` exists because a hash chain cannot detect
truncation — delete the newest three entries and `seq 0..N-4` verifies perfectly.

**But detection is not prevention, and both tables are in the same database.** An actor with
write access to that Postgres can rewrite entries *and* the head that would have exposed the
rewrite, consistently, and nothing anywhere disagrees. The property the platform claims —
evidence that cannot be mutated or masked — is currently enforced by a grant inside the same
blast radius as the data it protects.

**The mitigation is to ship each entry off-host as it is written**, to a system under
different administrative control: Splunk HEC, an OTLP log endpoint, New Relic, syslog to a
collector — the target matters less than the trust boundary. Tampering then requires
compromising two systems that do not trust each other, and the off-host copy is what an
investigator reconciles against.

**The seam already exists and this is cheap.** `AuditSink` is a protocol
(`core/audit/sink.py`) with two implementations; a fan-out sink that writes Postgres *and*
streams to a collector needs no signature change and no core rework. Two design questions are
real and unresolved:

- **Synchronous or asynchronous.** Principle VI says nothing blocking that could be an async
  emitter — but an emitter that can drop is an evidence gap nobody sees, which is the failure
  this whole idea exists to close. A local durable spool that the emitter drains is probably
  the answer: the write blocks on the spool, never on the network.
- **What a failed ship means.** `start_governed_run` already refuses a run whose
  `AUTHORITY_ISSUED` could not be audited. Whether an unshippable entry should refuse a *step*
  is the same question one layer out, and the answer decides whether this is a governance
  control or a convenience.

Needs an ADR before a feature. It is not 013's work — recorded here while the reasoning is
fresh, because a gap in the evidence plane is the one kind this platform cannot afford to
carry silently.

1. **R1–R17 are referenced but never defined in-repo.** The constitution requires every spec to
   declare which mandated requirements it touches, and the spec template enforces it — but no
   file enumerates them. Every spec to date has cited them from context. They should be written
   down.
2. **The architecture document the constitution cites is not in this repository.** The
   constitution says it is "sourced from architecture v1.14"; that document lives elsewhere.
   Anything it contains that governs — including sequencing — is currently unavailable to anyone
   working only from the repo, which is what made this file necessary.
3. **The registry-isolation gate row has no owning feature — CLOSED by 018, 2026-07-31.** It was
   named in the constitution's Quality Gates while no ADR deferred it and no planned feature
   attached it. 004's conformance contract recorded it as deriving from Principle IV and ADR-0025
   rather than from a deferral, and named both possible fixes: a feature claims it, or ADR-0047
   distinguishes *deferred by decision* from *not yet applicable*.

   **Both happened, in one change.** 018 carries the row against the live control plane, and
   ADR-0047's amendment of 2026-07-31 names the two states — with the row that prompted the
   distinction as the first thing the distinction is applied to.

## Maintaining this file

Update it in the same change that lands a feature or defers work — not afterwards. A deferral
recorded only in a spec's "out of scope" list is invisible to whoever plans the next feature,
which is the failure this file exists to prevent.

**Landing a feature means removing its `Next` entry, not only adding a `Shipped` row.** On
2026-08-05 three entries were found still sitting under `Next` — northbound surfaces, portal
answering, capability packs — every one of them shipped, one of them describing machinery as
absent that had existed for months. Both halves had been done for each: the Shipped row was
written and the Next entry was left. Nothing detects this, because a stale forward-looking
section is indistinguishable from an ambitious one; the only thing that catches it is reading
`Next` against `src/` before believing it. **This file is the first thing a planner reads, so
it is the most expensive one to leave wrong** — this drift produced two wrong recommendations
in a single session.
