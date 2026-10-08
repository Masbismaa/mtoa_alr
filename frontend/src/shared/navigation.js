// pindah halaman / muat ulang. Dibungkus di sini biar gampang diganti di test (window.location ga bisa di-mock langsung)
export function navigateTo(url) {
  window.location.assign(url);
}

export function reloadPage() {
  window.location.reload();
}
