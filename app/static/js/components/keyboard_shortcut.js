// shortcut keyboard ala SAP GUI. Tombol tujuannya ditandain data-shortcut (toolbar, panel Kriteria Pencarian):
// F3 Kembali, Shift+F3 Keluar, F12 / Shift+F12 Batal, Ctrl+S Simpan, F8 Jalankan, F1 Bantuan
(function () {
  "use strict";

  // tombol keyboard -> nama shortcut. null = bukan shortcut, dibiarin
  function findShortcut(event) {
    if (event.altKey) return null;
    if (event.key === "F3") return event.shiftKey ? "exit" : "back";
    if (event.key === "F12") return "cancel";
    if (event.key === "F8") return "run";
    if (event.key === "F1") return "help";
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") return "save";
    return null;
  }

  document.addEventListener("keydown", function (event) {
    const shortcutName = findShortcut(event);
    if (!shortcutName || event.defaultPrevented) return;
    // lagi ada dialog kebuka (konfirmasi, Bantuan, Multi Selection): shortcut layar ga dijalanin
    if (document.querySelector("dialog[open]")) return;
    // aksi bawaan browser (cari di halaman, simpan halaman, bantuan browser) dicegah biar ga bentrok
    event.preventDefault();
    const targetEl = document.querySelector('[data-shortcut="' + shortcutName + '"]');
    // tombolnya ga ada / nonaktif di layar ini: ga ngapa-ngapain
    if (!targetEl || targetEl.disabled) return;
    // pake click() biar alurnya sama kayak diklik (termasuk peringatan form belum disimpan)
    targetEl.click();
  });
})();
