// contoh payload tabel link buat test. Bentuknya HARUS sama kayak
// app/services/entry_table_service.py:build_entry_table_payload (dijaga test Python test_entry_table_api.py)

export function makeRow(id, overrides = {}) {
  return {
    id,
    title: `Link ${id}`,
    detail_url: `/entries/${id}?back=/entries/?run%3D1%23daftar_link`,
    category_label: "Web › SAP",
    category_url: "/categories/2",
    access_text: `https://link${id}.spindo.com`,
    description: "",
    visibility: "public",
    visibility_label: "Public",
    status: "unknown",
    status_label: "Belum dicek",
    status_title: "",
    attachment_count: 0,
    owner_name: "User Login",
    created_text: "05 Okt 2026, 14:30 WIB",
    ...overrides,
  };
}

const COLUMN_LIST = [
  { key: "title", label: "Judul", width: 180, is_hideable: false, is_sortable: true, filter: { key: "title", kind: "text", value: "", option_list: [], is_locked: false } },
  { key: "category", label: "Kategori", width: 110, is_hideable: true, is_sortable: true, filter: null },
  { key: "access", label: "URL / Address", width: 170, is_hideable: true, is_sortable: true, filter: null },
  { key: "visibility", label: "Visibilitas", width: 90, is_hideable: true, is_sortable: true, filter: { key: "visibility", kind: "choice", value: "", option_list: [["public", "Public"], ["private", "Private"]], is_locked: false } },
  { key: "owner", label: "Dibuat Oleh", width: 110, is_hideable: true, is_sortable: true, filter: null },
];

export function makePayload(overrides = {}) {
  const rows = overrides.rows || [makeRow(1), makeRow(2), makeRow(3)];
  return {
    table_key: "entry",
    api_url: "/entries/table-data",
    page_url: "/entries/",
    layout_url: "/settings/table-layout",
    anchor: "daftar_link",
    columns: COLUMN_LIST.map((column) => ({ is_hidden: false, sort_state: null, next_sort: column.key, ...column })),
    layout: { hidden_list: [], width_dict: {} },
    default_layout: { hidden_list: [], width_dict: {} },
    default_width_dict: { title: 180, category: 110, access: 170, visibility: 90, owner: 110 },
    sort: "",
    query: { run: ["1"] },
    page: 1,
    pages: 1,
    total: rows.length,
    page_list: [1],
    rows,
    is_filtered: false,
    heading: { icon: "link", text: `Seluruh link: ${rows.length} data`, count_text: null },
    empty: null,
    export_url: "/export?run=1",
    ...overrides,
  };
}

// balasan fetch palsu ala API ALR ({ is_success, message, data })
export function jsonResponse(data, status = 200, extra = {}) {
  const isSuccess = status >= 200 && status < 300;
  return {
    ok: isSuccess,
    status,
    redirected: false,
    json: async () => (isSuccess ? { is_success: true, message: "Berhasil", data, error_list: [] }
      : { is_success: false, message: extra.message || "Gagal", data: null, error_list: [] }),
    ...extra,
  };
}
