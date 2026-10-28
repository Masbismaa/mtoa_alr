// toolbar sistem: tombol Find.
(function () {
  "use strict";

  function notify(text, type) {
    if (window.AlrStatusBar) window.AlrStatusBar.show(text, type);
  }

  // Find = sama kayak tekan "/" (fokus ke Cari cepat di Kriteria Pencarian, lihat selection_panel.js)
  document.querySelectorAll("[data-system-find]").forEach(function (buttonEl) {
    buttonEl.addEventListener("click", function () {
      if (!document.querySelector("[data-selection-quick]")) {
        notify("There is nothing to search on this screen", "info");
        return;
      }
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true }));
    });
  });
})();
