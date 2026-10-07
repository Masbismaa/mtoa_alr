// tabel ala ALV SAP: tarik garis di kanan judul kolom buat ngatur lebar (atau fokus + panah kiri/kanan),
// menu "Kolom" buat nyembunyiin/nampilin kolom. Layout langsung disimpen ke akun lewat AlrUiPreference.saveToServer.
// ngurutin kolom ga di sini: judul kolom itu link biasa (?sort=...), diurutin server
(function () {
  "use strict";

  const MIN_WIDTH = 60;
  const MAX_WIDTH = 800;
  const KEYBOARD_STEP = 16;
  const SAVE_DELAY = 600;
  const preference = window.AlrUiPreference;

  function parseJson(text, fallback) {
    try {
      return JSON.parse(text || "");
    } catch (error) {
      return fallback;
    }
  }

  function clampWidth(width) {
    return Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, width)));
  }

  function setupTable(tableEl) {
    const tableKey = tableEl.dataset.tableKey;
    const layoutDict = parseJson(tableEl.dataset.tableLayout, {});
    const defaultLayoutDict = parseJson(tableEl.dataset.defaultLayout, { hidden_list: [], width_dict: {} });
    const defaultWidthDict = parseJson(tableEl.dataset.defaultWidth, {});
    const cardEl = tableEl.closest(".card") || document;
    const menuEl = cardEl.querySelector('[data-table-menu="' + tableKey + '"]');
    const statusEl = menuEl ? menuEl.querySelector("[data-table-status]") : null;
    let saveTimer = null;

    layoutDict.hidden_list = Array.isArray(layoutDict.hidden_list) ? layoutDict.hidden_list : [];
    layoutDict.width_dict = layoutDict.width_dict && typeof layoutDict.width_dict === "object" ? layoutDict.width_dict : {};

    // status simpan layout: di menu Kolom + di status bar bawah (kelihatan walau menunya ketutup).
    // yg berhasil ga dicatat ke riwayat biar ga numpuk tiap kolom digeser, yg gagal dicatat
    function showStatus(text, isError, isFinal) {
      if (statusEl) {
        statusEl.textContent = text;
        statusEl.classList.toggle("text-danger", Boolean(isError));
      }
      if (isFinal && window.AlrStatusBar) window.AlrStatusBar.show(text, isError ? "danger" : "success", Boolean(isError));
    }

    // disimpen setelah user berhenti geser/klik sebentar, biar ga ngirim tiap piksel
    function scheduleSave() {
      if (!preference) return;
      showStatus("Menyimpan layout...");
      window.clearTimeout(saveTimer);
      saveTimer = window.setTimeout(async function () {
        const resultDict = await preference.saveToServer({
          table_key: tableKey,
          hidden_list: layoutDict.hidden_list,
          width_dict: layoutDict.width_dict
        }, tableEl.dataset.layoutUrl);
        showStatus(resultDict.is_success ? "Layout tabel tersimpan" : (resultDict.message || "Gagal menyimpan layout tabel"), !resultDict.is_success, true);
      }, SAVE_DELAY);
    }

    function getHeadCell(key) {
      return tableEl.querySelector('th[data-column="' + key + '"]');
    }

    function setColumnHidden(key, isHidden) {
      tableEl.querySelectorAll('[data-column="' + key + '"]').forEach(function (cellEl) {
        cellEl.hidden = isHidden;
      });
    }

    function setColumnWidth(key, width) {
      const headEl = getHeadCell(key);
      if (headEl) headEl.style.width = width + "px";
    }

    function rememberWidth(key, width) {
      layoutDict.width_dict[key] = clampWidth(width);
      scheduleSave();
    }

    // geser lebar kolom pake mouse / jari
    tableEl.querySelectorAll("[data-table-resize]").forEach(function (handleEl) {
      const headEl = handleEl.closest("th");
      const key = headEl.dataset.column;

      handleEl.addEventListener("pointerdown", function (event) {
        event.preventDefault();
        const startX = event.clientX;
        const startWidth = headEl.getBoundingClientRect().width;
        let currentWidth = startWidth;
        handleEl.setPointerCapture(event.pointerId);
        tableEl.classList.add("is-resizing");

        function handleMove(moveEvent) {
          currentWidth = clampWidth(startWidth + moveEvent.clientX - startX);
          setColumnWidth(key, currentWidth);
        }

        function handleUp() {
          handleEl.removeEventListener("pointermove", handleMove);
          handleEl.removeEventListener("pointerup", handleUp);
          handleEl.removeEventListener("pointercancel", handleUp);
          tableEl.classList.remove("is-resizing");
          if (currentWidth !== Math.round(startWidth)) rememberWidth(key, currentWidth);
        }

        handleEl.addEventListener("pointermove", handleMove);
        handleEl.addEventListener("pointerup", handleUp);
        handleEl.addEventListener("pointercancel", handleUp);
      });

      // keyboard: panah kiri/kanan ngecilin/gedein kolom
      handleEl.addEventListener("keydown", function (event) {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const step = event.key === "ArrowRight" ? KEYBOARD_STEP : -KEYBOARD_STEP;
        const width = clampWidth(headEl.getBoundingClientRect().width + step);
        setColumnWidth(key, width);
        rememberWidth(key, width);
      });
    });

    if (!menuEl) return;
    const toggleList = menuEl.querySelectorAll("[data-table-column-toggle]");

    // centang/hapus centang kolom di menu "Kolom"
    toggleList.forEach(function (toggleEl) {
      toggleEl.addEventListener("change", function () {
        const key = toggleEl.value;
        const isHidden = !toggleEl.checked;
        setColumnHidden(key, isHidden);
        layoutDict.hidden_list = layoutDict.hidden_list.filter(function (hiddenKey) { return hiddenKey !== key; });
        if (isHidden) layoutDict.hidden_list.push(key);
        scheduleSave();
      });
    });

    // balikin ke layout awal: kolom bawaan, lebar bawaan
    menuEl.querySelector("[data-table-reset]").addEventListener("click", function () {
      layoutDict.hidden_list = defaultLayoutDict.hidden_list.slice();
      layoutDict.width_dict = {};
      toggleList.forEach(function (toggleEl) {
        const isHidden = layoutDict.hidden_list.includes(toggleEl.value);
        toggleEl.checked = !isHidden;
        setColumnHidden(toggleEl.value, isHidden);
      });
      Object.keys(defaultWidthDict).forEach(function (key) {
        setColumnWidth(key, defaultWidthDict[key]);
      });
      scheduleSave();
    });
  }

  document.querySelectorAll("table[data-table-key]").forEach(setupTable);

  // filter per kolom: ganti pilihan langsung diterapin, isian kosong ga ikut dikirim biar URL rapi
  document.querySelectorAll("[data-column-filter-form]").forEach(function (formEl) {
    const fieldList = document.querySelectorAll('[form="' + formEl.id + '"][data-column-filter]');
    fieldList.forEach(function (fieldEl) {
      if (fieldEl.tagName === "SELECT") {
        fieldEl.addEventListener("change", function () { formEl.requestSubmit(); });
      }
    });
    formEl.addEventListener("submit", function () {
      fieldList.forEach(function (fieldEl) {
        if (!fieldEl.value.trim()) fieldEl.disabled = true;
      });
    });
  });

  // halaman dibuka lagi lewat tombol Back: isian filter dinyalain lagi (kecuali yg emang dikunci)
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("[data-column-filter]:disabled:not([title])").forEach(function (fieldEl) { fieldEl.disabled = false; });
  });
})();
