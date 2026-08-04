// SPDX-License-Identifier: Apache-2.0
//
// ASKING WITHOUT LOSING THE PAGE, and keeping what was already answered (035).
//
// PROGRESSIVE ENHANCEMENT, NOT A CLIENT APP: without this file the form is an ordinary HTML
// form and still works. Nothing here decides anything — the server renders each exchange and
// states which conversation it landed in (ADR-0034); this only places both.
//
// The ONE script permitted to insert markup, and only markup this server rendered over a
// relative path. `tests/conformance/portal/test_containment.py` holds that line.
(function () {
  "use strict";

  var form = document.querySelector("form.ask");
  var outcome = document.getElementById("ask-transcript");
  var note = document.getElementById("ask-status");
  // A half-enhanced form that swallows the submit and cannot deliver is worse than none.
  if (!form || !outcome || !note || !window.fetch) return;

  var button = form.querySelector("button[type=submit]");
  var field = form.querySelector("#question");

  form.addEventListener("submit", function (event) {
    // Let the browser's own `required` handling speak.
    if (!field || !field.value.trim()) {
      return;
    }
    event.preventDefault();

    // The button keeps its size and accessible name; only the label changes.
    var label = button ? button.textContent : "";
    if (button) {
      button.disabled = true;
      button.setAttribute("aria-disabled", "true");
      button.textContent = "Asking…";
    }
    form.setAttribute("aria-busy", "true");
    note.textContent = "Working on your question. This takes a minute or two; you can stay here.";

    // The header is the marker the server branches on; a browser without this file sends none
    // and gets the whole page.
    fetch(form.action, {
      method: "POST",
      headers: { "X-Portal-Fragment": "exchange" },
      body: new FormData(form),
      credentials: "same-origin"
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        // APPEND, never replace — an answer that overwrote the last one is the page this
        // replaced.
        var landing = document.createElement("div");
        landing.innerHTML = html;
        while (landing.firstChild) {
          outcome.appendChild(landing.firstChild);
        }
        note.textContent = "";
        field.value = "";
        // The conversation the server put this exchange in. Until the first answer there is
        // none to post to, so the composer learns it here — otherwise every follow-up starts
        // a new conversation, which is what the served walk-through caught.
        var landed = outcome.querySelectorAll("[data-conversation]");
        var id = landed.length ? landed[landed.length - 1].getAttribute("data-conversation") : "";
        if (id && form.action.indexOf("conversation_id=") === -1) {
          form.action = "/ask?conversation_id=" + encodeURIComponent(id);
        }
        // Focus the NEWEST answer's heading, not a live region: a page of claims read aloud
        // unprompted talks over somebody already reading.
        var answers = outcome.querySelectorAll("#outcome, h2");
        var heading = answers[answers.length - 1];
        if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus(); }
      })
      .catch(function () {
        // The portal's own failure in its own voice, never dressed as an answer or a decline —
        // those are the platform's words. The transcript is left alone: earlier exchanges did
        // happen and are not this failure's to erase.
        note.textContent =
          "The question could not be sent from this page. Nothing was asked and nothing changed.";
      })
      .then(function () {
        form.removeAttribute("aria-busy");
        if (button) {
          button.disabled = false;
          button.removeAttribute("aria-disabled");
          button.textContent = label;
        }
      });
  });
})();
