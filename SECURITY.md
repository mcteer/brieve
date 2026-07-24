# Security Policy

This project is security infrastructure: it exists so that organizations can delegate
infrastructure work to agents without giving up their guarantees. A vulnerability here
can undermine the controls an operator is relying on, so we treat reports seriously and
ask you to report them privately.

## Reporting a vulnerability

**Report privately. Do not open a public issue, discussion, or pull request.**

Preferred: [GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository (Security → Report a vulnerability).

Alternative: email **security@\<domain\>**, encrypted to our published PGP key if the
content is sensitive.

**Include**: affected version and component, deployment profile and substrate, a clear
description of the impact, and reproduction steps or a proof of concept. If governance
behavior is involved, include the correlation ID and the relevant hook decisions —
**redacted**. Never send us real credentials, real customer data, or raw production
audit records; we don't want them, and receiving them creates a problem for both of us.

**Do not** include a working exploit in a pull request, test any system you do not own
or have explicit permission to test, or access data that is not yours while
investigating.

## What we commit to

| Stage | Target |
| --- | --- |
| Acknowledgement of your report | 3 business days |
| Initial assessment and severity | 10 business days |
| Fix or mitigation for critical/high | 30 days from confirmation |
| Coordinated public disclosure | Within 90 days, sooner if a fix ships earlier |

We will keep you informed as the assessment progresses, credit you in the advisory
unless you prefer otherwise, and coordinate timing with you. If we disagree about
severity or whether something is a vulnerability, we will explain our reasoning rather
than closing silently.

If a report reveals an issue in an upstream product or a third-party MCP server, we
will tell you and coordinate with that vendor's disclosure process — but the report is
theirs to receive, and we will ask you to file it with them.

## Severity: what matters most here

The following are treated as **critical or high** regardless of how difficult they are
to trigger, because each one falsifies a guarantee this product makes:

- **Governance bypass** — any path by which a tool call reaches a product without
  passing the hook pipeline, or by which enforcement fails *open* rather than closed.
- **Scope amplification** — an agent acting with authority exceeding the requesting
  user's, including through delegation chains, inter-agent handoff, brokered
  credentials, or a confused-deputy path.
- **Cross-tenant leakage** — any read, write, cache hit, precedent reuse, or evidence
  query that crosses a tenant boundary.
- **Audit integrity** — tampering with, suppressing, or forging audit records; breaking
  the hash chain; masking events from the governed read path; or evidence access that
  is not itself recorded.
- **Credential exposure** — secret values reaching model context, logs, spans, audit
  records, generated code, or PR bodies; token replay after resumption; any standing
  credential beyond the single documented exception.
- **Registration bypass** — an unregistered workload obtaining credentials, or an
  unregistered, review-overdue, or drifted tool executing.
- **Control-plane compromise** — an agent influencing its own definition, ceiling,
  registration, or the platform that governs it.

## Scope

**In scope**: this repository's code — core, adapters, hook pipeline, registries,
identity flows, durability, audit, surfaces (MCP/API/CLI/portal), first-party native
tools, capability packs, and the installer.

**Out of scope**:

- Vulnerabilities in HashiCorp, IBM, or other vendor products themselves — report those
  to the vendor. We will help you route them.
- Third-party MCP servers we do not maintain. If our *hardened deployment profile* for
  one is inadequate, that **is** in scope.
- An operator's own misconfiguration, unless our defaults, documentation, or preflight
  checks led them there — in which case, please do report it.
- Findings from automated scanners with no demonstrated impact.
- Denial of service through legitimate resource consumption (large runs, expensive
  queries); resource bounds are a product concern, not a security report.

**Model behavior specifically.** Two cases that look similar and are not:

- **Not a vulnerability**: causing an agent to produce wrong, unhelpful, or
  embarrassing output, or to take an action *within the requesting user's own
  authority*. Ungoverned reasoning is a documented property of local-loop (Path B)
  integration, and a user directing an agent to do something they are entitled to do is
  the product working. Quality problems are bugs or eval gaps — file them normally.
- **A vulnerability**: prompt injection or any other model-mediated path that **escapes
  scope** — causing an action beyond the user's entitlements, leaking data across a
  tenant boundary, exfiltrating secret values, bypassing a hook or approval, or
  corrupting audit. The distinguishing question is not "did the model misbehave" but
  "did the model's misbehavior cross a boundary the platform promises to hold."

## Supported versions

Security fixes are provided for:

- The **current stable** release and the one before it.
- The **current regular** release.
- All **LTS** releases within their 12-month support window.

Fixes land on `main` first and are backported to affected supported branches. LTS
branches receive security and critical fixes only. Anything outside these windows
requires upgrading; we will say so plainly rather than issuing an unsupported patch.

## Advisories

Confirmed vulnerabilities are published as GitHub Security Advisories with CVEs where
applicable, and mirrored in release notes. Advisories state affected versions, severity
and vector, the fix version, and mitigations for operators who cannot upgrade
immediately.

**Air-gapped and regulated operators**: advisories are also published in a
machine-readable feed and included, signed, in the release bundle, so estates without
egress can consume them through their existing transfer process. If you operate offline
and need advisory delivery arranged, contact us at the security address.

## For operators

- Deployment hardening, profile guidance, and the shared-responsibility boundary are in
  the operations documentation — several controls are yours to configure, and the
  documentation is explicit about which.
- Run `harness doctor --preflight` before upgrading; it surfaces version drift and
  incompatible artifacts, including advisories affecting your pinned set.
- Report suspected exploitation of a live estate through the security address, not
  through public channels, and preserve your audit records — they are the evidence.

## Leaked credentials

If a credential belonging to you, this project, or an operator is exposed — in a commit,
an issue, a log, or anywhere else — treat it as compromised: rotate it immediately, then
notify us at the security address. Do not attempt to resolve it by rewriting history
alone; published history is assumed captured.

## Safe harbor

We will not pursue or support legal action against researchers who act in good faith
under this policy: report privately, avoid privacy violations and data destruction,
test only systems you own or are authorized to test, and give us reasonable time to
respond before disclosure. If you are unsure whether an activity is authorized, ask
first — we would rather answer the question than receive the report afterward.

There is currently no paid bug bounty. We credit researchers in advisories and are
glad to say so publicly.
