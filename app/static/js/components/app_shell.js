// shell aplikasi ala SAP GUI: dialog Bantuan dari toolbar + status bar bawah (pesan terakhir & riwayatnya).
// komponen lain bisa ngirim pesan ke status bar lewat window.AlrStatusBar.show(teks, jenis, isKept)
(function () {
  "use strict";

  const HISTORY_KEY = "alr_status_history";
  const MAX_HISTORY_COUNT = 20;
  // jenis pesan -> ikon yg dipake (danger pake ikon peringatan, warnanya merah dari CSS)
  const ICON_BY_TYPE_DICT = { success: "success", info: "info", warning: "warning", danger: "warning" };

  // dialog bisa ditutup pake tombol, Esc (bawaan <dialog>), atau klik area gelap
  function setupDialog(dialogEl, closeSelector) {
    if (!dialogEl || typeof dialogEl.showModal !== "function") return null;
    dialogEl.querySelector(closeSelector).addEventListener("click", function () { dialogEl.close(); });
    dialogEl.addEventListener("click", function (event) {
      if (event.target === dialogEl) dialogEl.close();
    });
    return dialogEl;
  }

  // BANTUAN
  const helpDialogEl = setupDialog(document.getElementById("help_dialog"), "[data-help-close]");
  document.querySelectorAll("[data-help-open]").forEach(function (buttonEl) {
    buttonEl.addEventListener("click", function () {
      if (helpDialogEl) helpDialogEl.showModal();
    });
  });

  // STATUS BAR
  const barEl = document.querySelector("[data-status-bar]");
  if (!barEl) return;
  const textEl = barEl.querySelector("[data-status-text]");
  const statusDialogEl = setupDialog(document.getElementById("status_dialog"), "[data-status-close]");

  // riwayat disimpen di sessionStorage (ilang pas tab ditutup). Diblok browser -> cuma pesan terakhir
  function readHistory() {
    try {
      const historyList = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]");
      return Array.isArray(historyList) ? historyList : [];
    } catch (error) {
      return [];
    }
  }

  function writeHistory(historyList) {
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(historyList.slice(-MAX_HISTORY_COUNT)));
    } catch (error) {
      // sessionStorage diblok, cuekin aja
    }
  }

  function render(entryDict) {
    const iconKey = ICON_BY_TYPE_DICT[entryDict.type] || "info";
    textEl.textContent = entryDict.text;
    barEl.dataset.statusType = entryDict.type;
    barEl.querySelectorAll("[data-status-icon]").forEach(function (iconEl) {
      iconEl.hidden = iconEl.dataset.statusIcon !== iconKey;
    });
  }

  // tampilin pesan di status bar + catat ke riwayat. isKept false = cuma tampil (buat pesan yg sering, misal simpan layout)
  function show(text, type, isKept) {
    const entryDict = { text: String(text), type: type || "info", time: new Date().toISOString() };
    render(entryDict);
    if (isKept !== false) writeHistory(readHistory().concat([entryDict]));
  }

  function formatTime(isoText) {
    const date = new Date(isoText);
    return isNaN(date) ? "" : date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
  }

  // riwayat pesan, terbaru di atas. Pake textContent biar aman dari XSS
  function openHistory() {
    if (!statusDialogEl) return;
    const historyList = readHistory().slice().reverse();
    const listEl = statusDialogEl.querySelector("[data-status-list]");
    listEl.replaceChildren();
    historyList.forEach(function (entryDict) {
      const itemEl = document.createElement("li");
      itemEl.className = "status-history-item is-" + entryDict.type;
      const timeEl = document.createElement("span");
      timeEl.className = "status-history-time";
      timeEl.textContent = formatTime(entryDict.time);
      const messageEl = document.createElement("span");
      messageEl.textContent = entryDict.text;
      itemEl.append(timeEl, messageEl);
      listEl.append(itemEl);
    });
    statusDialogEl.querySelector("[data-status-empty]").hidden = historyList.length > 0;
    statusDialogEl.showModal();
  }

  barEl.querySelector("[data-status-open]").addEventListener("click", openHistory);

  // pesan flash dari server (yg sukses ilang sendiri 5 detik) tetep nempel di status bar.
  // ga ada pesan baru -> tampilin pesan terakhir dari riwayat
  const flashList = document.querySelectorAll("[data-flash]");
  if (flashList.length) {
    flashList.forEach(function (flashEl) {
      show(flashEl.querySelector(".flash-text").textContent.trim(), flashEl.dataset.flashCategory);
    });
  } else {
    const lastEntryDict = readHistory().slice(-1)[0];
    if (lastEntryDict) render(lastEntryDict);
  }

  // pesan flash yg dibikin dari JS juga ikut ke status bar
  if (window.AlrFlash) {
    const showFlash = window.AlrFlash.show;
    window.AlrFlash.show = function (message, category) {
      showFlash(message, category);
      show(message, category);
    };
  }

  window.AlrStatusBar = { show: show };
})();
