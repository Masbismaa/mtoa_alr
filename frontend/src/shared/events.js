// klik kiri biasa (tanpa Ctrl/Shift/Alt/Cmd). Klik pake tombol itu = user mau buka link di tab baru, jadi dibiarin
export function isPlainClick(event) {
  return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey;
}

// elemen yg punya aksi sendiri di dalam baris tabel: klik di sini ga dianggep klik baris
export const INTERACTIVE_SELECTOR = "a, button, input, select, textarea, label";

export function isInteractiveTarget(target) {
  return Boolean(target && target.closest && target.closest(INTERACTIVE_SELECTOR));
}
