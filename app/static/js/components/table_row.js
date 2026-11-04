// baris aktif di tabel ALV (layar lebar): klik baris -> baris jadi aktif, double-click buka (data-row-url),
// klik kanan -> menu baris: buka, salin nilai sel, salin baris
(function () {
  "use strict";

  const INTERACTIVE_SELECTOR = "a, button, input, select, textarea, label, [data-bs-toggle]";
  let menuEl = null;
  let menuRowEl = null;

  function notify(text, type) {
    if (window.AlrStatusBar) window.AlrStatusBar.show(text, type, false);
  }

  // salin ke clipboard (cara salinnya dari copy_button.js), hasilnya dikabarin di status bar
  function copyText(text) {
    return window.AlrCopy.copyText(text).then(
      function () { notify("Copied: " + (text.length > 60 ? text.slice(0, 60) + "…" : text), "success"); },
      function () { notify("Copy failed; the browser did not allow it", "danger"); }
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
    return labelEl ? labelEl.textContent.trim() : "column";
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
      menuEl.setAttribute("aria-label", "Row menu");
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
      addMenuItem("Open", function () { window.location.href = rowEl.dataset.rowUrl; });
    }
    if (cellEl && cellEl.dataset.column) {
      addMenuItem("Copy " + readColumnLabel(tableEl, cellEl), function () { copyText(readCellValue(cellEl)); });
    }
    addMenuItem("Copy row", function () {
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

    function activate(index) {
      if (activeIndex >= 0 && activeIndex !== index) rowList[activeIndex].classList.remove("is-active");
      rowList[index].classList.add("is-active");
      activeIndex = index;
    }

    function openRow(rowEl) {
      if (rowEl.dataset.rowUrl) window.location.href = rowEl.dataset.rowUrl;
    }

    rowList.forEach(function (rowEl, index) {
      // klik di link/tombol tetep jalan normal, barisnya cuma ditandain aktif
      rowEl.addEventListener("click", function () {
        activate(index);
      });
      rowEl.addEventListener("dblclick", function (event) {
        if (event.target.closest(INTERACTIVE_SELECTOR)) return;
        openRow(rowEl);
      });
      // klik kanan di link: menu bawaan browser (buka di tab baru, salin link)
      rowEl.addEventListener("contextmenu", function (event) {
        if (event.target.closest(INTERACTIVE_SELECTOR)) return;
        event.preventDefault();
        activate(index);
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
