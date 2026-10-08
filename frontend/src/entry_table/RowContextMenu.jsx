// menu klik kanan di baris tabel (juga lewat Shift+F10 / tombol Menu di keyboard):
// Buka, Salin <kolom yg diklik>, Salin baris. Panah atas/bawah pindah pilihan, Esc/Tab nutup.
import { useEffect, useLayoutEffect, useRef } from "react";

const SCREEN_MARGIN = 8;

export default function RowContextMenu({ x, y, itemList, onClose }) {
  const menuRef = useRef(null);

  // geser biar ga keluar layar, terus fokus ke pilihan pertama
  useLayoutEffect(() => {
    const menuEl = menuRef.current;
    const rect = menuEl.getBoundingClientRect();
    menuEl.style.left = Math.max(SCREEN_MARGIN, Math.min(x, window.innerWidth - rect.width - SCREEN_MARGIN)) + "px";
    menuEl.style.top = Math.max(SCREEN_MARGIN, Math.min(y, window.innerHeight - rect.height - SCREEN_MARGIN)) + "px";
    const firstItemEl = menuEl.querySelector("[role=menuitem]");
    if (firstItemEl) firstItemEl.focus({ preventScroll: true });
  }, [x, y]);

  // klik di luar, user nge-scroll (roda mouse / geser layar sentuh), atau ukuran layar berubah -> tutup
  // (posisi menu udah ga nyambung sama barisnya). Sengaja BUKAN event "scroll": scroll halus yg masih jalan
  // dari sebelum menu kebuka bakal langsung nutup menunya lagi
  useEffect(() => {
    function handlePointerDown(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) onClose(false);
    }
    function handleUserScroll(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) onClose(false);
    }
    function handleResize() {
      onClose(false);
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("wheel", handleUserScroll, { passive: true });
    document.addEventListener("touchmove", handleUserScroll, { passive: true });
    window.addEventListener("resize", handleResize);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("wheel", handleUserScroll);
      document.removeEventListener("touchmove", handleUserScroll);
      window.removeEventListener("resize", handleResize);
    };
  }, [onClose]);

  function handleKeyDown(event) {
    const itemElList = Array.from(menuRef.current.querySelectorAll("[role=menuitem]"));
    const currentIndex = itemElList.indexOf(document.activeElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      itemElList[(currentIndex + step + itemElList.length) % itemElList.length].focus();
    } else if (event.key === "Escape" || event.key === "Tab") {
      event.preventDefault();
      onClose(true);
    }
  }

  return (
    <div
      // class app-menu, BUKAN dropdown-menu: lihat komentar .app-menu di static/css/components/table.css
      className="app-menu row-context-menu"
      role="menu"
      aria-label="Menu baris"
      ref={menuRef}
      style={{ left: x + "px", top: y + "px" }}
      onKeyDown={handleKeyDown}
    >
      {itemList.map((item) => (
        <button
          type="button"
          className="dropdown-item"
          role="menuitem"
          key={item.label}
          onClick={() => {
            onClose(true);
            item.onSelect();
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
