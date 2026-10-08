// titik masuk tabel link: cari kartu ber-atribut data-entry-table (components/entry_table.html),
// baca data awal dari atribut itu, terus pasang komponen React di dalamnya.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import ErrorBoundary from "../shared/ErrorBoundary.jsx";
import EntryTable from "./EntryTable.jsx";

export function mountEntryTable(containerEl) {
  let initialPayload;
  try {
    initialPayload = JSON.parse(containerEl.dataset.entryTable);
  } catch (error) {
    console.error("data-entry-table bukan JSON yg valid", error);
    containerEl.textContent = "Data tabel rusak, muat ulang halaman.";
    return null;
  }
  const root = createRoot(containerEl);
  root.render(
    <StrictMode>
      <ErrorBoundary>
        <EntryTable initialPayload={initialPayload} />
      </ErrorBoundary>
    </StrictMode>,
  );
  return root;
}

document.querySelectorAll("[data-entry-table]").forEach(mountEntryTable);
