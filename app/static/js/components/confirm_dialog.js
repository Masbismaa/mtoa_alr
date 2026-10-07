// dialog konfirmasi: otomatis buat form ber-atribut data-confirm-message,
// bisa juga dipanggil manual lewat window.AlrConfirm.open({...}).
// isInfo: true -> cuma pemberitahuan (satu tombol), dipake menu sidebar yg terkunci
(function () {
  "use strict";

  const dialogEl = document.getElementById("confirm_dialog");
  if (!dialogEl || typeof dialogEl.showModal !== "function") return;

  const titleEl = dialogEl.querySelector("[data-confirm-title]");
  const messageEl = dialogEl.querySelector("[data-confirm-message]");
  const okButton = dialogEl.querySelector("[data-confirm-ok]");
  const cancelButton = dialogEl.querySelector("[data-confirm-cancel]");
  const statusEl = dialogEl.querySelector("[data-confirm-status]");
  const iconEl = dialogEl.querySelector("[data-confirm-icon]");
  let resolveCurrent = null;

  // buka dialog, hasilnya Promise true (lanjut) / false (batal)
  function open(optionDict) {
    const settingDict = optionDict || {};
    titleEl.textContent = settingDict.title || "Yakin?";
    messageEl.textContent = settingDict.message || "";
    okButton.textContent = settingDict.okLabel || "Ya, lanjutkan";
    // mode pemberitahuan: warna kuning, tombol Batal disembunyiin
    const isInfo = Boolean(settingDict.isInfo);
    statusEl.classList.toggle("bg-danger", !isInfo);
    statusEl.classList.toggle("bg-warning", isInfo);
    iconEl.classList.toggle("text-danger", !isInfo);
    iconEl.classList.toggle("text-warning", isInfo);
    okButton.classList.toggle("btn-danger", !isInfo);
    okButton.classList.toggle("btn-primary", isInfo);
    cancelButton.parentElement.hidden = isInfo;
    dialogEl.showModal();
    // fokus awal ke "Batal" biar ga kepencet hapus pas neken Enter (mode info: ke tombol Mengerti)
    (isInfo ? okButton : cancelButton).focus();
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

  // menu sidebar yg terkunci: diklik -> muncul pemberitahuan ga ada otoritas
  document.querySelectorAll("[data-locked-message]").forEach(function (buttonEl) {
    buttonEl.addEventListener("click", function () {
      open({ title: "Tidak ada otoritas", message: buttonEl.dataset.lockedMessage, okLabel: "Mengerti", isInfo: true });
    });
  });

  window.AlrConfirm = { open: open };
})();