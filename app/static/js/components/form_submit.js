// tombol submit jadi "loading" pas form dikirim, biar ga keklik 2x
(function () {
  "use strict";

  document.querySelectorAll("form[method='post']:not([data-no-loading])").forEach(function (formEl) {
    formEl.addEventListener("submit", function (event) {
      // ditunda sebentar: kalau submit-nya dibatalin (misal dialog konfirmasi), tombol ga ikut dikunci
      window.setTimeout(function () {
        if (event.defaultPrevented) return;
        formEl.querySelectorAll("button[type='submit'], input[type='submit']").forEach(function (buttonEl) {
          buttonEl.disabled = true;
          buttonEl.classList.add("is-loading");
          buttonEl.setAttribute("aria-busy", "true");
        });
      }, 0);
    });
  });

  // user pencet "back" di browser: tombol dibalikin normal lagi
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    document.querySelectorAll(".is-loading").forEach(function (buttonEl) {
      buttonEl.disabled = false;
      buttonEl.classList.remove("is-loading");
      buttonEl.removeAttribute("aria-busy");
    });
  });
})();