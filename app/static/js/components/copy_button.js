// tombol copy: sekali klik langsung kesalin, ga perlu blok teks manual
(function () {
  "use strict";

  const RESET_MS = 1500;

  // cadangan buat akses lewat http biasa (misal pake IP kantor), clipboard API cuma jalan di https/localhost
  function copyWithFallback(text) {
    const textareaEl = document.createElement("textarea");
    textareaEl.value = text;
    textareaEl.setAttribute("readonly", "");
    textareaEl.className = "visually-hidden";
    document.body.append(textareaEl);
    textareaEl.select();
    const isCopied = document.execCommand("copy");
    textareaEl.remove();
    if (!isCopied) throw new Error("copy gagal");
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    copyWithFallback(text);
  }

  // ambil teks yg mau dicopy dari tombol (langsung / dari elemen target)
  function getCopyText(buttonEl) {
    if (buttonEl.dataset.copyTarget) {
      const targetEl = document.getElementById(buttonEl.dataset.copyTarget);
      if (!targetEl) return "";
      return targetEl.dataset.secretValue || targetEl.textContent;
    }
    return buttonEl.dataset.copyText || "";
  }

  document.addEventListener("click", async function (event) {
    const buttonEl = event.target.closest("[data-copy-text], [data-copy-target]");
    if (!buttonEl) return;

    const labelEl = buttonEl.querySelector("[data-copy-label]");
    const originalLabel = labelEl ? labelEl.textContent : "";

    try {
      await copyText(getCopyText(buttonEl));
      if (labelEl) labelEl.textContent = "Tersalin \u2713";
      buttonEl.classList.add("is-copied");
      window.setTimeout(function () {
        if (labelEl) labelEl.textContent = originalLabel;
        buttonEl.classList.remove("is-copied");
      }, RESET_MS);
    } catch (error) {
      if (window.AlrFlash) window.AlrFlash.show("Gagal menyalin, coba blok teksnya manual", "danger");
    }
  });

  window.AlrClipboard = { copyText: copyText };
})();