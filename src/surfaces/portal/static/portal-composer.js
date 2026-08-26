// SPDX-License-Identifier: Apache-2.0
//
// Empty-home Ask/Build slider: sets form.action and the send label.
// Without this file the form posts /ask. Do not put this switch in portal-ask.js.
(function () {
  "use strict";

  var form = document.querySelector("form.ask[data-create-home]");
  if (!form) return;
  var build = form.querySelector('input[name="verb"][value="build"]');
  var ask = form.querySelector('input[name="verb"][value="ask"]');
  var send = form.querySelector("button[type=submit]");
  var field = form.querySelector("#question");
  if (!build || !ask || build.disabled) return;

  function apply() {
    if (build.checked) {
      form.setAttribute("action", "/");
      if (field) field.setAttribute("name", "message");
      if (send && form.getAttribute("aria-busy") !== "true") send.setAttribute("aria-label", "Build");
    } else {
      form.setAttribute("action", "/ask");
      if (field) field.setAttribute("name", "question");
      if (send && form.getAttribute("aria-busy") !== "true") send.setAttribute("aria-label", "Ask");
    }
  }

  ask.addEventListener("change", apply);
  build.addEventListener("change", apply);
  apply();
})();
