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

  // Whether any run reached a terminal state while this stream was open. Reloading
  // without one is a loop; see the "closed" handler.
  var changed = false;

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
      if (node.textContent !== data.state) {
        changed = true;
      }
      node.textContent = data.state;
    }
  });

  source.addEventListener("closed", function () {
    source.close();
    // Reload ONLY if something actually changed while this stream was open.
    //
    // The first version reloaded unconditionally, which is an infinite loop: on a thread
    // with nothing running the stream closes immediately with reason "settled", the page
    // reloads, opens a new stream, closes again. It made the portal unusable and hammered
    // the API, and no hermetic test could see it because none of them run this file. The
    // accessibility gate found it in about a second, which is the argument for having a
    // lane that drives a real browser.
    //
    // When a run did reach a terminal state, its result is on the server and this page is
    // stale — reloading is the thin-client answer, because the server renders it and this
    // file does not.
    if (changed) {
      window.location.reload();
    }
  });

  source.onerror = function () {
    source.close();
  };
})();
