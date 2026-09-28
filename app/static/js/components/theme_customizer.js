// panel UI Customizer: mode, warna aksen, kerapatan, font. Langsung kepake + auto-save
(function () {
  "use strict";

  const STATUS_CLEAR_MS = 2000;
  const CLOSE_DELAY_MS = 250;
  const preference = window.AlrUiPreference;
  const panelEl = document.querySelector("[data-customizer]");
  const backdropEl = document.querySelector(".customizer-backdrop");
  if (!preference || !panelEl || !backdropEl) return;

  const statusEl = panelEl.querySelector("[data-customizer-status]");
  let lastFocusedEl = null;
  let statusTimerId = null;

  // tandain pilihan yg lagi aktif
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

  function openPanel() {
    lastFocusedEl = document.activeElement;
    syncSelected();
    backdropEl.hidden = false;
    panelEl.inert = false;
    // tunggu 1 frame biar animasi geser kejalan
    window.requestAnimationFrame(function () {
      panelEl.classList.add("is-open");
      backdropEl.classList.add("is-visible");
    });
    const firstOption = panelEl.querySelector("[data-pref-option]");
    if (firstOption) firstOption.focus();
  }

  function closePanel() {
    panelEl.classList.remove("is-open");
    backdropEl.classList.remove("is-visible");
    panelEl.inert = true;
    window.setTimeout(function () {
      backdropEl.hidden = true;
    }, CLOSE_DELAY_MS);
    if (lastFocusedEl) lastFocusedEl.focus();
  }

  async function handleOptionClick(optionEl) {
    const prefKey = optionEl.dataset.prefKey;
    const rawValue = optionEl.dataset.prefValue;
    const uiDict = {};
    const payloadDict = {};

    // UI pake key (blue/yellow), server nyimpen hex
    if (prefKey === "accent_color") {
      uiDict.accent_key = optionEl.dataset.accentKey;
      payloadDict.accent_color = rawValue;
    } else if (prefKey === "is_compact_view") {
      const isCompactView = rawValue === "true";
      uiDict.is_compact_view = isCompactView;
      payloadDict.is_compact_view = isCompactView;
    } else {
      uiDict[prefKey] = rawValue;
      payloadDict[prefKey] = rawValue;
    }

    const previousDict = preference.readCurrent();
    preference.apply(uiDict, true);
    syncSelected();
    showStatus("Menyimpan...");

    const resultDict = await preference.saveToServer(payloadDict);
    if (resultDict.is_success) {
      showStatus("Tersimpan \u2713");
    } else {
      // gagal -> balikin ke pilihan sebelumnya
      preference.apply(previousDict, true);
      syncSelected();
      showStatus(resultDict.message || "Gagal menyimpan", true);
    }
  }

  document.querySelectorAll("[data-customizer-open]").forEach(function (openEl) {
    openEl.addEventListener("click", openPanel);
  });

  document.querySelectorAll("[data-customizer-close]").forEach(function (closeEl) {
    closeEl.addEventListener("click", closePanel);
  });

  panelEl.querySelectorAll("[data-pref-option]").forEach(function (optionEl) {
    optionEl.addEventListener("click", function () {
      handleOptionClick(optionEl);
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && panelEl.classList.contains("is-open")) {
      closePanel();
    }
  });

  // mode diganti dari tombol topbar -> pilihan di panel ikut update
  document.addEventListener("alr:preference-changed", syncSelected);

  syncSelected();
})();