// baris aktif ala ALV: baris yg diklik ditandain aktif
import { useCallback, useEffect, useState } from "react";

export default function useActiveRow(rows) {
  const [activeIndex, setActiveIndex] = useState(-1);

  // isi tabel ganti (urutan/halaman/filter) -> baris aktif dilepas
  useEffect(() => {
    setActiveIndex(-1);
  }, [rows]);

  const activate = useCallback((index) => {
    if (rows.length) setActiveIndex(index);
  }, [rows]);

  return { activeIndex, activate };
}
