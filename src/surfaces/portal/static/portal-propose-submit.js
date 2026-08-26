// SPDX-License-Identifier: Apache-2.0
//
// STARTING A BUILD WITHOUT LOSING THE PAGE.
//
// PROGRESSIVE ENHANCEMENT, NOT A CLIENT APP: without this file the form is an ordinary HTML
// form and still 303s to the run page. The server renders the same `_propose_run_main.html` a
// GET would wrap (ADR-0034); this places it and decides nothing. It is the Build counterpart
// of `portal-ask.js` — one of two scripts permitted to insert markup this server rendered.
(function () {
  "use strict";

  var form = document.querySelector("form.dock:not(.ask)")
    || document.querySelector("form.ask[data-create-home]");
  var main = document.querySelector(".app-main");
  if (!form || !main || !window.fetch) return;
  var button = form.querySelector("button[type=submit]");
  var note = document.getElementById("ask-status");
  var field = form.querySelector("#message") || form.querySelector("#question");
  var inflight = null;
  var label = button ? button.getAttribute("aria-label") || "" : "";

  form.addEventListener("submit", function (event) {
    var target = form.getAttribute("action") || "";
    if (target !== "/" && target !== "/propose") return;
    if (inflight) {
      event.preventDefault();
      inflight.abort();
      return;
    }
    if (!field || !field.value.trim()) return;
    event.preventDefault();

    inflight = new AbortController();
    if (button) {
      button.setAttribute("aria-label", "Stop");
      button.classList.add("go--stop");
    }
    form.setAttribute("aria-busy", "true");
    // Ask says what it is doing while it waits; Build said nothing, so the only sign it had
    // been pressed was a spinner dot with no sentence beside it.
    if (note) note.textContent = "Starting the build. The phases appear as it goes.";

    fetch(form.action, {
      method: "POST",
      headers: { "X-Portal-Fragment": "run" },
      body: new FormData(form),
      credentials: "same-origin",
      signal: inflight.signal,
    })
      .then(function (r) {
        return r.text().then(function (html) { return { ok: r.ok, html: html }; });
      })
      .then(function (res) {
        var landing = document.createElement("div");
        landing.innerHTML = res.html;
        var section = landing.querySelector("[data-propose-run]");
        if (!section) {
          var note = landing.querySelector(".notice");
          var inner = document.querySelector(".thread .inner");
          if (note && inner) inner.appendChild(note);
          return;
        }
        var runId = section.getAttribute("data-propose-run") || "";
        main.textContent = "";
        main.appendChild(section);
        if (runId && history.replaceState) {
          history.replaceState(null, "", "/propose/runs/" + encodeURIComponent(runId));
        }
        if (window.BRIEVE_PROPOSE_WATCH) window.BRIEVE_PROPOSE_WATCH.start(runId);
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") return;
      })
      .then(function () {
        inflight = null;
        if (note && document.body.contains(note)) note.textContent = "";
        if (!document.body.contains(form)) return;
        form.removeAttribute("aria-busy");
        if (!button) return;
        if (label) button.setAttribute("aria-label", label);
        button.classList.remove("go--stop");
      });
  });
})();
