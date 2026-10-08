// baris aktif ala ALV: klik / Tab ke tabel -> baris jadi aktif, panah atas/bawah pindah, Home/End ke ujung.
// cuma satu baris yg bisa di-Tab (roving tabindex), jadi Tab ga mampir ke tiap baris.
import { useCallback, useEffect, useRef, useState } from "react";

export default function useActiveRow(rows) {
  const [activeIndex, setActiveIndex] = useState(-1);
  const rowRefList = useRef([]);

  // isi tabel ganti (urutan/halaman/filter) -> baris aktif dilepas
  useEffect(() => {
    setActiveIndex(-1);
  }, [rows]);

  // isFocused = pindahin fokus keyboard ke baris itu. Pindah pake panah: layar ikut geser kalau barisnya
  // ga keliatan. Diklik (kiri/kanan): barisnya pasti udah keliatan, layar jangan geser (isScrolled false)
  const activate = useCallback((index, isFocused, isScrolled = true) => {
    if (!rows.length) return;
    const nextIndex = Math.max(0, Math.min(rows.length - 1, index));
    setActiveIndex(nextIndex);
    if (isFocused && rowRefList.current[nextIndex]) rowRefList.current[nextIndex].focus({ preventScroll: !isScrolled });
  }, [rows]);

  // baris yg bisa di-Tab: yg aktif, kalau belum ada yg aktif baris pertama
  const getTabIndex = useCallback(
    (index) => (index === (activeIndex >= 0 ? activeIndex : 0) ? 0 : -1),
    [activeIndex],
  );

  const setRowRef = useCallback((index) => (element) => {
    rowRefList.current[index] = element;
  }, []);

  return { activeIndex, activate, getTabIndex, setRowRef };
}
