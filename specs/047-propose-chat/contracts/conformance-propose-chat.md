# Conformance: Propose chat (047)

## Hermetic / CI

| ID | Claim | How it can lose |
| --- | --- | --- |
| P1 | Propose intake rejects missing/malformed repository or empty task | Accepts empty task or bad URL |
| P2 | `repository_not_owned` refuses before subject acquisition side effects that imply success | Opens path as if owned |
| P3 | Phase order is Research→Plan→Write→Judge→Propose; progress exposes all five | Skips or reorders user-visible phases |
| P4 | Failed phase stops later phases; no PR URL on success payload | Later phase completes or PR presented |
| P5 | Judge deny → no publish | PR opened after deny |
| P6 | Final plan fail → no publish | PR opened after plan fail |
| P7 | Portal Propose composer has no agent picker | Agent `<select>` on Propose |
| P8 | Ask cannot open a PR (regression) | Ask path creates forge PR |
| P9 | Phase messages contain no secret-shaped values | Credential/token appears in reason |
| P10 | API and MCP propose progress meaning match (parity fixture) | Divergent phase/outcome shapes |

## Enclave / named runner

| ID | Claim | Runner |
| --- | --- | --- |
| E1 | Real PR opened on owned demo repository after successful propose | Dan — enclave + forge |
| E2 | Real terraform plan failure blocks PR | Dan — enclave with Terraform |
| E3 | SSE/UI shows at least one mid-run phase transition | Dan — walkthrough |

**Named runner**: Dan McTeer (maintainer). Enclave rows fail loudly when the enclave is
absent (do not skip green).
