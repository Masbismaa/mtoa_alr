// kepala tabel ala ALV: judul kolom diklik buat ngurutin, garis di kanan judul ditarik buat ngatur lebar,
// baris kedua = filter per kolom (nyambung ke isian Kriteria Pencarian yg sama).
import { useState } from "react";
import Icon from "../shared/Icon.jsx";
import { isPlainClick } from "../shared/events.js";
import { clampWidth } from "./useColumnLayout.js";

const KEYBOARD_STEP = 16;
const LOCKED_FILTER_TITLE = "More than one value, change it via Selection Criteria";

// garis geser lebar kolom: mouse/jari ditarik, atau fokus + panah kiri/kanan
function ResizeHandle({ label, onResize, onResizeStateChange }) {
  function handlePointerDown(event) {
    event.preventDefault();
    const handleEl = event.currentTarget;
    const headEl = handleEl.closest("th");
    const startX = event.clientX;
    const startWidth = headEl.getBoundingClientRect().width;
    let currentWidth = startWidth;
    if (handleEl.setPointerCapture) handleEl.setPointerCapture(event.pointerId);
    onResizeStateChange(true);

    function handleMove(moveEvent) {
      currentWidth = clampWidth(startWidth + moveEvent.clientX - startX);
      onResize(currentWidth, false);
    }
    function handleUp() {
      handleEl.removeEventListener("pointermove", handleMove);
      handleEl.removeEventListener("pointerup", handleUp);
      handleEl.removeEventListener("pointercancel", handleUp);
      onResizeStateChange(false);
      // cuma disimpen kalau lebarnya beneran berubah
      if (currentWidth !== Math.round(startWidth)) onResize(currentWidth, true);
    }
    handleEl.addEventListener("pointermove", handleMove);
    handleEl.addEventListener("pointerup", handleUp);
    handleEl.addEventListener("pointercancel", handleUp);
  }

  function handleKeyDown(event) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const headEl = event.currentTarget.closest("th");
    const step = event.key === "ArrowRight" ? KEYBOARD_STEP : -KEYBOARD_STEP;
    onResize(clampWidth(headEl.getBoundingClientRect().width + step), true);
  }

  return (
    <span
      className="table-resize"
      tabIndex={0}
      role="separator"
      aria-orientation="vertical"
      aria-label={`Width of column ${label} (left/right arrows)`}
      onPointerDown={handlePointerDown}
      onKeyDown={handleKeyDown}
    />
  );
}

function SortIcon({ sortState }) {
  if (sortState === "desc") return <Icon name="arrow_down" className="col-sort-icon" />;
  if (sortState === "asc") return <Icon name="arrow_up" className="col-sort-icon" />;
  return <Icon name="selector" className="col-sort-icon" />;
}

// satu isian filter kolom. Teks: Enter = terapin. Pilihan: ganti = langsung terapin
function ColumnFilter({ column, value, onValueChange, onApply }) {
  const filter = column.filter;
  const lockedProps = filter.is_locked ? { disabled: true, title: LOCKED_FILTER_TITLE } : {};
  if (filter.kind === "choice") {
    return (
      <select
        className="form-select form-select-sm"
        aria-label={`Filter ${column.label}`}
        value={filter.is_locked ? "" : value}
        onChange={(event) => {
          onValueChange(filter.key, event.target.value);
          onApply(filter.key, event.target.value);
        }}
        {...lockedProps}
      >
        <option value="">{filter.is_locked ? "(multiple)" : "All"}</option>
        {filter.option_list.map(([optionValue, optionLabel]) => (
          <option value={optionValue} key={optionValue}>{optionLabel}</option>
        ))}
      </select>
    );
  }
  return (
    <input
      type="search"
      className="form-control form-control-sm"
      aria-label={`Filter ${column.label}`}
      placeholder={filter.is_locked ? "(multiple)" : "Filter… (use *)"}
      maxLength={100}
      autoComplete="off"
      value={filter.is_locked ? "" : value}
      onChange={(event) => onValueChange(filter.key, event.target.value)}
      onKeyDown={(event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        onApply(filter.key, event.currentTarget.value);
      }}
      {...lockedProps}
    />
  );
}

// nilai awal isian filter = yg lagi kepake di server
function readFilterValueDict(columns) {
  const valueDict = {};
  columns.forEach((column) => {
    if (column.filter) valueDict[column.filter.key] = column.filter.value;
  });
  return valueDict;
}

// kolom centang paling kiri ala ALV (hapus banyak, admin). selection = null kalau ga dipake
function SelectAllCell({ selection }) {
  return (
    <th className="cell-select">
      <input
        type="checkbox"
        className="form-check-input m-0"
        aria-label="Select all rows on this page"
        checked={selection.isAllChecked}
        disabled={selection.isDisabled}
        ref={(inputEl) => { if (inputEl) inputEl.indeterminate = selection.isSomeChecked; }}
        onChange={selection.onToggleAll}
      />
    </th>
  );
}

export default function TableHead({
  columns, getWidth, onResize, onResizeStateChange, buildSortHref, onSort, onFilterApply, selection = null,
  isFilterShown = true, applyFiltersRef = null,
}) {
  // isian filter yg lagi diketik (belum diterapin). TableHead di-render ulang dgn key baru tiap data ganti,
  // jadi isiannya selalu mulai dari nilai yg dipake server
  const [filterValueDict, setFilterValueDict] = useState(() => readFilterValueDict(columns));
  const hasFilter = columns.some((column) => column.filter);

  function handleValueChange(key, value) {
    setFilterValueDict((current) => ({ ...current, [key]: value }));
  }

  // tombol "Apply column filters" di toolbar ALV: terapin semua isian teks yg ga dikunci sekaligus
  function applyAllFilters() {
    const changeDict = {};
    columns.forEach((column) => {
      if (column.filter && !column.filter.is_locked) changeDict[column.filter.key] = filterValueDict[column.filter.key] || "";
    });
    onFilterApply(changeDict);
  }
  if (applyFiltersRef) applyFiltersRef.current = applyAllFilters;

  return (
    <thead>
      <tr>
        {selection && <SelectAllCell selection={selection} />}
        {columns.map((column) => (
          <th
            key={column.key}
            style={{ width: getWidth(column) + "px" }}
            aria-sort={column.sort_state ? (column.sort_state === "desc" ? "descending" : "ascending") : undefined}
          >
            {column.is_sortable ? (
              <a
                href={buildSortHref(column.next_sort)}
                className={"col-sort" + (column.sort_state ? " is-active" : "")}
                title={`Sort by ${column.label}`}
                onClick={(event) => {
                  if (!isPlainClick(event)) return;
                  event.preventDefault();
                  onSort(column.next_sort);
                }}
              >
                <span className="col-sort-label">{column.label}</span>
                <SortIcon sortState={column.sort_state} />
              </a>
            ) : (
              <span className="col-sort-label">{column.label}</span>
            )}
            <ResizeHandle
              label={column.label}
              onResize={(width, isSaved) => onResize(column.key, width, isSaved)}
              onResizeStateChange={onResizeStateChange}
            />
          </th>
        ))}
      </tr>
      {hasFilter && isFilterShown && (
        <tr className="table-filter-row">
          {selection && <th className="cell-select" />}
          {columns.map((column) => (
            <th key={column.key}>
              {column.filter && (
                <ColumnFilter
                  column={column}
                  value={filterValueDict[column.filter.key] || ""}
                  onValueChange={handleValueChange}
                  onApply={(key, value) => onFilterApply({ [key]: value })}
                />
              )}
            </th>
          ))}
        </tr>
      )}
    </thead>
  );
}
