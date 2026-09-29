// pesan flash (alert Tabler): bisa ditutup, yg sukses/info ilang sendiri, bisa dipanggil dari JS lain
(function () {
  "use strict";

  const AUTO_HIDE_MS = 5000;
  const AUTO_HIDE_CATEGORY_LIST = ["success", "info"];
  const REMOVE_DELAY_MS = 250;

  function dismiss(flashEl) {
    if (flashEl.classList.contains("is-leaving")) return;
    flashEl.classList.add("is-leaving");
    // nunggu animasi keluar selesai baru dihapus
    window.setTimeout(function () {
      flashEl.remove();
    }, REMOVE_DELAY_MS);
  }

  function setup(flashEl) {
    const closeButton = flashEl.querySelector("[data-flash-close]");
    if (closeButton) {
      closeButton.addEventListener("click", function () {
        dismiss(flashEl);
      });
    }

    // pesan error/warning tetep nongol sampe ditutup manual
    if (AUTO_HIDE_CATEGORY_LIST.includes(flashEl.dataset.flashCategory)) {
      window.setTimeout(function () {
        dismiss(flashEl);
      }, AUTO_HIDE_MS);
    }
  }

  // bikin pesan baru dari JS. Pake textContent biar aman dari XSS
  function show(message, category) {
    const listEl = document.querySelector("[data-flash-list]");
    if (!listEl) return;
    const flashCategory = category || "info";

    const flashEl = document.createElement("div");
    flashEl.className = "alert alert-" + flashCategory + " alert-dismissible flash-item";
    flashEl.setAttribute("role", "alert");
    flashEl.dataset.flash = "";
    flashEl.dataset.flashCategory = flashCategory;

    const textEl = document.createElement("div");
    textEl.className = "flash-text";
    textEl.textContent = message;

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "btn-close";
    closeButton.dataset.flashClose = "";
    closeButton.setAttribute("aria-label", "Tutup pesan");

    flashEl.append(textEl, closeButton);
    listEl.append(flashEl);
    setup(flashEl);
  }

  document.querySelectorAll("[data-flash]").forEach(setup);
  window.AlrFlash = { show: show };
})();