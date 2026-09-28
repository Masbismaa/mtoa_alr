// pesan flash: bisa ditutup, yg sukses/info ilang sendiri, bisa dipanggil dari JS lain
(function () {
  "use strict";

  const AUTO_HIDE_MS = 5000;
  const AUTO_HIDE_CATEGORY_LIST = ["success", "info"];
  const FALLBACK_REMOVE_MS = 400;

  function dismiss(flashEl) {
    if (flashEl.classList.contains("is-leaving")) return;
    flashEl.classList.add("is-leaving");
    flashEl.addEventListener("animationend", function () {
      flashEl.remove();
    }, { once: true });
    // jaga-jaga kalau animasi dimatiin (reduced motion)
    window.setTimeout(function () {
      flashEl.remove();
    }, FALLBACK_REMOVE_MS);
  }

  function setup(flashEl) {
    const closeButton = flashEl.querySelector("[data-flash-close]");
    if (closeButton) {
      closeButton.addEventListener("click", function () {
        dismiss(flashEl);
      });
    }

    // pesan error/warning tetep nongol sampe ditutup manual
    const isAutoHide = AUTO_HIDE_CATEGORY_LIST.some(function (category) {
      return flashEl.classList.contains("flash-" + category);
    });
    if (isAutoHide) {
      window.setTimeout(function () {
        dismiss(flashEl);
      }, AUTO_HIDE_MS);
    }
  }

  // bikin pesan baru dari JS. Pake textContent biar aman dari XSS
  function show(message, category) {
    const listEl = document.querySelector("[data-flash-list]");
    if (!listEl) return;

    const flashEl = document.createElement("div");
    flashEl.className = "flash flash-" + (category || "info");
    flashEl.setAttribute("role", "alert");
    flashEl.dataset.flash = "";

    const textEl = document.createElement("span");
    textEl.className = "flash-text";
    textEl.textContent = message;

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "flash-close";
    closeButton.dataset.flashClose = "";
    closeButton.setAttribute("aria-label", "Tutup pesan");
    closeButton.textContent = "\u00d7";

    flashEl.append(textEl, closeButton);
    listEl.append(flashEl);
    setup(flashEl);
  }

  document.querySelectorAll("[data-flash]").forEach(setup);
  window.AlrFlash = { show: show };
})();   