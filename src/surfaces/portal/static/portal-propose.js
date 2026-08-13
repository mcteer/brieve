// SPDX-License-Identifier: Apache-2.0
// Propose run watcher (047). Same containment rules as portal.js: same-origin SSE only,
// textContent only, no invented phase order.
(function () {
  "use strict";

  var root = document.querySelector("[data-propose-run]");
  if (!root || typeof EventSource === "undefined") {
    return;
  }
  var runId = root.getAttribute("data-propose-run");
  if (!runId) {
    return;
  }

  var source = new EventSource(
    "/propose/runs/" + encodeURIComponent(runId) + "/events"
  );
  var changed = false;

  source.addEventListener("run", function (event) {
    var data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      return;
    }
    var stateNode = document.querySelector('[data-run-id="' + runId + '"] .state');
    if (stateNode && typeof data.state === "string" && stateNode.textContent !== data.state) {
      changed = true;
      stateNode.textContent = data.state;
    }
    var progress = data.propose_progress;
    if (!progress || !Array.isArray(progress.phases)) {
      return;
    }
    progress.phases.forEach(function (phase) {
      var li = document.querySelector(
        '#phase-strip [data-phase="' + phase.name + '"]'
      );
      if (!li) {
        return;
      }
      var nextClass = "phase phase--" + phase.status;
      if (li.className !== nextClass) {
        changed = true;
        li.className = nextClass;
      }
      var statusNode = li.querySelector(".phase-status");
      if (statusNode && statusNode.textContent !== phase.status) {
        statusNode.textContent = phase.status;
      }
      var reasonNode = li.querySelector(".phase-reason");
      if (phase.reason) {
        if (!reasonNode) {
          reasonNode = document.createElement("span");
          reasonNode.className = "phase-reason";
          li.appendChild(reasonNode);
        }
        if (reasonNode.textContent !== phase.reason) {
          reasonNode.textContent = phase.reason;
          changed = true;
        }
      }
    });
  });

  source.addEventListener("closed", function () {
    source.close();
    if (changed) {
      window.location.reload();
    }
  });

  source.onerror = function () {
    source.close();
  };
})();
