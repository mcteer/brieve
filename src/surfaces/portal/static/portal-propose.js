// SPDX-License-Identifier: Apache-2.0
// Propose run watcher (047). Same containment rules as portal.js: same-origin SSE only,
// textContent only, no invented phase order.
//
// **No reload, and no giving up.** The stream updates state, phases, and the outcome in
// place. Closing on the first error (or on the 5-minute budget) left the strip frozen
// until a person refreshed — the opposite of why the stream exists.
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

  var terminal = { completed: true, failed: true, stopped: true };
  var stopped = false;
  var source = null;
  var reconnectTimer = 0;

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

  function applyRun(event) {
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
      var li = document.querySelector(
        '#phase-strip [data-phase="' + phase.name + '"]'
      );
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
      if (phase.reason) {
        var reasonNode = li.querySelector(".phase-reason");
        if (!reasonNode) {
          reasonNode = document.createElement("span");
          reasonNode.className = "phase-reason";
          li.appendChild(reasonNode);
        }
        if (reasonNode.textContent !== phase.reason) {
          reasonNode.textContent = phase.reason;
        }
      }
    });
  }

  function scheduleReconnect() {
    if (stopped || reconnectTimer) {
      return;
    }
    reconnectTimer = window.setTimeout(function () {
      reconnectTimer = 0;
      connect();
    }, 1000);
  }

  function connect() {
    if (stopped) {
      return;
    }
    if (source) {
      source.close();
      source = null;
    }
    source = new EventSource(
      "/propose/runs/" + encodeURIComponent(runId) + "/events"
    );
    source.addEventListener("run", applyRun);
    source.addEventListener("closed", function (event) {
      var reason = "";
      try {
        reason = String(JSON.parse(event.data).reason || "");
      } catch (err) {
        reason = "";
      }
      if (source) {
        source.close();
        source = null;
      }
      if (reason === "settled" || reason === "refused") {
        stopped = true;
        return;
      }
      // `budget` is the stream's own bound — the comment in events.py says the browser
      // must reconnect. Anything else is a blip.
      scheduleReconnect();
    });
    source.onerror = function () {
      // Do not close. EventSource reconnects while CONNECTING/OPEN; closing here is
      // what froze the Build strip on the first handshake error.
      if (source && source.readyState === EventSource.CLOSED) {
        source = null;
        scheduleReconnect();
      }
    };
  }

  connect();
})();
