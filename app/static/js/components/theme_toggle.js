// tombol ganti mode terang/gelap (ada di topbar & halaman login)
(function () {
  "use strict";

  const preference = window.AlrUiPreference;
  if (!preference) return;

  document.querySelectorAll("[data-theme-toggle]").forEach(function (buttonEl) {
    buttonEl.addEventListener("click", async function () {
      if (buttonEl.disabled) return;

      const previousTheme = preference.readCurrent().theme_mode;
      const nextTheme = previousTheme === "dark" ? "light" : "dark";
      const switchingClass = `is-theme-switching-to-${nextTheme}`;

      buttonEl.disabled = true;
      buttonEl.classList.remove("is-theme-switching-to-dark", "is-theme-switching-to-light");
      buttonEl.classList.add("is-theme-switching", switchingClass);
      buttonEl.setAttribute("aria-label", `Ubah ke mode ${nextTheme === "dark" ? "gelap" : "terang"}`);

      // langsung ganti di layar dulu biar kerasa instan, baru simpen ke server
      preference.apply({ theme_mode: nextTheme }, true);
      const resultDict = await preference.saveToServer({ theme_mode: nextTheme });

      // gagal simpen -> balikin lagi + kasih tau user
      if (!resultDict.is_success) {
        preference.apply({ theme_mode: previousTheme }, true);
        if (window.AlrFlash) {
          window.AlrFlash.show(resultDict.message || "Gagal menyimpan mode tampilan", "danger");
        }
      }

      window.setTimeout(function () {
        buttonEl.classList.remove("is-theme-switching", switchingClass);
        buttonEl.disabled = false;
      }, 560);
    });
  });
})();
