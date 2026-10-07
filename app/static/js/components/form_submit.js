// tombol submit jadi "loading" pas form dikirim, biar ga keklik 2x
(function () {
  "use strict";

  document.querySelectorAll("form[method='post']:not([data-no-loading])").forEach(function (formEl) {
    formEl.addEventListener("submit", function (event) {
      // ditunda sebentar: kalau submit-nya dibatalin (misal dialog konfirmasi), tombol ga ikut dikunci
      window.setTimeout(function () {
        if (event.defaultPrevented) return;
        // tombol Simpan di toolbar ada di luar form (atribut form="id"), ikut dikunci juga
        const outsideButtonList = formEl.id ? Array.from(document.querySelectorAll("[form='" + formEl.id + "'][type='submit']")) : [];
        Array.from(formEl.querySelectorAll("button[type='submit'], input[type='submit']")).concat(outsideButtonList).forEach(function (buttonEl) {
          buttonEl.disabled = true;
          buttonEl.classList.add("btn-loading");
          buttonEl.setAttribute("aria-busy", "true");
        });
      }, 0);
    });
  });

  // user pencet "back" di browser: tombol dibalikin normal lagi
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    document.querySelectorAll(".btn-loading").forEach(function (buttonEl) {
      buttonEl.disabled = false;
      buttonEl.classList.remove("btn-loading");
      buttonEl.removeAttribute("aria-busy");
    });
  });
})();