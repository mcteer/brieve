// SPDX-License-Identifier: Apache-2.0
//
// Filters already-rendered history rows by visible text. No API call.
// Absent this script, the full list stays and the search field does not pretend to filter.
(function () {
  "use strict";

  var field = document.querySelector("[data-history-search]");
  var rows = document.querySelectorAll("[data-history-row]");
  var empty = document.querySelector("[data-history-empty]");
  if (!field || !rows.length) return;

  function visibleText(node) {
    return (node.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  field.addEventListener("input", function () {
    var needle = (field.value || "").trim().toLowerCase();
    var shown = 0;
    for (var i = 0; i < rows.length; i += 1) {
      var row = rows[i];
      var match = !needle || visibleText(row).indexOf(needle) !== -1;
      row.closest("li").hidden = !match;
      if (match) shown += 1;
    }
    if (empty) empty.hidden = shown !== 0;
  });
})();
