// SPDX-License-Identifier: Apache-2.0
//
// ASKING WITHOUT LOSING THE PAGE, and keeping what was already answered (035).
//
// PROGRESSIVE ENHANCEMENT, NOT A CLIENT APP: without this file the form is an ordinary HTML
// form and still works. Nothing here decides anything — the server renders each exchange
// exactly as it does for a full page load (ADR-0034) and this only chooses where to put it.
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

    // The button keeps its size and accessible name; only the label changes — a spinner would
    // drop the target under 24x24 and remove what focus was sitting on.
    var label = button ? button.textContent : "";
    if (button) {
      button.disabled = true;
      button.setAttribute("aria-disabled", "true");
      button.textContent = "Asking…";
    }
    form.setAttribute("aria-busy", "true");
    note.textContent =
      "Working on your question. This usually takes a minute or two, and you can stay here.";

    fetch(form.action, {
      method: "POST",
      // The marker the server branches on; a browser without this file sends none and gets the
      // whole page.
      headers: { "X-Portal-Fragment": "exchange" },
      body: new FormData(form),
      credentials: "same-origin"
    })
      .then(function (response) {
        return response.text();
      })
      .then(function (html) {
        // APPEND, never replace. The transcript is the feature: an answer that overwrote the
        // last one is the single-shot page this replaced.
        var landing = document.createElement("div");
        landing.innerHTML = html;
        while (landing.firstChild) {
          outcome.appendChild(landing.firstChild);
        }
        note.textContent = "";
        field.value = "";
        // Focus the NEWEST answer's heading rather than announcing it into a live region: a
        // page of claims read aloud unprompted talks over somebody already reading.
        var answers = outcome.querySelectorAll("#outcome, h2");
        var heading = answers[answers.length - 1];
        if (heading) {
          heading.setAttribute("tabindex", "-1");
          heading.focus();
        }
      })
      .catch(function () {
        // The portal's own failure in the portal's own voice, never dressed as an answer or a
        // decline. Those are the platform's words and this is not the platform. The transcript
        // is left alone — earlier exchanges did happen and are not this failure's to erase.
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
