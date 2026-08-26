// SPDX-License-Identifier: Apache-2.0
// Build phase strip + outcome (047). textContent only; markup stays the server's.
(function (global) {
  "use strict";

  function setOutcome(htmlClass, text, href) {
    var box = document.querySelector("[data-propose-outcome]");
    if (!box) return;
    var existing = box.querySelector("p");
    if (existing) {
      var sameClass = existing.className === htmlClass;
      if (href) {
        var link = existing.querySelector("a");
        if (
          sameClass &&
          link &&
          link.getAttribute("href") === href &&
          link.textContent === text
        ) {
          return;
        }
      } else if (sameClass && existing.textContent === text) {
        return;
      }
    }
    box.textContent = "";
    var p = document.createElement("p");
    p.className = htmlClass;
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      a.textContent = text;
      p.appendChild(a);
    } else {
      p.textContent = text;
    }
    box.appendChild(p);
  }

  function applyRun(event, runId) {
    var data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      return;
    }
    var stateNode = document.querySelector('[data-run-id="' + runId + '"] .state');
    if (stateNode && typeof data.state === "string" && stateNode.textContent !== data.state) {
      stateNode.textContent = data.state;
    }
    if (typeof data.state === "string") {
      var stopForm = document.querySelector("[data-stop-form]");
      if (stopForm) {
        var done = data.state === "stopped" || data.state === "completed" || data.state === "failed";
        stopForm.hidden = done;
      }
    }
    if (typeof data.pr_url === "string" && data.pr_url) {
      setOutcome("result", "Pull request", data.pr_url);
    } else if (typeof data.ended_reason === "string" && data.ended_reason) {
      var reason = data.ended_reason;
      if (reason.indexOf("Ended") !== 0) {
        reason = "Ended without a pull request — " + reason;
      }
      setOutcome("ended", reason, null);
    }
    // Nomad "complete" is not "no PR". Inventing that copy from allocation
    // state hid real pull requests while the durable result still had the URL
    // (or had it wiped by a later checkpoint). The server sends ended_reason
    // when the durable result settled without one.
    var progress = data.propose_progress;
    if (!progress || !Array.isArray(progress.phases)) {
      return;
    }
    // Same rule as `_phase_position` in app.py: the phase the run is ON, not the count done.
    var done = 0;
    progress.phases.forEach(function (phase, at) {
      if (phase.status === "completed") done += 1;
      if (phase.status === "active" || phase.status === "failed") done = at + 1;
      var li = document.querySelector('#phase-strip [data-phase="' + phase.name + '"]');
      if (!li) return;
      var nextClass = "node node--" + phase.status;
      if (li.className !== nextClass) li.className = nextClass;
      var statusNode = li.querySelector(".phase-status");
      if (statusNode && statusNode.textContent !== phase.status) statusNode.textContent = phase.status;
    });
    // The ring and the count inside it are drawn from these two numbers, so they are set
    // together — a dial that disagrees with its own label is worse than no dial.
    var dial = document.getElementById("phase-strip");
    if (!dial) return;
    dial.style.setProperty("--dial-done", done);
    dial.style.setProperty("--dial-total", progress.phases.length);
    var count = dial.querySelector(".dial-count");
    if (count) count.textContent = done + " of " + progress.phases.length;
  }

  global.BRIEVE_PROPOSE = { applyRun: applyRun };
})(window);
