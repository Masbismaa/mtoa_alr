// kirim pesan ke status bar bawah ala SAP (js/components/app_shell.js -> window.AlrStatusBar).
// isKept false = cuma tampil, ga masuk riwayat (buat pesan yg sering, misal "Layout tersimpan").
// status bar belum siap / ga ada di halaman -> diem aja
export function showStatus(text, type = "info", isKept = true) {
  if (window.AlrStatusBar) window.AlrStatusBar.show(text, type, isKept);
}
