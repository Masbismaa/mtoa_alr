// peringatan perubahan yg belum disimpan, buat form ber-atribut data-form-guard.
// isian berubah terus pindah halaman (link, tombol Kembali/Keluar/Batal, form lain, tutup tab) -> ditanya dulu.
// form belum berubah -> ga ditanya apa-apa
(function () {
  "use strict";

  const formEl = document.querySelector("form[data-form-guard]");
  if (!formEl) return;
  let initialState = null;
  let isLeaving = false;

  // isi form jadi teks buat dibandingin. File cukup nama + ukurannya, token CSRF ga ikut
  function readState() {
    const partList = [];
    new FormData(formEl).forEach(function (value, key) {
      if (key === "csrf_token") return;
      partList.push(key + "=" + (value instanceof File ? value.name + ":" + value.size : value));
    });
    return partList.join("&");
  }

  // form yg tampil lagi abis gagal disimpan (error validasi) isinya belum kesimpen, jadi dari awal dianggap berubah
  const isUnsavedFromStart = formEl.hasAttribute("data-form-guard-dirty");

  function isDirty() {
    return isUnsavedFromStart || (initialState !== null && readState() !== initialState);
  }

  // snapshot diambil setelah semua script form (editor teks, lampiran) selesai nyiapin isian
  window.addEventListener("load", function () {
    initialState = readState();
  });

  function confirmLeave() {
    if (!window.AlrConfirm) return Promise.resolve(window.confirm("Perubahan belum disimpan. Tetap keluar?"));
    return window.AlrConfirm.open({
      title: "Buang perubahan?",
      message: "Isian yang berubah belum disimpan. Kalau keluar sekarang, perubahannya hilang.",
      okLabel: "Ya, buang"
    });
  }

  // klik link ke halaman lain (termasuk tombol Kembali/Keluar/Batal di toolbar & form)
  document.addEventListener("click", async function (event) {
    const linkEl = event.target.closest("a[href]");
    if (!linkEl || isLeaving || !isDirty()) return;
    const isNewTab = linkEl.target === "_blank" || linkEl.hasAttribute("download") || event.ctrlKey || event.metaKey || event.shiftKey;
    const href = linkEl.getAttribute("href");
    if (isNewTab || event.button !== 0 || href.startsWith("#") || href.startsWith("javascript:")) return;
    event.preventDefault();
    if (await confirmLeave()) {
      isLeaving = true;
      window.location.href = linkEl.href;
    }
  }, true);

  // form ini dikirim (Simpan) -> boleh pergi. Form lain dikirim (misal Logout) -> ditanya dulu.
  // form yg punya konfirmasi sendiri (data-confirm-message) & dialog dibiarin
  document.addEventListener("submit", async function (event) {
    const submittedEl = event.target;
    if (submittedEl === formEl) {
      isLeaving = true;
      // pengiriman dibatalin script lain -> peringatan nyala lagi
      window.setTimeout(function () {
        if (event.defaultPrevented) isLeaving = false;
      }, 0);
      return;
    }
    if (isLeaving || !isDirty() || submittedEl.method === "dialog" || submittedEl.hasAttribute("data-confirm-message")) return;
    event.preventDefault();
    if (await confirmLeave()) {
      isLeaving = true;
      submittedEl.requestSubmit(event.submitter);
    }
  }, true);

  // tutup tab, refresh, atau tombol back browser: browser yg nampilin pertanyaannya
  window.addEventListener("beforeunload", function (event) {
    if (isLeaving || !isDirty()) return;
    event.preventDefault();
    event.returnValue = "";
  });
})();
