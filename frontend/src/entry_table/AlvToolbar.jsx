// toolbar ikon ala ALV SAP di atas tabel: Details | Sort naik/turun | Filter | Export, Layout (kolom) | hapus banyak.
// Sort pake kolom yg lagi dipilih (klik sel / judul kolom), Details buka baris yg lagi aktif.
import Icon from "../shared/Icon.jsx";

function ToolButton({ icon, label, title, isDisabled = false, isPressed, onClick }) {
  return (
    <button
      type="button"
      className="btn btn-icon alv-tool"
      aria-label={label}
      title={title || label}
      disabled={isDisabled}
      aria-pressed={isPressed}
      onClick={onClick}
    >
      <Icon name={icon} />
    </button>
  );
}

export default function AlvToolbar({
  activeRow,
  onOpenRow,
  sortColumn,
  onSort,
  isFilterShown,
  onToggleFilter,
  onApplyFilters,
  hasFilter,
  exportUrl,
  columnMenu,
  bulkDelete,
  countText,
}) {
  const sortTitle = sortColumn ? ` by ${sortColumn.label}` : " (click a column first)";
  return (
    <div className="alv-toolbar" role="toolbar" aria-label="List toolbar">
      <ToolButton
        icon="find"
        label="Details"
        title={activeRow ? `Details: ${activeRow.title} (Enter)` : "Details (select a row first)"}
        isDisabled={!activeRow}
        onClick={() => onOpenRow(activeRow)}
      />
      <span className="alv-divider" aria-hidden="true" />
      <ToolButton icon="arrow_up" label="Sort ascending" title={"Sort ascending" + sortTitle} isDisabled={!sortColumn} onClick={() => onSort(sortColumn.key)} />
      <ToolButton icon="arrow_down" label="Sort descending" title={"Sort descending" + sortTitle} isDisabled={!sortColumn} onClick={() => onSort("-" + sortColumn.key)} />
      {hasFilter && (
        <>
          <span className="alv-divider" aria-hidden="true" />
          <ToolButton icon="list" label="Filter row" title="Show / hide the filter row" isPressed={isFilterShown} onClick={onToggleFilter} />
          <ToolButton icon="search" label="Apply column filters" isDisabled={!isFilterShown} onClick={onApplyFilters} />
        </>
      )}
      <span className="alv-divider" aria-hidden="true" />
      {exportUrl && (
        <a href={exportUrl} className="btn btn-icon alv-tool" aria-label="Export Excel" title="Export to Excel">
          <Icon name="download" />
        </a>
      )}
      {columnMenu}
      {bulkDelete}
      {countText && <span className="alv-count">{countText}</span>}
    </div>
  );
}
