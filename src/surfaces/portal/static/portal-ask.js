// SPDX-License-Identifier: Apache-2.0
//
// ASKING WITHOUT LOSING THE PAGE, keeping what was already answered (035).
//
// PROGRESSIVE ENHANCEMENT, NOT A CLIENT APP: without this file the form is an ordinary HTML
// form and still works. The server renders each exchange and states which conversation it
// landed in (ADR-0034); this places both and decides nothing. It is the ONE script permitted
// to insert markup this server rendered — see `test_containment.py`.
(function () {
  "use strict";

  // A half-enhanced form that swallows the submit and cannot deliver is worse than none.
  var form = document.querySelector("form.ask");
  var outcome = document.getElementById("ask-transcript");
  var note = document.getElementById("ask-status");
  if (!form || !outcome || !note || !window.fetch) return;
  var button = form.querySelector("button[type=submit]");
  var field = form.querySelector("#question");
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
    note.textContent = "Working on your question. This takes a minute or two; you can stay here.";

    fetch(form.action, {
      method: "POST",
      headers: { "X-Portal-Fragment": "exchange" },
      body: new FormData(form),
      credentials: "same-origin",
      signal: inflight.signal,
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var landing = document.createElement("div");
        landing.innerHTML = html;
        while (landing.firstChild) outcome.appendChild(landing.firstChild);
        note.textContent = "";
        field.value = "";
        var landed = outcome.querySelectorAll("[data-conversation]");
        var id = landed.length ? landed[landed.length - 1].getAttribute("data-conversation") : "";
        if (id && form.action.indexOf("conversation_id=") === -1) {
          form.action = "/ask?conversation_id=" + encodeURIComponent(id);
          if (history.replaceState) history.replaceState(null, "", "/ask/" + encodeURIComponent(id));
        }
        var seen = outcome.querySelectorAll(".exchange");
        var last = seen[seen.length - 1];
        if (last) { last.setAttribute("tabindex", "-1"); last.focus(); }
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") {
          note.textContent = "Stopped waiting. The question was already sent.";
          return;
        }
        note.textContent =
          "The question could not be sent from this page. Nothing was asked and nothing changed.";
      })
      .then(function () {
        inflight = null;
        form.removeAttribute("aria-busy");
        if (!button) return;
        button.textContent = label;
        button.classList.remove("go--stop");
      });
  });
})();
