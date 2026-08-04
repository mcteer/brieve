// SPDX-License-Identifier: Apache-2.0
//
// ASKING WITHOUT LOSING THE PAGE, keeping what was already answered (035).
//
// PROGRESSIVE ENHANCEMENT, NOT A CLIENT APP: without this file the form is an ordinary HTML
// form and still works. Nothing here decides anything — the server renders each exchange and
// states which conversation it landed in (ADR-0034); this only places both, and is the ONE
// script permitted to insert markup this server rendered. See `test_containment.py`.
(function () {
  "use strict";

  // A half-enhanced form that swallows the submit and cannot deliver is worse than none.
  var form = document.querySelector("form.ask");
  var outcome = document.getElementById("ask-transcript");
  var note = document.getElementById("ask-status");
  if (!form || !outcome || !note || !window.fetch) return;
  var button = form.querySelector("button[type=submit]");
  var field = form.querySelector("#question");

  // ENTER SENDS; SHIFT+ENTER writes a new line — what every chat interface does and the
  // opposite of a textarea's default. `requestSubmit` runs the handler below and honours
  // `required`. `isComposing` guards an IME, where Enter chooses a character.
  if (field) {
    field.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        if (form.requestSubmit) form.requestSubmit(); else form.submit();
      }
    });
  }

  form.addEventListener("submit", function (event) {
    if (!field || !field.value.trim()) return;  // The browser's own `required` speaks first.
    event.preventDefault();

    var label = button ? button.textContent : "";  // Size and name kept; only the word changes.
    if (button) {
      button.disabled = true;
      button.setAttribute("aria-disabled", "true");
      button.textContent = "Asking…";
    }
    form.setAttribute("aria-busy", "true");
    note.textContent = "Working on your question. This takes a minute or two; you can stay here.";

    // The header is what the server branches on; without this file none is sent and the whole
    // page comes back.
    fetch(form.action, {
      method: "POST",
      headers: { "X-Portal-Fragment": "exchange" },
      body: new FormData(form),
      credentials: "same-origin"
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        // APPEND, never replace — overwriting the last answer is the page this replaced.
        var landing = document.createElement("div");
        landing.innerHTML = html;
        while (landing.firstChild) outcome.appendChild(landing.firstChild);
        note.textContent = "";
        field.value = "";
        // The conversation the server put this in. Until the first answer there is none to
        // post to, so the composer learns it here — otherwise every follow-up starts a new
        // conversation, which the served walk-through caught.
        var landed = outcome.querySelectorAll("[data-conversation]");
        var id = landed.length ? landed[landed.length - 1].getAttribute("data-conversation") : "";
        if (id && form.action.indexOf("conversation_id=") === -1) {
          form.action = "/ask?conversation_id=" + encodeURIComponent(id);
        }
        // Focus the NEWEST answer's heading, not a live region: a page of claims read aloud
        // unprompted talks over somebody already reading.
        var seen = outcome.querySelectorAll("#outcome, h2");
        var head = seen[seen.length - 1];
        if (head) { head.setAttribute("tabindex", "-1"); head.focus(); }
      })
      .catch(function () {
        // The portal's own failure in its own voice, never dressed as an answer or a decline.
        // The transcript is left alone: earlier exchanges happened.
        note.textContent =
          "The question could not be sent from this page. Nothing was asked and nothing changed.";
      })
      .then(function () {
        form.removeAttribute("aria-busy");
        if (!button) return;
        button.disabled = false;
        button.removeAttribute("aria-disabled");
        button.textContent = label;
      });
  });
})();
