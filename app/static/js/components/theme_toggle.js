// tombol ganti mode terang/gelap (ada di topbar & halaman login)
(function () {
  "use strict";

  const preference = window.AlrUiPreference;
  if (!preference) return;

  const buttonList = document.querySelectorAll("[data-theme-toggle]");

  function syncButtons() {
    const isDark = preference.readCurrent().theme_mode === "dark";
    buttonList.forEach(function (buttonEl) {
      buttonEl.setAttribute("aria-checked", String(isDark));
      buttonEl.title = isDark ? "Ubah ke Light mode" : "Ubah ke Dark mode";
    });
  }

  syncButtons();
  document.addEventListener("alr:preference-changed", syncButtons);

  buttonList.forEach(function (buttonEl) {
    buttonEl.addEventListener("click", async function () {
      if (buttonEl.disabled) return;

      const previousTheme = preference.readCurrent().theme_mode;
      const nextTheme = previousTheme === "dark" ? "light" : "dark";
      buttonList.forEach(function (toggleEl) { toggleEl.disabled = true; });

      // langsung ganti di layar dulu biar kerasa instan, baru simpen ke server
      preference.apply({ theme_mode: nextTheme }, true);
      const [resultDict] = await Promise.all([
        preference.saveToServer({ theme_mode: nextTheme }),
        new Promise(function (resolve) { window.setTimeout(resolve, 560); }),
      ]);

      // gagal simpen -> balikin lagi + kasih tau user
      if (!resultDict.is_success) {
        preference.apply({ theme_mode: previousTheme }, true);
        if (window.AlrFlash) {
          window.AlrFlash.show(resultDict.message || "Gagal menyimpan mode tampilan", "danger");
        }
      }

      buttonList.forEach(function (toggleEl) { toggleEl.disabled = false; });
    });
  });
})();
