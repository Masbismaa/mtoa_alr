// filter dashboard: pilih dropdown langsung nyari, ngetik keyword nunggu bentar baru nyari
(function () {
  "use strict";
  const DEBOUNCE_MS = 500;
  const formEl = document.querySelector("[data-filter-form]");
  if (!formEl) return;
  const searchEl = formEl.querySelector("[data-filter-search]");
  let timerId = null;

  function submitFilter() {
    formEl.classList.add("is-loading");
    formEl.requestSubmit();
  }

  formEl.querySelectorAll("[data-filter-auto]").forEach(function (selectEl) {
    selectEl.addEventListener("change", submitFilter);
  });

  if (searchEl) {
    // nunggu user berhenti ngetik dulu biar ga reload tiap huruf
    searchEl.addEventListener("input", function () {
      window.clearTimeout(timerId);
      timerId = window.setTimeout(submitFilter, DEBOUNCE_MS);
    });

    // abis reload, kursor balik ke ujung teks biar bisa lanjut ngetik
    if (searchEl.value) {
      const textLength = searchEl.value.length;
      searchEl.focus();
      searchEl.setSelectionRange(textLength, textLength);
    }

    // tekan "/" buat langsung ke kolom search
    document.addEventListener("keydown", function (event) {
      const activeEl = document.activeElement;
      const isTyping = activeEl && (["INPUT", "TEXTAREA", "SELECT"].includes(activeEl.tagName) || activeEl.isContentEditable);
      if (event.key === "/" && !isTyping) {
        event.preventDefault();
        searchEl.focus();
      }
    });
  }
})();