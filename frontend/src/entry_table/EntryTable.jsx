// tabel link ala ALV (Daftar Link & isi kategori). Isi kartu #daftar_link: judul, tombol Export/Kolom, tabel, navigasi halaman.
//
// Alur data:
//   payload awal (ditempel server di data-entry-table) -> tampil
//   user ngurutin / filter kolom / pindah halaman -> load(kriteria, halaman) -> API -> payload baru -> tampil
// Semua yg nentuin ISI tabel (filter, hak akses, label, URL) ada di server: app/services/entry_table_service.py
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Icon from "../shared/Icon.jsx";
import { postJson } from "../shared/api.js";
import { copyText } from "../shared/clipboard.js";
import { isInteractiveTarget } from "../shared/events.js";
import { navigateTo, reloadPage } from "../shared/navigation.js";
import { buildUrl, withQueryValue } from "../shared/queryString.js";
import { showStatus } from "../shared/statusBar.js";
import ColumnMenu from "./ColumnMenu.jsx";
import EmptyState from "./EmptyState.jsx";
import Pagination from "./Pagination.jsx";
import RowContextMenu from "./RowContextMenu.jsx";
import TableHead from "./TableHead.jsx";
import { getColumnRenderer } from "./columns.jsx";
import useActiveRow from "./useActiveRow.js";
import useColumnLayout from "./useColumnLayout.js";
import useTableData, { HISTORY_NONE } from "./useTableData.js";

const COPY_PREVIEW_LENGTH = 60;

async function copyWithStatus(text) {
  try {
    await copyText(text);
    const preview = text.length > COPY_PREVIEW_LENGTH ? text.slice(0, COPY_PREVIEW_LENGTH) + "…" : text;
    showStatus("Copied: " + preview, "success", false);
  } catch (error) {
    showStatus("Copy failed; the browser did not allow it", "danger");
  }
}

function openRow(row) {
  navigateTo(row.detail_url);
}

export default function EntryTable({ initialPayload }) {
  const { payload, isLoading, error, load } = useTableData(initialPayload);
  const layout = useColumnLayout({
    tableKey: initialPayload.table_key,
    layoutUrl: initialPayload.layout_url,
    initialLayout: initialPayload.layout,
    defaultLayout: initialPayload.default_layout,
    defaultWidthDict: initialPayload.default_width_dict,
  });
  const { activeIndex, activate, getTabIndex, setRowRef } = useActiveRow(payload.rows);
  const [isResizing, setIsResizing] = useState(false);
  // menu klik kanan yg lagi kebuka: { rowIndex, columnKey, x, y }
  const [menu, setMenu] = useState(null);
  const menuRowIndexRef = useRef(null);
  const headingRef = useRef(null);
  const rowElList = useRef([]);
  // hapus banyak (admin): id baris yg dicentang. Isi tabel ganti -> centangan dikosongin
  const [selectedIdSet, setSelectedIdSet] = useState(() => new Set());
  const isBulkDelete = Boolean(payload.bulk_delete_url);
  const deletableIdList = payload.rows.filter((row) => row.can_delete).map((row) => row.id);
  useEffect(() => { setSelectedIdSet(new Set()); }, [payload.rows]);

  const visibleColumns = payload.columns.filter((column) => !layout.isHidden(column));
  const buildPageHref = (query, page) => buildUrl(payload.page_url, query, page, payload.anchor);

  // AKSI YG NGAMBIL DATA BARU
  function handleSort(nextSort) {
    load({ ...payload.query, sort: [nextSort] }, 1);
  }

  // changeDict = { key filter: nilai baru }, nilai kosong = filternya dihapus. Halaman balik ke 1
  function handleFilterApply(changeDict) {
    let nextQuery = payload.query;
    Object.entries(changeDict).forEach(([key, value]) => {
      nextQuery = withQueryValue(nextQuery, key, value);
    });
    load(nextQuery, 1);
  }

  // pindah halaman: abis datanya dateng, fokus & layar ke judul tabel (tombol halaman yg diklik bisa aja ilang)
  async function handlePageChange(page) {
    const data = await load(payload.query, page);
    if (!data || !headingRef.current) return;
    headingRef.current.focus({ preventScroll: true });
    if (headingRef.current.getBoundingClientRect().top < 0) headingRef.current.scrollIntoView({ block: "start" });
  }

  // HAPUS BANYAK
  function toggleRowSelection(rowId) {
    setSelectedIdSet((current) => {
      const next = new Set(current);
      if (next.has(rowId)) next.delete(rowId);
      else next.add(rowId);
      return next;
    });
  }

  function toggleAllSelection() {
    const isAllChecked = deletableIdList.length > 0 && deletableIdList.every((rowId) => selectedIdSet.has(rowId));
    setSelectedIdSet(isAllChecked ? new Set() : new Set(deletableIdList));
  }

  async function handleBulkDelete() {
    const idList = [...selectedIdSet];
    const message = `${idList.length} selected links will be permanently deleted, including their attachments.`;
    const isConfirmed = window.AlrConfirm
      ? await window.AlrConfirm.open({ title: "Delete selected links?", message, okLabel: "Yes, delete" })
      : window.confirm(message);
    if (!isConfirmed) return;
    try {
      const data = await postJson(payload.bulk_delete_url, { entry_id_list: idList });
      showStatus(`${data.deleted_count} links deleted`, "success");
      load(payload.query, payload.page, HISTORY_NONE);
    } catch (deleteError) {
      showStatus(deleteError.message, "danger");
    }
  }

  // MENU KLIK KANAN
  // isi tabel ganti -> menu ditutup (nomor barisnya udah nunjuk data lain)
  useEffect(() => {
    menuRowIndexRef.current = null;
    setMenu(null);
  }, [payload.rows]);

  // isRefocus = fokus balik ke baris asal (ditutup lewat keyboard / abis milih)
  const closeMenu = useCallback((isRefocus) => {
    const rowIndex = menuRowIndexRef.current;
    menuRowIndexRef.current = null;
    setMenu(null);
    if (isRefocus && rowIndex !== null && rowElList.current[rowIndex]) rowElList.current[rowIndex].focus();
  }, []);

  function openMenu(nextMenu) {
    menuRowIndexRef.current = nextMenu.rowIndex;
    setMenu(nextMenu);
  }

  function buildMenuItemList(row, columnKey) {
    const itemList = [{ label: "Open", onSelect: () => openRow(row) }];
    const column = visibleColumns.find((item) => item.key === columnKey);
    if (column) {
      itemList.push({ label: "Copy " + column.label, onSelect: () => copyWithStatus(getColumnRenderer(column.key).copyValue(row)) });
    }
    itemList.push({
      label: "Copy row",
      onSelect: () => copyWithStatus(visibleColumns.map((item) => getColumnRenderer(item.key).copyValue(row)).join("\t")),
    });
    return itemList;
  }

  function openMenuAtRow(index) {
    const rowEl = rowElList.current[index];
    const rect = rowEl.getBoundingClientRect();
    openMenu({ rowIndex: index, columnKey: visibleColumns.length ? visibleColumns[0].key : null, x: rect.left + 24, y: rect.bottom });
  }

  // KEYBOARD & MOUSE DI BARIS
  function handleRowKeyDown(event, index) {
    // lagi fokus di link/tombol di dalem baris: biarin jalan normal
    if (event.target !== event.currentTarget) return;
    const isMenuKey = event.key === "ContextMenu" || (event.shiftKey && event.key === "F10");
    if (event.key === "ArrowDown") activate(index + 1, true);
    else if (event.key === "ArrowUp") activate(index - 1, true);
    else if (event.key === "Home") activate(0, true);
    else if (event.key === "End") activate(payload.rows.length - 1, true);
    else if (event.key === "Enter") openRow(payload.rows[index]);
    else if (isMenuKey) openMenuAtRow(index);
    else return;
    event.preventDefault();
  }

  function handleRowContextMenu(event, index) {
    // klik kanan di link: menu bawaan browser (buka di tab baru, salin link)
    if (isInteractiveTarget(event.target)) return;
    event.preventDefault();
    activate(index, true, false);
    const cellEl = event.target.closest("td");
    openMenu({ rowIndex: index, columnKey: cellEl ? cellEl.dataset.column : null, x: event.clientX, y: event.clientY });
  }

  function setRowElement(index) {
    const setActiveRowRef = setRowRef(index);
    return (element) => {
      rowElList.current[index] = element;
      setActiveRowRef(element);
    };
  }

  const hasRows = payload.rows.length > 0;
  // ga ada data sama sekali -> cukup pesan kosong. Kosong gara-gara filter -> kepala tabel tetep ada biar filternya bisa dihapus
  const isTableShown = hasRows || payload.is_filtered;
  const heading = payload.heading;

  return (
    <>
      <div className="card-header">
        <h3 className="card-title" ref={headingRef} tabIndex={-1} aria-live="polite">
          <Icon name={heading.icon} /> {heading.text}
        </h3>
        <div className="card-actions">
          {isBulkDelete && (
            <button
              type="button"
              className="btn btn-sm btn-ghost-danger"
              disabled={selectedIdSet.size === 0}
              data-fkey="Shift+F2"
              title="Delete the selected links (Shift+F2)"
              onClick={handleBulkDelete}
            >
              <Icon name="trash" /> Delete selected{selectedIdSet.size ? ` (${selectedIdSet.size})` : ""}
            </button>
          )}
          {payload.export_url && (
            <a href={payload.export_url} className="btn btn-sm"><Icon name="download" /> Export Excel</a>
          )}
          {isTableShown && (
            <ColumnMenu
              tableKey={payload.table_key}
              columns={payload.columns}
              isHidden={layout.isHidden}
              onToggle={layout.setHidden}
              onReset={layout.reset}
              saveStatus={layout.saveStatus}
            />
          )}
          {heading.count_text && <span className="badge bg-secondary-lt">{heading.count_text}</span>}
        </div>
      </div>

      {error && (
        <div className="alert alert-danger m-3" role="alert">
          <Icon name="alert_triangle" /> {error.message}
          {error.isSessionExpired && (
            <> <button type="button" className="btn btn-sm ms-2" onClick={reloadPage}>Reload</button></>
          )}
        </div>
      )}

      {isTableShown ? (
        <div className="table-responsive">
          <table
            className={"table table-vcenter card-table table-stack data-table" + (isResizing ? " is-resizing" : "")}
            aria-busy={isLoading ? "true" : "false"}
          >
            {/* key baru tiap data ganti -> isian filter kolom balik ke nilai yg dipake server */}
            <TableHead
              key={JSON.stringify(payload.query)}
              columns={visibleColumns}
              getWidth={layout.getWidth}
              onResize={layout.setWidth}
              onResizeStateChange={setIsResizing}
              buildSortHref={(nextSort) => buildPageHref({ ...payload.query, sort: [nextSort] }, 1)}
              onSort={handleSort}
              onFilterApply={handleFilterApply}
              selection={isBulkDelete ? {
                isAllChecked: deletableIdList.length > 0 && deletableIdList.every((rowId) => selectedIdSet.has(rowId)),
                isSomeChecked: selectedIdSet.size > 0 && selectedIdSet.size < deletableIdList.length,
                isDisabled: deletableIdList.length === 0,
                onToggleAll: toggleAllSelection,
              } : null}
            />
            <tbody aria-label="Data rows, use the up/down arrows">
              {payload.rows.map((row, index) => (
                <tr
                  key={row.id}
                  ref={setRowElement(index)}
                  data-row-url={row.detail_url}
                  className={index === activeIndex ? "is-active" : undefined}
                  tabIndex={getTabIndex(index)}
                  onClick={(event) => activate(index, !isInteractiveTarget(event.target), false)}
                  onFocus={(event) => { if (event.target === event.currentTarget) activate(index, false); }}
                  onDoubleClick={(event) => { if (!isInteractiveTarget(event.target)) openRow(row); }}
                  onKeyDown={(event) => handleRowKeyDown(event, index)}
                  onContextMenu={(event) => handleRowContextMenu(event, index)}
                >
                  {isBulkDelete && (
                    <td className="cell-select">
                      <input
                        type="checkbox"
                        className="form-check-input m-0"
                        aria-label={`Select ${row.title}`}
                        title={row.can_delete ? undefined : "You can't delete this link"}
                        checked={selectedIdSet.has(row.id)}
                        disabled={!row.can_delete}
                        onChange={() => toggleRowSelection(row.id)}
                      />
                    </td>
                  )}
                  {visibleColumns.map((column) => {
                    const renderer = getColumnRenderer(column.key);
                    return (
                      <td
                        key={column.key}
                        data-column={column.key}
                        data-label={column.label}
                        className={renderer.className}
                        title={renderer.title ? renderer.title(row) : undefined}
                      >
                        {renderer.render(row)}
                      </td>
                    );
                  })}
                  <td className="cell-action">
                    <a href={row.detail_url} className="btn btn-sm"><Icon name="eye" /> View</a>
                  </td>
                </tr>
              ))}
              {!hasRows && payload.empty && (
                <tr>
                  <td colSpan={visibleColumns.length + (isBulkDelete ? 2 : 1)}><EmptyState empty={payload.empty} /></td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        payload.empty && <EmptyState empty={payload.empty} />
      )}

      <Pagination
        page={payload.page}
        pages={payload.pages}
        pageList={payload.page_list}
        buildPageHref={(page) => buildPageHref(payload.query, page)}
        onPageChange={handlePageChange}
      />

      {/* menu klik kanan dirender langsung di <body> (portal): kartu punya animasi transform (app-fade-up),
          yg bikin position: fixed di dalemnya dihitung dari kartu, bukan dari layar -> menunya nongol di tempat lain */}
      {menu && payload.rows[menu.rowIndex] && createPortal(
        <RowContextMenu
          x={menu.x}
          y={menu.y}
          itemList={buildMenuItemList(payload.rows[menu.rowIndex], menu.columnKey)}
          onClose={closeMenu}
        />,
        document.body,
      )}
    </>
  );
}
