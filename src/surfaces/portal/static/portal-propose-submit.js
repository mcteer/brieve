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

  var form = document.querySelector("form.dock:not(.ask)");
  var main = document.querySelector(".app-main");
  if (!form || !main || !window.fetch) return;
  var button = form.querySelector("button[type=submit]");
  var field = form.querySelector("#message");
  var inflight = null;
  var label = button ? button.textContent : "";

  form.addEventListener("submit", function (event) {
    if (inflight) {
      event.preventDefault();
      inflight.abort();
      return;
    }
    if (!field || !field.value.trim()) return;
    event.preventDefault();

    inflight = new AbortController();
    if (button) {
      button.textContent = "Stop";
      button.classList.add("go--stop");
    }
    form.setAttribute("aria-busy", "true");

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
        if (!document.body.contains(form)) return;
        form.removeAttribute("aria-busy");
        if (!button) return;
        button.textContent = label;
        button.classList.remove("go--stop");
      });
  });
})();
