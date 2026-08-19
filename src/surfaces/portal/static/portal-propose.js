// SPDX-License-Identifier: Apache-2.0
// Propose run watcher (047). Same-origin SSE only. No reload; reconnect on blips.
(function (global) {
  "use strict";

  var stopped = false;
  var source = null;
  var reconnectTimer = 0;
  var runId = "";

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
    if (stopped || !runId) {
      return;
    }
    if (source) {
      source.close();
      source = null;
    }
    source = new EventSource(
      "/propose/runs/" + encodeURIComponent(runId) + "/events"
    );
    source.addEventListener("run", function (event) {
      window.BRIEVE_PROPOSE.applyRun(event, runId);
    });
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
      scheduleReconnect();
    });
    source.onerror = function () {
      if (source && source.readyState === EventSource.CLOSED) {
        source = null;
        scheduleReconnect();
      }
    };
  }

  function start(id) {
    if (!id || typeof EventSource === "undefined" || !window.BRIEVE_PROPOSE) {
      return;
    }
    stopped = false;
    runId = id;
    connect();
  }

  global.BRIEVE_PROPOSE_WATCH = { start: start };

  var root = document.querySelector("[data-propose-run]");
  if (root) {
    start(root.getAttribute("data-propose-run"));
  }
})(window);
