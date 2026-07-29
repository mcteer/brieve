// SPDX-License-Identifier: Apache-2.0
//
// The portal's ENTIRE client-side surface. A conformance row reads this file and asserts
// what it does not do: no fetch beyond this origin, no model endpoint, no decision logic,
// no storage. That assertion is only possible because this is small enough to read — which
// is the argument for having no build step at all. A bundle can be trusted; a file can be
// checked.
//
// What it does: subscribes to server-sent state changes so a person does not refresh.
// Everything it renders was computed server-side and arrived as text.
(function () {
  "use strict";

  var script = document.currentScript;
  var threadId = script && script.getAttribute("data-thread-id");
  if (!threadId || typeof EventSource === "undefined") {
    // No thread, or a browser without EventSource. The page is already complete and
    // correct without this; it simply will not update on its own.
    return;
  }

  // Same-origin, relative. There is no other URL in this file.
  var source = new EventSource("/threads/" + encodeURIComponent(threadId) + "/events");

  source.addEventListener("run", function (event) {
    var data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      return;
    }
    var node = document.querySelector('[data-run-id="' + data.run_id + '"] .state');
    if (node && typeof data.state === "string") {
      // textContent, never innerHTML: server-rendered state arrives as text and stays text.
      node.textContent = data.state;
    }
  });

  source.addEventListener("closed", function () {
    source.close();
    // A settled run may have produced a result the page has not fetched. Reloading is the
    // thin-client answer: the server renders it, this file does not.
    window.location.reload();
  });

  source.onerror = function () {
    source.close();
  };
})();
