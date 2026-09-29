// editor teks bertoolbar (tanpa library luar). Hasil HTML disalin ke textarea tersembunyi,
// terus dibersihin lagi di server (tag berbahaya dibuang)
(function () {
  "use strict";

  const LINK_PATTERN = /^https?:\/\/\S+$/i;
  const STATE_COMMAND_LIST = ["bold", "italic", "underline", "insertUnorderedList", "insertOrderedList"];

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

  // nyalain tombol toolbar sesuai format di posisi kursor
  function updateToolbarState(editorEl) {
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
    const rawUrl = window.prompt("Masukkan link (harus diawali http:// atau https://)", "https://");
    if (!rawUrl) return;

    const url = rawUrl.trim();
    if (!LINK_PATTERN.test(url)) {
      if (window.AlrFlash) window.AlrFlash.show("Link harus diawali http:// atau https://", "warning");
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
    const selectedText = window.getSelection().toString() || "kode";
    // textContent -> isi otomatis di-escape, aman
    const codeEl = document.createElement("code");
    codeEl.textContent = selectedText;
    document.execCommand("insertHTML", false, codeEl.outerHTML + "&nbsp;");
  }

  function runCommand(editorEl, command) {
    const part = getPart(editorEl);
    part.contentEl.focus();

    if (command === "createLink") {
      insertLink(part.contentEl);
    } else if (command === "code") {
      insertCode();
    } else {
      document.execCommand(command, false, null);
    }

    syncInput(editorEl);
    updateToolbarState(editorEl);
  }

  function setupEditor(editorEl) {
    const part = getPart(editorEl);
    editorEl.dataset.rteReady = "true";

    editorEl.querySelectorAll("[data-rte-command]").forEach(function (buttonEl) {
      // mousedown dicegah biar blok teks di editor ga ilang pas tombol diklik
      buttonEl.addEventListener("mousedown", function (event) {
        event.preventDefault();
      });
      buttonEl.addEventListener("click", function () {
        runCommand(editorEl, buttonEl.dataset.rteCommand);
      });
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

  // enter bikin paragraf <p> (lebih rapi dibanding <div>)
  try {
    document.execCommand("defaultParagraphSeparator", false, "p");
  } catch (error) {
    // browser lama, cuekin
  }

  init(document);
  window.AlrRichTextEditor = { init: init };
})();