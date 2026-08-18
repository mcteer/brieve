// SPDX-License-Identifier: Apache-2.0
//
// COPY CONTROLS on Ask question bubbles and code panels. Progressive enhancement: without
// this script the buttons are inert; with it, each copies plain text via the clipboard API.
//
// Event delegation so exchanges appended by `portal-ask.js` work without a second pass.
// textContent only — this file must never insert markup (portal containment).
(function () {
  "use strict";

  function sourceFor(button) {
    var scope = button.getAttribute("data-copy-scope");
    if (scope === "code") {
      var frame = button.closest(".answer-code-frame");
      return frame ? frame.querySelector("code") : null;
    }
    if (scope === "asked") {
      var bubble = button.closest(".you, .asked");
      return bubble ? bubble.querySelector(".asked-text") : null;
    }
    return null;
  }

  function flash(button, label) {
    // Icon stays; only the accessible name and a brief class change — never replace the SVG.
    var previous = button.getAttribute("aria-label") || "Copy";
    button.setAttribute("aria-label", label);
    if (label === "Copied") button.classList.add("copy-control--done");
    window.setTimeout(function () {
      button.setAttribute("aria-label", previous);
      button.classList.remove("copy-control--done");
    }, 1600);
  }

  function write(text, button) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { flash(button, "Copied"); },
        function () { flash(button, "Copy failed"); }
      );
      return;
    }
    // Fallback for environments without the clipboard API: select a transient field.
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    try {
      flash(button, document.execCommand("copy") ? "Copied" : "Copy failed");
    } catch (err) {
      flash(button, "Copy failed");
    }
    document.body.removeChild(area);
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || !target.closest) return;
    var button = target.closest(".copy-control");
    if (!button) return;
    var source = sourceFor(button);
    if (!source) return;
    var text = (source.textContent || "").replace(/\u00a0/g, " ").trim();
    if (!text) return;
    event.preventDefault();
    write(text, button);
    button.blur();
  });
})();
