# SPDX-License-Identifier: Apache-2.0
"""Rows asserting that the DEPLOYED processes run — 017, closing ROADMAP gap 0d.

Every other gate in this repository asserts something about a process the test itself
constructs. These assert something about the process a *deployment* constructs, which is
the one code path with no coverage by construction: component tests call `create_app` with
substitutes, and the served process is a different object assembled by code no test builds.

**What these rows assert: REACH, not correctness.** A collaborator wired to the *wrong*
place still assembles, still answers, and still passes here. What this closes is the class
where a collaborator is wired to *nothing* — which this repository has now found and fixed
five separate times under five names, most recently a northbound API that had never served
a request in a deployed enclave because its assembly asked for a credential role bound to a
different job.

Describing this package as proving the deployment correct would be an overstatement. The
conformance contract says so, and so does this docstring, because the two places someone
looks are the contract and the code.
"""
