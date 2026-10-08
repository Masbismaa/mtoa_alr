// baris aktif di tabel ALV (layar lebar): klik baris / Tab ke tabel -> baris jadi aktif.
// panah atas/bawah pindah, Home/End ke ujung, Enter atau double-click buka (data-row-url),
// klik kanan / Shift+F10 / tombol Menu -> menu baris: buka, salin nilai sel, salin baris
(function () {
  "use strict";

  const INTERACTIVE_SELECTOR = "a, button, input, select, textarea, label, [data-bs-toggle]";
  let menuEl = null;
  let menuRowEl = null;

  function notify(text, type) {
    if (window.AlrStatusBar) window.AlrStatusBar.show(text, type, false);
  }

  // salin ke clipboard, browser lama / tanpa izin pake cara textarea
  function copyText(text) {
    function fallback() {
      const textareaEl = document.createElement("textarea");
      textareaEl.value = text;
      textareaEl.setAttribute("readonly", "");
      textareaEl.style.position = "fixed";
      textareaEl.style.opacity = "0";
      document.body.append(textareaEl);
      textareaEl.select();
      const isCopied = document.execCommand("copy");
      textareaEl.remove();
      return isCopied ? Promise.resolve() : Promise.reject(new Error("copy gagal"));
    }
    const copyPromise = navigator.clipboard && window.isSecureContext ? navigator.clipboard.writeText(text).catch(fallback) : fallback();
    return copyPromise.then(
      function () { notify("Disalin: " + (text.length > 60 ? text.slice(0, 60) + "…" : text), "success"); },
      function () { notify("Gagal menyalin, browser ga ngizinin", "danger"); }
    );
  }

  // isi sel buat disalin: nilai tombol copy (URL lengkap) > tooltip (teks lengkap yg kepotong) > teks yg keliatan
  function readCellValue(cellEl) {
    const copyEl = cellEl.querySelector("[data-copy-text]");
    if (copyEl) return copyEl.dataset.copyText;
    const titledEl = cellEl.querySelector("[title]");
    if (titledEl && titledEl.title) return titledEl.title.trim();
    if (cellEl.title) return cellEl.title.trim();
    return cellEl.innerText.replace(/\s+/g, " ").trim();
  }

  function readColumnLabel(tableEl, cellEl) {
    const labelEl = tableEl.querySelector('thead tr:first-child th[data-column="' + cellEl.dataset.column + '"] .col-sort-label');
    return labelEl ? labelEl.textContent.trim() : "kolom";
  }

  function closeMenu(isRefocus) {
    if (!menuEl || menuEl.hidden) return;
    menuEl.hidden = true;
    if (isRefocus && menuRowEl) menuRowEl.focus();
    menuRowEl = null;
  }

  function addMenuItem(label, onSelect) {
    const itemEl = document.createElement("button");
    itemEl.type = "button";
    itemEl.className = "dropdown-item";
    itemEl.setAttribute("role", "menuitem");
    itemEl.textContent = label;
    itemEl.addEventListener("click", function () {
      closeMenu(true);
      onSelect();
    });
    menuEl.append(itemEl);
  }

  // menu baris: dibikin ulang tiap dibuka, isinya ngikut baris & sel yg diklik
  function openMenu(tableEl, rowEl, cellEl, positionX, positionY) {
    if (!menuEl) {
      menuEl = document.createElement("div");
      menuEl.className = "dropdown-menu row-context-menu show";
      menuEl.setAttribute("role", "menu");
      menuEl.setAttribute("aria-label", "Menu baris");
      menuEl.hidden = true;
      menuEl.addEventListener("keydown", function (event) {
        const itemList = Array.from(menuEl.querySelectorAll("[role=menuitem]"));
        const currentIndex = itemList.indexOf(document.activeElement);
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          const step = event.key === "ArrowDown" ? 1 : -1;
          itemList[(currentIndex + step + itemList.length) % itemList.length].focus();
        } else if (event.key === "Escape" || event.key === "Tab") {
          event.preventDefault();
          closeMenu(true);
        }
      });
      document.body.append(menuEl);
    }
    menuEl.replaceChildren();
    menuRowEl = rowEl;
    if (rowEl.dataset.rowUrl) {
      addMenuItem("Buka", function () { window.location.href = rowEl.dataset.rowUrl; });
    }
    if (cellEl && cellEl.dataset.column) {
      addMenuItem("Salin " + readColumnLabel(tableEl, cellEl), function () { copyText(readCellValue(cellEl)); });
    }
    addMenuItem("Salin baris", function () {
      const visibleCellList = Array.from(rowEl.cells).filter(function (rowCellEl) { return rowCellEl.dataset.column && !rowCellEl.hidden; });
      copyText(visibleCellList.map(readCellValue).join("\t"));
    });
    menuEl.hidden = false;
    // jangan sampe menunya keluar layar
    const menuRect = menuEl.getBoundingClientRect();
    menuEl.style.left = Math.min(positionX, window.innerWidth - menuRect.width - 8) + "px";
    menuEl.style.top = Math.min(positionY, window.innerHeight - menuRect.height - 8) + "px";
    menuEl.querySelector("[role=menuitem]").focus();
  }

  function setupTable(tableEl) {
    const bodyEl = tableEl.tBodies[0];
    const rowList = bodyEl ? Array.from(bodyEl.rows) : [];
    if (!rowList.length) return;
    let activeIndex = -1;
    bodyEl.setAttribute("aria-label", "Baris data, pakai panah atas/bawah");

    // cuma baris aktif yg bisa di-Tab (roving tabindex), jadi Tab ga mampir ke tiap baris
    rowList.forEach(function (rowEl, index) {
      rowEl.tabIndex = index === 0 ? 0 : -1;
    });

    function activate(index, isFocus) {
      const nextIndex = Math.max(0, Math.min(rowList.length - 1, index));
      if (activeIndex >= 0 && activeIndex !== nextIndex) {
        rowList[activeIndex].classList.remove("is-active");
        rowList[activeIndex].tabIndex = -1;
      }
      rowList[nextIndex].classList.add("is-active");
      rowList[nextIndex].tabIndex = 0;
      activeIndex = nextIndex;
      if (isFocus) rowList[nextIndex].focus();
    }

    function openRow(rowEl) {
      if (rowEl.dataset.rowUrl) window.location.href = rowEl.dataset.rowUrl;
    }

    function openMenuAtRow(rowEl) {
      const firstCellEl = Array.from(rowEl.cells).find(function (cellEl) { return cellEl.dataset.column && !cellEl.hidden; });
      const rowRect = rowEl.getBoundingClientRect();
      openMenu(tableEl, rowEl, firstCellEl, rowRect.left + 24, rowRect.bottom);
    }

    rowList.forEach(function (rowEl, index) {
      // klik di link/tombol tetep jalan normal, barisnya cuma ditandain aktif
      rowEl.addEventListener("click", function (event) {
        activate(index, !event.target.closest(INTERACTIVE_SELECTOR));
      });
      rowEl.addEventListener("focus", function () {
        activate(index, false);
      });
      rowEl.addEventListener("dblclick", function (event) {
        if (event.target.closest(INTERACTIVE_SELECTOR)) return;
        openRow(rowEl);
      });
      rowEl.addEventListener("keydown", function (event) {
        // lagi fokus di link/tombol di dalem baris: biarin
        if (event.target !== rowEl) return;
        const isMenuKey = event.key === "ContextMenu" || (event.shiftKey && event.key === "F10");
        if (event.key === "ArrowDown") activate(index + 1, true);
        else if (event.key === "ArrowUp") activate(index - 1, true);
        else if (event.key === "Home") activate(0, true);
        else if (event.key === "End") activate(rowList.length - 1, true);
        else if (event.key === "Enter") openRow(rowEl);
        else if (isMenuKey) openMenuAtRow(rowEl);
        else return;
        event.preventDefault();
      });
      // klik kanan di link: menu bawaan browser (buka di tab baru, salin link)
      rowEl.addEventListener("contextmenu", function (event) {
        if (event.target.closest(INTERACTIVE_SELECTOR)) return;
        event.preventDefault();
        activate(index, true);
        openMenu(tableEl, rowEl, event.target.closest("td"), event.clientX, event.clientY);
      });
    });
  }

  document.addEventListener("click", function (event) {
    if (menuEl && !menuEl.hidden && !menuEl.contains(event.target)) closeMenu(false);
  });
  window.addEventListener("scroll", function () { closeMenu(false); }, true);
  window.addEventListener("resize", function () { closeMenu(false); });

  // HP: tabel jadi kartu, baris aktif ga dipake
  if (window.matchMedia("(min-width: 768px)").matches) {
    document.querySelectorAll("table.data-table").forEach(function (tableEl) {
      // tabel link React (data-entry-table) udah ngurus baris aktif & menunya sendiri
      if (!tableEl.closest("[data-entry-table]")) setupTable(tableEl);
    });
  }
})();
