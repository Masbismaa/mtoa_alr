// panel "Atur tampilan": klik pilihan = langsung dicoba, Simpan = disimpen ke akun,
// ditutup tanpa Simpan = balik ke tampilan sebelumnya, Reset = balik ke default
(function () {
  "use strict";

  const STATUS_CLEAR_MS = 2500;
  const preference = window.AlrUiPreference;
  const panelEl = document.querySelector("[data-customizer]");
  if (!preference || !panelEl) return;

  const statusEl = panelEl.querySelector("[data-customizer-status]");
  const saveButton = panelEl.querySelector("[data-customizer-save]");
  const resetButton = panelEl.querySelector("[data-customizer-reset]");
  const closeButton = panelEl.querySelector('[data-bs-dismiss="offcanvas"]');
  let savedDict = preference.readCurrent();
  let statusTimerId = null;

  function isSameDict(firstDict, secondDict) {
    return JSON.stringify(firstDict) === JSON.stringify(secondDict);
  }

  // tandain pilihan yg lagi kepake
  function syncSelected() {
    const currentDict = preference.readCurrent();
    panelEl.querySelectorAll("[data-pref-option]").forEach(function (optionEl) {
      const prefKey = optionEl.dataset.prefKey;
      let isSelected = false;

      if (prefKey === "accent_color") {
        isSelected = optionEl.dataset.accentKey === currentDict.accent_key;
      } else if (prefKey === "is_compact_view") {
        isSelected = (optionEl.dataset.prefValue === "true") === currentDict.is_compact_view;
      } else {
        isSelected = optionEl.dataset.prefValue === currentDict[prefKey];
      }

      optionEl.setAttribute("aria-checked", String(isSelected));
      optionEl.classList.toggle("is-selected", isSelected);
    });
  }

  function showStatus(message, isError) {
    if (!statusEl) return;
    window.clearTimeout(statusTimerId);
    statusEl.textContent = message;
    statusEl.classList.toggle("is-error", Boolean(isError));
    if (!isError) {
      statusTimerId = window.setTimeout(function () {
        statusEl.textContent = "";
      }, STATUS_CLEAR_MS);
    }
  }

  // server nyimpen warna aksen dalam bentuk hex, UI pake key (blue/pink)
  function findAccentHex(accentKey) {
    const swatchEl = panelEl.querySelector('[data-pref-key="accent_color"][data-accent-key="' + accentKey + '"]');
    return swatchEl ? swatchEl.dataset.prefValue : null;
  }

  function handleOptionClick(optionEl) {
    const prefKey = optionEl.dataset.prefKey;
    const uiDict = {};
    if (prefKey === "accent_color") {
      uiDict.accent_key = optionEl.dataset.accentKey;
    } else if (prefKey === "is_compact_view") {
      uiDict.is_compact_view = optionEl.dataset.prefValue === "true";
    } else {
      uiDict[prefKey] = optionEl.dataset.prefValue;
    }
    preference.apply(uiDict, true);
  }

  function handleReset() {
    preference.apply({
      theme_mode: panelEl.dataset.defaultTheme,
      accent_key: panelEl.dataset.defaultAccentKey,
      is_compact_view: false,
      font_family: panelEl.dataset.defaultFont
    }, true);
    showStatus("Balik ke default, klik Simpan biar kesimpen");
  }

  async function handleSave() {
    const currentDict = preference.readCurrent();
    saveButton.disabled = true;
    showStatus("Menyimpan...");
    const resultDict = await preference.saveToServer({
      theme_mode: currentDict.theme_mode,
      accent_color: findAccentHex(currentDict.accent_key),
      is_compact_view: currentDict.is_compact_view,
      font_family: currentDict.font_family
    });
    saveButton.disabled = false;

    if (resultDict.is_success) {
      savedDict = currentDict;
      showStatus("Tersimpan ✓");
      if (closeButton) closeButton.click();
    } else {
      showStatus(resultDict.message || "Gagal menyimpan", true);
    }
  }

  panelEl.querySelectorAll("[data-pref-option]").forEach(function (optionEl) {
    optionEl.addEventListener("click", function () {
      handleOptionClick(optionEl);
    });
  });

  if (resetButton) resetButton.addEventListener("click", handleReset);
  if (saveButton) saveButton.addEventListener("click", handleSave);

  // panel dibuka: inget tampilan yg lagi kesimpen
  panelEl.addEventListener("show.bs.offcanvas", function () {
    savedDict = preference.readCurrent();
    syncSelected();
  });

  // panel ditutup tanpa Simpan: balikin tampilannya
  panelEl.addEventListener("hidden.bs.offcanvas", function () {
    if (!isSameDict(preference.readCurrent(), savedDict)) {
      preference.apply(savedDict, true);
    }
  });

  // tiap preferensi berubah (dari panel ini atau tombol tema) -> pilihan di panel ikut update
  document.addEventListener("alr:preference-changed", syncSelected);

  syncSelected();
})();
