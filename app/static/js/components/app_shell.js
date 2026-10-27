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

  // TOMBOL FUNGSI ALA SAP GUI: tombol yg punya data-fkey (F3 Back, F8 Execute, Ctrl+S Save, ...) dipencet lewat keyboard.
  // Tombol yg disabled / lagi ga keliatan dicuekin. Ctrl+S & F-key bawaan browser (cari, simpan halaman) diganti
  function readKeyName(event) {
    if (!/^F([1-9]|1[0-2])$/.test(event.key) && !(event.ctrlKey && event.key.toLowerCase() === "s")) return "";
    const keyName = event.key.length === 1 ? event.key.toUpperCase() : event.key;
    return (event.ctrlKey ? "Ctrl+" : "") + (event.shiftKey ? "Shift+" : "") + keyName;
  }

  document.addEventListener("keydown", function (event) {
    if (event.altKey || event.metaKey || event.repeat || document.querySelector("dialog[open]")) return;
    const keyName = readKeyName(event);
    if (!keyName) return;
    const targetEl = Array.from(document.querySelectorAll('[data-fkey="' + keyName + '"]')).find(function (el) {
      return !el.disabled && el.getAttribute("aria-disabled") !== "true" && el.getClientRects().length > 0;
    });
    // Ctrl+S di layar tanpa Save: jangan munculin "Save page" bawaan browser (kayak SAP, ga ngapa-ngapain)
    if (targetEl || keyName === "Ctrl+S") event.preventDefault();
    if (targetEl) targetEl.click();
  });

  // JAM DI STATUS BAR (jam komputer user, diperbarui tiap 30 detik)
  const clockEl = document.querySelector("[data-status-clock]");
  function updateClock() {
    clockEl.textContent = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }
  if (clockEl) {
    updateClock();
    window.setInterval(updateClock, 30000);
  }

  // BANTUAN
  const helpDialogEl = setupDialog(document.getElementById("help_dialog"), "[data-help-close]");
  document.querySelectorAll("[data-help-open]").forEach(function (buttonEl) {
    buttonEl.addEventListener("click", function () {
      if (helpDialogEl) helpDialogEl.showModal();
    });
  });

  // STATUS BAR
  // Simpan folder sidebar yg dibuka di tab ini. Cabang halaman aktif selalu dibuka saat pindah halaman.
  const sidebarBranchList = document.querySelectorAll("#app_sidebar details[data-sidebar-branch]");
  let sidebarState = {};
  try {
    const stored = JSON.parse(sessionStorage.getItem("alr_sidebar_branches") || "{}");
    if (stored && typeof stored === "object" && !Array.isArray(stored)) sidebarState = stored;
  } catch (error) {
    // Sidebar tetap bisa dibuka tanpa penyimpanan browser.
  }
  sidebarBranchList.forEach(function (branchEl) {
    const key = branchEl.dataset.sidebarBranch;
    if (branchEl.dataset.sidebarActive !== "true" && typeof sidebarState[key] === "boolean") {
      branchEl.open = sidebarState[key];
    }
    branchEl.addEventListener("toggle", function () {
      sidebarState[key] = branchEl.open;
      try { sessionStorage.setItem("alr_sidebar_branches", JSON.stringify(sidebarState)); } catch (error) {}
    });
    branchEl.querySelector("summary").addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        event.preventDefault();
        branchEl.open = event.key === "ArrowRight";
      }
    });
  });

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
    return isNaN(date) ? "" : date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
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

  // tombol di status bar + menu System > Message history
  document.querySelectorAll("[data-status-open]").forEach(function (buttonEl) {
    buttonEl.addEventListener("click", openHistory);
  });

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
