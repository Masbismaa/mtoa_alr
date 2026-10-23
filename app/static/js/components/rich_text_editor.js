// editor teks bertoolbar ala Word (tanpa library luar). Hasil HTML disalin ke textarea tersembunyi,
// terus dibersihin lagi di server (tag berbahaya & nilai font/warna di luar pilihan toolbar dibuang)
(function () {
  "use strict";

  const LINK_PATTERN = /^https?:\/\/\S+$/i;
  const STATE_COMMAND_LIST = [
    "bold", "italic", "underline", "strikeThrough", "insertUnorderedList", "insertOrderedList",
    "justifyLeft", "justifyCenter", "justifyRight", "justifyFull"
  ];
  // blok teks terakhir per editor: dropdown (gaya paragraf/font/ukuran) bikin fokus pindah & blok teks ilang
  const savedRangeMap = new WeakMap();

  function getPart(editorEl) {
    return {
      contentEl: editorEl.querySelector("[data-rte-content]"),
      inputEl: editorEl.querySelector("[data-rte-input]")
    };
  }

  // salin isi editor ke textarea yg ikut dikirim form
  function syncInput(editorEl) {
    const part = getPart(editorEl);
    // editor yg kosong kadang nyisain <br>, dianggep kosong aja
    part.inputEl.value = part.contentEl.textContent.trim() === "" && !part.contentEl.querySelector("li") ? "" : part.contentEl.innerHTML;
  }

  function readCommandValue(command) {
    try {
      return String(document.queryCommandValue(command) || "");
    } catch (error) {
      return "";
    }
  }

  // nyalain tombol toolbar & isi dropdown sesuai format di posisi kursor
  function updateToolbarState(editorEl) {
    editorEl.querySelectorAll("[data-rte-select]").forEach(function (selectEl) {
      let value = readCommandValue(selectEl.dataset.rteSelect).toLowerCase();
      if (selectEl.dataset.rteSelect === "formatBlock" && (!value || value === "div")) value = "p";
      // font dibaca sebagai daftar CSS ('"Times New Roman", serif'), cukup ambil yg pertama
      if (selectEl.dataset.rteSelect === "fontName") value = value.split(",")[0].replace(/["']/g, "").trim();
      const optionEl = Array.from(selectEl.options).find(function (el) { return el.value.toLowerCase() === value; });
      selectEl.value = optionEl ? optionEl.value : selectEl.options[0].value;
    });
    editorEl.querySelectorAll("[data-rte-command]").forEach(function (buttonEl) {
      const command = buttonEl.dataset.rteCommand;
      if (!STATE_COMMAND_LIST.includes(command)) return;
      let isActive = false;
      try {
        isActive = document.queryCommandState(command);
      } catch (error) {
        isActive = false;
      }
      buttonEl.classList.toggle("is-active", isActive);
      buttonEl.setAttribute("aria-pressed", String(isActive));
    });
  }

  function insertLink(contentEl) {
    // simpen posisi blok teks dulu, soalnya kotak prompt bikin fokus pindah
    const selection = window.getSelection();
    const savedRange = selection.rangeCount ? selection.getRangeAt(0).cloneRange() : null;
    const rawUrl = window.prompt("Enter a link (must start with http:// or https://)", "https://");
    if (!rawUrl) return;

    const url = rawUrl.trim();
    if (!LINK_PATTERN.test(url)) {
      if (window.AlrFlash) window.AlrFlash.show("The link must start with http:// or https://", "warning");
      return;
    }

    contentEl.focus();
    if (savedRange) {
      selection.removeAllRanges();
      selection.addRange(savedRange);
    }
    // kalau ga ada teks yg diblok, link-nya ditulis sebagai teks sekalian
    if (selection.isCollapsed) {
      const linkEl = document.createElement("a");
      linkEl.href = url;
      linkEl.textContent = url;
      document.execCommand("insertHTML", false, linkEl.outerHTML);
    } else {
      document.execCommand("createLink", false, url);
    }
  }

  function insertCode() {
    const selectedText = window.getSelection().toString() || "code";
    // textContent -> isi otomatis di-escape, aman
    const codeEl = document.createElement("code");
    codeEl.textContent = selectedText;
    document.execCommand("insertHTML", false, codeEl.outerHTML + "&nbsp;");
  }

  function restoreSelection(editorEl) {
    const range = savedRangeMap.get(editorEl);
    if (!range) return;
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function runCommand(editorEl, command, value) {
    const part = getPart(editorEl);
    part.contentEl.focus();
    restoreSelection(editorEl);

    if (command === "createLink") {
      insertLink(part.contentEl);
    } else if (command === "code") {
      insertCode();
    } else if (command === "formatBlock") {
      document.execCommand(command, false, "<" + value + ">");
    } else {
      document.execCommand(command, false, value || "");
    }

    syncInput(editorEl);
    updateToolbarState(editorEl);
  }

  function setupEditor(editorEl) {
    const part = getPart(editorEl);
    editorEl.dataset.rteReady = "true";

    // mousedown dicegah biar blok teks di editor ga ilang pas tombol diklik (termasuk tombol buka menu warna)
    editorEl.querySelectorAll(".rte-toolbar button").forEach(function (buttonEl) {
      buttonEl.addEventListener("mousedown", function (event) {
        event.preventDefault();
      });
    });
    editorEl.querySelectorAll("[data-rte-command]").forEach(function (buttonEl) {
      buttonEl.addEventListener("click", function () {
        runCommand(editorEl, buttonEl.dataset.rteCommand, buttonEl.dataset.rteValue);
      });
    });
    editorEl.querySelectorAll("[data-rte-select]").forEach(function (selectEl) {
      selectEl.addEventListener("change", function () {
        if (selectEl.value) runCommand(editorEl, selectEl.dataset.rteSelect, selectEl.value);
      });
    });

    document.addEventListener("selectionchange", function () {
      const selection = window.getSelection();
      if (selection.rangeCount && part.contentEl.contains(selection.anchorNode)) {
        savedRangeMap.set(editorEl, selection.getRangeAt(0).cloneRange());
        updateToolbarState(editorEl);
      }
    });

    // Tab / Shift+Tab di dalem list = naik-turun level kayak Word. Di luar list Tab tetep pindah fokus
    part.contentEl.addEventListener("keydown", function (event) {
      if (event.key !== "Tab" || event.ctrlKey || event.altKey) return;
      const anchorNode = window.getSelection().anchorNode;
      const anchorEl = anchorNode && (anchorNode.nodeType === 1 ? anchorNode : anchorNode.parentElement);
      if (!anchorEl || !anchorEl.closest("li")) return;
      event.preventDefault();
      runCommand(editorEl, event.shiftKey ? "outdent" : "indent");
    });

    part.contentEl.addEventListener("input", function () {
      syncInput(editorEl);
    });

    part.contentEl.addEventListener("keyup", function () {
      updateToolbarState(editorEl);
    });

    part.contentEl.addEventListener("mouseup", function () {
      updateToolbarState(editorEl);
    });

    // paste dari Word/web jadi teks polos biar ga bawa style & script aneh
    part.contentEl.addEventListener("paste", function (event) {
      event.preventDefault();
      const clipboardData = event.clipboardData || window.clipboardData;
      const plainText = clipboardData ? clipboardData.getData("text/plain") : "";
      document.execCommand("insertText", false, plainText);
    });

    // jaga-jaga: salin sekali lagi pas form dikirim
    const formEl = editorEl.closest("form");
    if (formEl) {
      formEl.addEventListener("submit", function () {
        syncInput(editorEl);
      });
    }
  }

  // aktifin semua editor di dalam rootEl (dipanggil lagi pas "Add field")
  function init(rootEl) {
    const scopeEl = rootEl || document;
    const editorList = scopeEl.matches && scopeEl.matches("[data-rte]") ? [scopeEl] : [];
    scopeEl.querySelectorAll("[data-rte]:not([data-rte-ready])").forEach(function (editorEl) {
      editorList.push(editorEl);
    });
    editorList.forEach(function (editorEl) {
      if (editorEl.dataset.rteReady !== "true") setupEditor(editorEl);
    });
  }

  // enter bikin paragraf <p> (lebih rapi dibanding <div>); format pake tag (<font>, <b>) bukan style
  // biar lolos sanitizer server
  try {
    document.execCommand("defaultParagraphSeparator", false, "p");
    document.execCommand("styleWithCSS", false, false);
  } catch (error) {
    // browser lama, cuekin
  }

  init(document);
  window.AlrRichTextEditor = { init: init };
})();