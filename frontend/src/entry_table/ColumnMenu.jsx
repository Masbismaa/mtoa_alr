// tombol "Kolom" di kepala kartu: centang kolom yg mau tampil + balikin layout awal.
// dropdown-nya dipegang React sendiri (bukan data-bs-toggle Bootstrap), soalnya Bootstrap ngubah class elemen
// yg dirender React -> menu bisa ketutup sendiri tiap tabel dirender ulang.
// Esc (di mana aja selama menu kebuka) & klik di luar -> tutup.
import { useEffect, useRef, useState } from "react";
import Icon from "../shared/Icon.jsx";

export default function ColumnMenu({ tableKey, columns, isHidden, onToggle, onReset, saveStatus }) {
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef(null);
  const buttonRef = useRef(null);

  // klik di luar menu / Esc -> tutup
  useEffect(() => {
    if (!isOpen) return undefined;
    function handlePointerDown(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) setIsOpen(false);
    }
    function handleKeyDown(event) {
      if (event.key !== "Escape") return;
      setIsOpen(false);
      if (buttonRef.current) buttonRef.current.focus();
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div className="dropdown" data-table-menu={tableKey} ref={wrapperRef}>
      <button
        type="button"
        className="btn btn-sm"
        aria-expanded={isOpen}
        title="Atur kolom tabel"
        ref={buttonRef}
        onClick={() => setIsOpen((open) => !open)}
      >
        <Icon name="columns" /> Kolom
      </button>
      {isOpen && (
        // class app-menu, BUKAN dropdown-menu: lihat komentar .app-menu di static/css/components/table.css
        <div className="app-menu app-menu-end table-column-menu">
          <span className="dropdown-header">Tampilkan kolom</span>
          {columns.filter((column) => column.is_hideable).map((column) => (
            <label className="dropdown-item" key={column.key}>
              <input
                type="checkbox"
                className="form-check-input m-0 me-2"
                checked={!isHidden(column)}
                onChange={(event) => onToggle(column.key, !event.target.checked)}
              />
              {column.label}
            </label>
          ))}
          <div className="dropdown-divider" />
          <button type="button" className="dropdown-item" onClick={onReset}>
            <Icon name="refresh" className="dropdown-item-icon" /> Kembalikan layout awal
          </button>
          <div className={"dropdown-item-text small " + (saveStatus.isError ? "text-danger" : "text-secondary")} role="status">
            {saveStatus.text}
          </div>
        </div>
      )}
    </div>
  );
}
