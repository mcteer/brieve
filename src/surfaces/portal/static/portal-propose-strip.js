// SPDX-License-Identifier: Apache-2.0
// Build phase strip + outcome (047). textContent only; markup stays the server's.
(function (global) {
  "use strict";

  var terminal = { completed: true, failed: true, stopped: true };

  function setOutcome(htmlClass, text, href) {
    var box = document.querySelector("[data-propose-outcome]");
    if (!box) {
      return;
    }
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
    if (typeof data.pr_url === "string" && data.pr_url) {
      setOutcome("result", "Pull request", data.pr_url);
    } else if (typeof data.ended_reason === "string" && data.ended_reason) {
      var reason = data.ended_reason;
      if (reason.indexOf("Ended") !== 0) {
        reason = "Ended without a pull request — " + reason;
      }
      setOutcome("ended", reason, null);
    } else if (typeof data.state === "string" && terminal[data.state]) {
      setOutcome("ended", "Ended without a pull request.", null);
    }
    var progress = data.propose_progress;
    if (!progress || !Array.isArray(progress.phases)) {
      return;
    }
    progress.phases.forEach(function (phase) {
      var li = document.querySelector('#phase-strip [data-phase="' + phase.name + '"]');
      if (!li) {
        return;
      }
      var nextClass = "phase phase--" + phase.status;
      if (li.className !== nextClass) {
        li.className = nextClass;
      }
      var statusNode = li.querySelector(".phase-status");
      if (statusNode && statusNode.textContent !== phase.status) {
        statusNode.textContent = phase.status;
      }
      if (!phase.reason) {
        return;
      }
      var reasonNode = li.querySelector(".phase-reason");
      if (!reasonNode) {
        reasonNode = document.createElement("span");
        reasonNode.className = "phase-reason";
        li.appendChild(reasonNode);
      }
      if (reasonNode.textContent !== phase.reason) {
        reasonNode.textContent = phase.reason;
      }
    });
  }

  global.BRIEVE_PROPOSE = { applyRun: applyRun };
})(window);
