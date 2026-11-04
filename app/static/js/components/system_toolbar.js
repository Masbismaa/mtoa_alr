// toolbar sistem: tombol Find.
(function () {
  "use strict";

  function notify(text, type) {
    if (window.AlrStatusBar) window.AlrStatusBar.show(text, type);
  }

  // Find = fokus ke Cari cepat di Kriteria Pencarian (selection_panel.js)
  document.querySelectorAll("[data-system-find]").forEach(function (buttonEl) {
    buttonEl.addEventListener("click", function () {
      if (!document.querySelector("[data-selection-quick]") || !window.AlrSelection) {
        notify("There is nothing to search on this screen", "info");
        return;
      }
      window.AlrSelection.focusQuickSearch();
    });
  });
})();
