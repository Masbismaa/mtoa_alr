// isi sel per kolom tabel link. Kunci = key kolom di app/schemas/table_schema.py (ENTRY_COLUMN_LIST).
//
// Nambah kolom baru:
//   1. table_schema.py   -> daftar kolom (judul, lebar, bisa diurutin/disembunyiin)
//   2. entry_table_service.py:build_entry_row -> data baris yg dibutuhin
//   3. di sini           -> cara nampilin (render) + teks buat menu "Salin" (copyValue)
//   4. access_entry_service.py:ENTRY_SORT_COLUMN_DICT -> kalau kolomnya bisa diurutin
import Icon from "../shared/Icon.jsx";
import CopyButton from "./CopyButton.jsx";

// warna badge, samain dgn app/templates/components/badge.html
const VISIBILITY_BADGE_CLASS = { public: "bg-green-lt", private: "bg-orange-lt" };
const STATUS_BADGE_CLASS = { up: "bg-green-lt", down: "bg-red-lt" };

// potong teks kepanjangan, sama kayak filter Jinja truncate(length, true, "…", 0)
export function truncateText(text, length) {
  return text.length > length ? text.slice(0, length - 1) + "…" : text;
}

const EMPTY_CELL = <span className="text-secondary">-</span>;

export const COLUMN_RENDERER_DICT = {
  title: {
    className: "cell-title",
    render: (row) => (
      <a href={row.detail_url} className="text-reset fw-bold" title={row.title}>{truncateText(row.title, 50)}</a>
    ),
    copyValue: (row) => row.title,
  },
  category: {
    render: (row) => (
      <a href={row.category_url} className="badge bg-secondary-lt text-wrap text-start" title={row.category_label}>
        {row.category_label}
      </a>
    ),
    copyValue: (row) => row.category_label,
  },
  access: {
    render: (row) => (row.access_text ? (
      <div className="cell-copy">
        <code className="cell-url" title={row.access_text}>{row.access_text}</code>
        <CopyButton text={row.access_text} label="Copy link" />
      </div>
    ) : EMPTY_CELL),
    copyValue: (row) => row.access_text,
  },
  description: {
    className: "cell-description text-secondary",
    render: (row) => (row.description
      ? <span title={row.description}>{truncateText(row.description, 60)}</span>
      : "-"),
    copyValue: (row) => row.description,
  },
  visibility: {
    render: (row) => (
      <span className={"badge " + (VISIBILITY_BADGE_CLASS[row.visibility] || "bg-secondary-lt")}>{row.visibility_label}</span>
    ),
    copyValue: (row) => row.visibility_label,
  },
  status: {
    render: (row) => (
      <span className={"badge " + (STATUS_BADGE_CLASS[row.status] || "bg-secondary-lt")} title={row.status_title || undefined}>
        {row.status_label}
      </span>
    ),
    copyValue: (row) => row.status_label,
  },
  attachment: {
    render: (row) => (row.attachment_count ? <><Icon name="paperclip" /> {row.attachment_count}</> : EMPTY_CELL),
    copyValue: (row) => String(row.attachment_count),
  },
  owner: {
    title: (row) => row.owner_name,
    render: (row) => row.owner_name,
    copyValue: (row) => row.owner_name,
  },
  created: {
    className: "text-nowrap text-secondary",
    title: (row) => row.created_text,
    render: (row) => row.created_text,
    copyValue: (row) => row.created_text,
  },
};

// kolom yg belum punya renderer (misal baru ditambah di server tapi lupa di sini): tampil "-" + peringatan di console
export function getColumnRenderer(key) {
  const renderer = COLUMN_RENDERER_DICT[key];
  if (renderer) return renderer;
  console.warn(`Kolom "${key}" belum punya renderer di frontend/src/entry_table/columns.jsx`);
  return { render: () => EMPTY_CELL, copyValue: () => "" };
}
