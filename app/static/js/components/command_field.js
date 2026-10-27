// toolbar sistem: command field (kode menu), Find.
// kode: "LL" / "/nLL" = buka di tab ini, "/oLL" = buka di tab baru, "/n" = Home. Ctrl+/ = fokus ke command field
(function () {
  "use strict";

  const formEl = document.querySelector("[data-command-form]");
  if (!formEl) return;
  const inputEl = formEl.querySelector("[data-command-input]");
  const transactionList = JSON.parse(formEl.querySelector("[data-transaction-map]").textContent);
  const HOME_URL = formEl.dataset.homeUrl;

  function notify(text, type) {
    if (window.AlrStatusBar) window.AlrStatusBar.show(text, type);
  }

  // return {url, isNewTab} atau null kalau kodenya ga dikenal
  function resolveCommand(rawText) {
    let code = rawText.trim().toUpperCase();
    let isNewTab = false;
    if (code.startsWith("/O")) {
      isNewTab = true;
      code = code.slice(2);
    } else if (code.startsWith("/N")) {
      code = code.slice(2);
    }
    code = code.trim();
    if (!code) return { url: HOME_URL, isNewTab: isNewTab };
    const transaction = transactionList.find(function (item) { return item.code === code; });
    return transaction ? { url: transaction.url, isNewTab: isNewTab } : null;
  }

  formEl.addEventListener("submit", function (event) {
    event.preventDefault();
    const rawText = inputEl.value;
    if (!rawText.trim()) return;
    const target = resolveCommand(rawText);
    if (!target) {
      notify("Menu code " + rawText.trim().toUpperCase() + " not found", "danger");
      inputEl.select();
      return;
    }
    inputEl.value = "";
    if (target.isNewTab) {
      window.open(target.url, "_blank", "noopener");
    } else {
      window.location.assign(target.url);
    }
  });

  // Enter selalu jalanin kodenya, walau daftar saran (datalist) lagi kebuka (bawaannya Enter cuma nutup daftar)
  inputEl.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      formEl.requestSubmit();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.ctrlKey && event.key === "/") {
      event.preventDefault();
      inputEl.focus();
      inputEl.select();
    }
  });

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
