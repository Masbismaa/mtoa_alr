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
        const message = "There is no search bar on this screen. Open All Links or another list screen to search.";
        if (window.AlrConfirm) {
          window.AlrConfirm.open({ title: "Search not available", message: message, okLabel: "Got it", isInfo: true });
        } else {
          notify(message, "info");
        }
        return;
      }
      window.AlrSelection.focusQuickSearch();
    });
  });
})();
