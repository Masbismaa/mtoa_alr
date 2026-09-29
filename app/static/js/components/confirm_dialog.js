// dialog konfirmasi: otomatis buat form ber-atribut data-confirm-message,
// bisa juga dipanggil manual lewat window.AlrConfirm.open({...})
(function () {
  "use strict";

  const dialogEl = document.getElementById("confirm_dialog");
  if (!dialogEl || typeof dialogEl.showModal !== "function") return;

  const titleEl = dialogEl.querySelector("[data-confirm-title]");
  const messageEl = dialogEl.querySelector("[data-confirm-message]");
  const okButton = dialogEl.querySelector("[data-confirm-ok]");
  const cancelButton = dialogEl.querySelector("[data-confirm-cancel]");
  let resolveCurrent = null;

  // buka dialog, hasilnya Promise true (lanjut) / false (batal)
  function open(optionDict) {
    const settingDict = optionDict || {};
    titleEl.textContent = settingDict.title || "Yakin?";
    messageEl.textContent = settingDict.message || "";
    okButton.textContent = settingDict.okLabel || "Ya, lanjutkan";
    dialogEl.showModal();
    // fokus awal ke "Batal" biar ga kepencet hapus pas neken Enter
    cancelButton.focus();
    return new Promise(function (resolve) {
      resolveCurrent = resolve;
    });
  }

  function finish(isConfirmed) {
    if (dialogEl.open) dialogEl.close();
    if (resolveCurrent) {
      resolveCurrent(isConfirmed);
      resolveCurrent = null;
    }
  }

  okButton.addEventListener("click", function () {
    finish(true);
  });

  cancelButton.addEventListener("click", function () {
    finish(false);
  });

  // tombol Esc
  dialogEl.addEventListener("cancel", function (event) {
    event.preventDefault();
    finish(false);
  });

  // klik area gelap di luar dialog
  dialogEl.addEventListener("click", function (event) {
    if (event.target === dialogEl) finish(false);
  });

  // form yg butuh konfirmasi dulu sebelum dikirim
  document.querySelectorAll("form[data-confirm-message]").forEach(function (formEl) {
    formEl.addEventListener("submit", async function (event) {
      if (formEl.dataset.isConfirmed === "true") {
        delete formEl.dataset.isConfirmed;
        return;
      }
      event.preventDefault();
      const isConfirmed = await open({
        title: formEl.dataset.confirmTitle,
        message: formEl.dataset.confirmMessage,
        okLabel: formEl.dataset.confirmOk
      });
      if (isConfirmed) {
        formEl.dataset.isConfirmed = "true";
        formEl.requestSubmit();
      }
    });
  });

  window.AlrConfirm = { open: open };
})();