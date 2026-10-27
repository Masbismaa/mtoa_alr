// test perilaku tabel link: ngurutin, filter, pindah halaman, request balapan, layout, keyboard, menu klik kanan, error
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { jsonResponse, makePayload, makeRow } from "../test/makePayload.js";
import EntryTable from "./EntryTable.jsx";
import { QUERY_CHANGED_EVENT } from "./useTableData.js";

vi.mock("../shared/navigation.js", () => ({ navigateTo: vi.fn(), reloadPage: vi.fn() }));
vi.mock("../shared/clipboard.js", () => ({ copyText: vi.fn(async () => {}) }));
const { navigateTo } = await import("../shared/navigation.js");
const { copyText } = await import("../shared/clipboard.js");

// fetch palsu yg balesannya bisa diatur urutannya (buat ngetes request balapan)
function mockFetchSequence() {
  const pendingList = [];
  const fetchMock = vi.fn((url) => new Promise((resolve, reject) => pendingList.push({ url, resolve, reject })));
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, pendingList };
}

function getRowList() {
  return within(screen.getByRole("table")).getAllByRole("row").filter((rowEl) => rowEl.dataset.rowUrl);
}

beforeEach(() => {
  window.history.replaceState(null, "", "/entries/?run=1#daftar_link");
  const metaEl = document.createElement("meta");
  metaEl.name = "csrf-token";
  metaEl.content = "token-csrf";
  document.head.append(metaEl);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("tampilan awal", () => {
  it("nampilin baris dari payload server tanpa request tambahan", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<EntryTable initialPayload={makePayload()} />);
    expect(screen.getByText("All links: 3")).toBeInTheDocument();
    expect(getRowList()).toHaveLength(3);
    expect(screen.getByRole("link", { name: /Export Excel/ })).toHaveAttribute("href", "/export?run=1");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("judul kolom tetep link beneran (Ctrl+klik buka tab baru)", () => {
    render(<EntryTable initialPayload={makePayload()} />);
    expect(screen.getByTitle("Sort by Title")).toHaveAttribute("href", "/entries/?run=1&sort=title#daftar_link");
  });

  it("teks dari server ditampilin sebagai teks, bukan HTML (anti XSS)", () => {
    const row = makeRow(9, { title: '<img src=x onerror="alert(1)">' });
    const { container } = render(<EntryTable initialPayload={makePayload({ rows: [row] })} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument();
  });

  it("hasil filter kosong: kepala tabel + filter kolom tetep ada biar filternya bisa dihapus", () => {
    const payload = makePayload({
      rows: [], total: 0, pages: 0, page_list: [], is_filtered: true, export_url: null,
      heading: { icon: "search", text: "Search results: 0", count_text: null },
      empty: { icon: "search", title: "No results.", subtitle: "Coba ubah kriteria.", action: null },
    });
    render(<EntryTable initialPayload={payload} />);
    expect(screen.getByRole("searchbox", { name: "Filter Title" })).toBeInTheDocument();
    expect(screen.getByText("No results.")).toBeInTheDocument();
  });

  it("belum ada data sama sekali: cuma pesan kosong + tombol tambah", () => {
    const payload = makePayload({
      rows: [], total: 0, pages: 0, page_list: [], export_url: null,
      empty: { icon: "link", title: "No links yet", subtitle: "Add one.", action: { url: "/entries/new", label: "Add Link", icon: "plus", is_primary: true } },
    });
    render(<EntryTable initialPayload={payload} />);
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByRole("link", { name: /Add Link/ })).toHaveAttribute("href", "/entries/new");
  });
});

describe("ngambil data baru", () => {
  it("klik judul kolom -> API dgn urutan baru, URL browser & panel kriteria ikut ganti", async () => {
    const { pendingList } = mockFetchSequence();
    const queryEventList = [];
    const listener = (event) => queryEventList.push(event.detail.query);
    document.addEventListener(QUERY_CHANGED_EVENT, listener);
    render(<EntryTable initialPayload={makePayload()} />);

    await userEvent.click(screen.getByTitle("Sort by Title"));
    expect(pendingList[0].url).toBe("/entries/table-data?run=1&sort=title");
    expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true");

    const sortedPayload = makePayload({ sort: "title", query: { run: ["1"], sort: ["title"] }, rows: [makeRow(3), makeRow(1)] });
    await act(async () => pendingList[0].resolve(jsonResponse(sortedPayload)));

    expect(getRowList().map((rowEl) => rowEl.dataset.rowUrl)).toEqual([makeRow(3).detail_url, makeRow(1).detail_url]);
    expect(window.location.pathname + window.location.search).toBe("/entries/?run=1&sort=title");
    expect(queryEventList).toEqual([{ run: ["1"], sort: ["title"] }]);
    expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "false");
    document.removeEventListener(QUERY_CHANGED_EVENT, listener);
  });

  it("klik cepet dua kali: cuma hasil request terakhir yg dipake", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload()} />);

    await userEvent.click(screen.getByTitle("Sort by Title"));
    await userEvent.click(screen.getByTitle("Sort by Created By"));
    // request pertama dibatalin
    const abortError = new DOMException("dibatalin", "AbortError");
    await act(async () => pendingList[0].reject(abortError));
    await act(async () => pendingList[1].resolve(jsonResponse(makePayload({ rows: [makeRow(7)] }))));

    expect(getRowList()).toHaveLength(1);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("filter teks: Enter -> API dgn filter itu, halaman balik ke 1", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload({ page: 3, pages: 5, page_list: [1, 2, 3, 4, 5] })} />);

    const inputEl = screen.getByRole("searchbox", { name: "Filter Title" });
    await userEvent.type(inputEl, "portal*{Enter}");
    expect(pendingList[0].url).toBe("/entries/table-data?run=1&title=portal*");
  });

  it("filter pilihan: ganti pilihan langsung diterapin, kosongin = filternya dibuang", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload({ query: { run: ["1"], visibility: ["public"] } })} />);

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Filter Visibility" }), "");
    expect(pendingList[0].url).toBe("/entries/table-data?run=1");
  });

  it("filter yg isinya lebih dari satu nilai (Multi Selection) dikunci", () => {
    const payload = makePayload();
    payload.columns[0].filter = { ...payload.columns[0].filter, is_locked: true };
    render(<EntryTable initialPayload={payload} />);
    expect(screen.getByRole("searchbox", { name: "Filter Title" })).toBeDisabled();
  });

  it("pindah halaman lewat klik biasa, Ctrl+klik dibiarin ke browser", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload({ pages: 3, page_list: [1, 2, 3] })} />);

    const pageLinkEl = screen.getByRole("link", { name: "2" });
    expect(pageLinkEl).toHaveAttribute("href", "/entries/?run=1&page=2#daftar_link");
    // browser yg buka tab baru; di jsdom navigasinya ditahan biar ga ada peringatan "not implemented"
    const blockNavigation = (event) => event.preventDefault();
    document.addEventListener("click", blockNavigation);
    fireEvent.click(pageLinkEl, { ctrlKey: true });
    document.removeEventListener("click", blockNavigation);
    expect(pendingList).toHaveLength(0);

    await userEvent.click(pageLinkEl);
    expect(pendingList[0].url).toBe("/entries/table-data?run=1&page=2");
  });

  it("tombol Back browser -> data sesuai URL, riwayat ga ditambah", async () => {
    const { pendingList } = mockFetchSequence();
    const pushSpy = vi.spyOn(window.history, "pushState");
    render(<EntryTable initialPayload={makePayload()} />);

    window.history.replaceState(null, "", "/entries/?run=1&sort=-title&page=2");
    act(() => window.dispatchEvent(new PopStateEvent("popstate")));
    expect(pendingList[0].url).toBe("/entries/table-data?run=1&sort=-title&page=2");
    await act(async () => pendingList[0].resolve(jsonResponse(makePayload())));
    expect(pushSpy).not.toHaveBeenCalled();
  });

  it("sesi habis (401): pesan jelas + tombol muat ulang, data lama tetep tampil", async () => {
    const { pendingList } = mockFetchSequence();
    const statusSpy = vi.fn();
    window.AlrStatusBar = { show: statusSpy };
    render(<EntryTable initialPayload={makePayload()} />);

    await userEvent.click(screen.getByTitle("Sort by Title"));
    await act(async () => pendingList[0].resolve(jsonResponse(null, 401, { message: "Your login session expired, reload the page and log in again" })));

    expect(screen.getByRole("alert")).toHaveTextContent("Your login session expired");
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
    expect(getRowList()).toHaveLength(3);
    expect(statusSpy).toHaveBeenCalledWith("Your login session expired, reload the page and log in again", "danger", true);
  });

  it("server ngebales HTML (bukan JSON) -> pesan error, bukan crash", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload()} />);
    await userEvent.click(screen.getByTitle("Sort by Title"));
    await act(async () => pendingList[0].resolve({ ok: true, status: 200, redirected: false, json: async () => { throw new SyntaxError("bukan json"); } }));
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid server response");
  });
});

describe("layout kolom", () => {
  it("sembunyiin kolom -> langsung ilang, disimpen ke akun abis jeda (bawa token CSRF)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn(async () => jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<EntryTable initialPayload={makePayload()} />);

    await user.click(screen.getByRole("button", { name: /Columns/ }));
    await user.click(screen.getByRole("checkbox", { name: "Category" }));
    expect(screen.queryByRole("columnheader", { name: /Category/ })).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();

    await act(async () => vi.advanceTimersByTime(700));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/settings/table-layout");
    expect(options.headers["X-CSRFToken"]).toBe("token-csrf");
    const body = JSON.parse(options.body);
    expect(body).toMatchObject({ table_key: "entry", hidden_list: ["category"], width_dict: {}, sequence: 1 });
    expect(body.client_id).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  });

  it("simpan layout diantre: cuma 1 request jalan, perubahan selama nunggu dikirim sekali (snapshot terbaru) abis itu", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { fetchMock, pendingList } = mockFetchSequence();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<EntryTable initialPayload={makePayload()} />);
    await user.click(screen.getByRole("button", { name: /Columns/ }));

    await user.click(screen.getByRole("checkbox", { name: "Category" }));
    await act(async () => vi.advanceTimersByTime(700));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // 2 perubahan lagi pas request pertama belum dibales -> belum boleh ada request kedua
    await user.click(screen.getByRole("checkbox", { name: "URL / Address" }));
    await act(async () => vi.advanceTimersByTime(700));
    await user.click(screen.getByRole("checkbox", { name: "Category" }));
    await act(async () => vi.advanceTimersByTime(700));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => pendingList[0].resolve(jsonResponse({})));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).hidden_list).toEqual(["access"]);
    await act(async () => pendingList[1].resolve(jsonResponse({})));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("tutup halaman pas simpanan lama masih jalan -> kiriman keepalive bawa nomor urut lebih tinggi (server buang yg lama)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { fetchMock } = mockFetchSequence();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<EntryTable initialPayload={makePayload()} />);
    await user.click(screen.getByRole("button", { name: /Columns/ }));
    await user.click(screen.getByRole("checkbox", { name: "Category" }));
    await act(async () => vi.advanceTimersByTime(700));
    // request pertama belum dibales, user ngubah lagi terus langsung nutup halaman
    await user.click(screen.getByRole("checkbox", { name: "URL / Address" }));
    act(() => window.dispatchEvent(new Event("pagehide")));

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [firstBody, keepaliveBody] = fetchMock.mock.calls.map((call) => JSON.parse(call[1].body));
    expect(fetchMock.mock.calls[1][1].keepalive).toBe(true);
    expect(keepaliveBody.client_id).toBe(firstBody.client_id);
    expect(keepaliveBody.sequence).toBeGreaterThan(firstBody.sequence);
    expect(keepaliveBody.hidden_list).toEqual(["category", "access"]);
  });

  it("layout ga ketimpa balasan API yg bawa layout lama", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload()} />);
    await userEvent.click(screen.getByRole("button", { name: /Columns/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Category" }));
    await userEvent.click(screen.getByTitle("Sort by Title"));
    const sortRequest = pendingList.find((item) => item.url.includes("table-data"));
    await act(async () => sortRequest.resolve(jsonResponse(makePayload({ layout: { hidden_list: [], width_dict: {} } }))));
    expect(screen.queryByRole("columnheader", { name: /Category/ })).toBeNull();
  });

  it("halaman ditutup pas simpanan masih nunggu -> langsung dikirim (keepalive)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn(async () => jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<EntryTable initialPayload={makePayload()} />);
    await user.click(screen.getByRole("button", { name: /Columns/ }));
    await user.click(screen.getByRole("checkbox", { name: "Category" }));

    act(() => window.dispatchEvent(new Event("pagehide")));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1].keepalive).toBe(true);
  });

  it("lebar kolom bisa diatur pake keyboard (panah kanan)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn(async () => jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    render(<EntryTable initialPayload={makePayload()} />);
    const handleEl = screen.getByRole("separator", { name: /Width of column Title/ });
    // jsdom ga ngitung layout, lebar awal dianggep 0 -> dijepit ke lebar minimal + 16
    fireEvent.keyDown(handleEl, { key: "ArrowRight" });
    await act(async () => vi.advanceTimersByTime(700));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).width_dict).toEqual({ title: 60 });
  });
});

describe("keyboard & menu klik kanan", () => {
  it("panah bawah pindah baris aktif, Enter buka detail", async () => {
    render(<EntryTable initialPayload={makePayload()} />);
    const [firstRowEl, secondRowEl] = getRowList();
    expect(firstRowEl).toHaveAttribute("tabindex", "0");
    expect(secondRowEl).toHaveAttribute("tabindex", "-1");

    act(() => firstRowEl.focus());
    fireEvent.keyDown(firstRowEl, { key: "ArrowDown" });
    expect(secondRowEl).toHaveClass("is-active");
    expect(secondRowEl).toHaveFocus();

    fireEvent.keyDown(secondRowEl, { key: "Enter" });
    expect(navigateTo).toHaveBeenCalledWith(makeRow(2).detail_url);
  });

  it("panah bawah pindah baris aktif, Enter buka detail", async () => {
    render(<EntryTable initialPayload={makePayload()}/>);
  })

  it("klik kanan di sel -> Salin nilai sel itu", async () => {
    render(<EntryTable initialPayload={makePayload()} />);
    const cellEl = getRowList()[0].querySelector('td[data-column="category"]');
    fireEvent.contextMenu(cellEl, { clientX: 10, clientY: 10 });

    const menuEl = screen.getByRole("menu", { name: "Row menu" });
    expect(within(menuEl).getAllByRole("menuitem").map((itemEl) => itemEl.textContent)).toEqual(["Open", "Copy Category", "Copy row"]);
    await userEvent.click(within(menuEl).getByRole("menuitem", { name: "Copy Category" }));
    expect(copyText).toHaveBeenCalledWith("Web › SAP");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("Salin baris = kolom yg tampil dipisah tab", async () => {
    render(<EntryTable initialPayload={makePayload()} />);
    fireEvent.contextMenu(getRowList()[0].querySelector('td[data-column="title"]'), { clientX: 10, clientY: 10 });
    await userEvent.click(screen.getByRole("menuitem", { name: "Copy row" }));
    expect(copyText).toHaveBeenCalledWith("Link 1\tWeb › SAP\thttps://link1.spindo.com\tPublic\tUser Login");
  });

  it("Shift+F10 buka menu dari keyboard, Esc nutup & fokus balik ke baris", async () => {
    render(<EntryTable initialPayload={makePayload()} />);
    const firstRowEl = getRowList()[0];
    act(() => firstRowEl.focus());
    fireEvent.keyDown(firstRowEl, { key: "F10", shiftKey: true });
    const menuEl = screen.getByRole("menu");
    expect(within(menuEl).getByRole("menuitem", { name: "Open" })).toHaveFocus();

    fireEvent.keyDown(menuEl, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
    expect(firstRowEl).toHaveFocus();
  });

  it("menu React ga pake class .dropdown-menu (Bootstrap nyegat panah/Esc-nya di fase capture -> TypeError)", async () => {
    // tiruan dataApiKeydownHandler Bootstrap: listener document fase CAPTURE (jalan sebelum React, ga bisa di-stopPropagation)
    const bootstrapHitList = [];
    const bootstrapListener = (event) => {
      if (event.target.closest(".dropdown-menu") && ["ArrowUp", "ArrowDown", "Escape"].includes(event.key)) bootstrapHitList.push(event.key);
    };
    document.addEventListener("keydown", bootstrapListener, true);
    render(<EntryTable initialPayload={makePayload()} />);

    fireEvent.contextMenu(getRowList()[0].querySelector('td[data-column="owner"]'), { clientX: 10, clientY: 10 });
    fireEvent.keyDown(screen.getByRole("menuitem", { name: "Open" }), { key: "ArrowDown" });
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
    await userEvent.click(screen.getByRole("button", { name: /Columns/ }));
    fireEvent.keyDown(screen.getByRole("checkbox", { name: "Category" }), { key: "Escape" });

    expect(bootstrapHitList).toEqual([]);
    expect(screen.queryByRole("menu")).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "Category" })).toBeNull();
    document.removeEventListener("keydown", bootstrapListener, true);
  });

  it("menu klik kanan: event scroll (sisa scroll halus) ga nutup menu, roda mouse nutup", () => {
    render(<EntryTable initialPayload={makePayload()} />);
    fireEvent.contextMenu(getRowList()[0].querySelector('td[data-column="owner"]'), { clientX: 10, clientY: 10 });

    fireEvent.scroll(window);
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.wheel(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("klik kanan di link: menu bawaan browser yg dipake", () => {
    render(<EntryTable initialPayload={makePayload()} />);
    const linkEl = within(getRowList()[0]).getByRole("link", { name: "Link 1" });
    fireEvent.contextMenu(linkEl);
    expect(screen.queryByRole("menu")).toBeNull();
  });
});

describe("hapus banyak (admin)", () => {
  function renderBulkTable() {
    const payload = makePayload({
      bulk_delete_url: "/entries/bulk-delete",
      rows: [makeRow(1, { can_delete: true }), makeRow(2, { can_delete: true }), makeRow(3, { can_delete: false })],
    });
    render(<EntryTable initialPayload={payload} />);
    return payload;
  }

  it("user biasa (tanpa bulk_delete_url) ga dapet kolom centang & tombol hapus", () => {
    render(<EntryTable initialPayload={makePayload()} />);
    expect(screen.queryByRole("checkbox", { name: /Select/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Delete selected/ })).toBeNull();
  });

  it("centang semua cuma milih baris yg boleh dihapus, tombol nunjukin jumlahnya", async () => {
    renderBulkTable();
    const deleteButton = screen.getByRole("button", { name: /Delete selected/ });
    expect(deleteButton).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Select Link 3" })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Select all rows on this page" }));
    expect(deleteButton).toHaveTextContent("Delete selected (2)");
    expect(screen.getByRole("checkbox", { name: "Select Link 3" })).not.toBeChecked();
  });

  it("konfirmasi -> kirim id yg dicentang + token CSRF -> data diambil ulang", async () => {
    renderBulkTable();
    const fetchMock = vi.fn(async (url) => (url === "/entries/bulk-delete"
      ? jsonResponse({ deleted_count: 1 })
      : jsonResponse(makePayload({ rows: [makeRow(2)] }))));
    vi.stubGlobal("fetch", fetchMock);
    window.AlrConfirm = { open: vi.fn(async () => true) };
    await userEvent.click(screen.getByRole("checkbox", { name: "Select Link 1" }));
    await userEvent.click(screen.getByRole("button", { name: /Delete selected/ }));
    await waitFor(() => expect(getRowList()).toHaveLength(1));
    const [, deleteOptions] = fetchMock.mock.calls[0];
    expect(JSON.parse(deleteOptions.body)).toEqual({ entry_id_list: [1] });
    expect(deleteOptions.headers["X-CSRFToken"]).toBe("token-csrf");
    delete window.AlrConfirm;
  });

  it("batal di konfirmasi -> ga ada request", async () => {
    renderBulkTable();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    window.AlrConfirm = { open: vi.fn(async () => false) };
    await userEvent.click(screen.getByRole("checkbox", { name: "Select Link 1" }));
    await userEvent.click(screen.getByRole("button", { name: /Delete selected/ }));
    expect(fetchMock).not.toHaveBeenCalled();
    delete window.AlrConfirm;
  });
});

describe("toolbar ALV", () => {
  it("Sort mati sebelum kolom dipilih; klik sel kolom terus Sort descending -> urut turun kolom itu", async () => {
    const { pendingList } = mockFetchSequence();
    localStorage.removeItem("alr_alv_filter_shown");
    render(<EntryTable initialPayload={makePayload()} />);
    const sortDescButton = screen.getByRole("button", { name: "Sort descending" });
    expect(sortDescButton).toBeDisabled();
    await userEvent.click(within(getRowList()[0]).getAllByRole("cell").find((cellEl) => cellEl.dataset.column === "owner"));
    expect(sortDescButton).toBeEnabled();
    await userEvent.click(sortDescButton);
    expect(pendingList[0].url).toBe("/entries/table-data?run=1&sort=-owner");
  });

  it("Details buka baris yg aktif, kolom View udah ga ada", async () => {
    render(<EntryTable initialPayload={makePayload()} />);
    expect(screen.getByRole("button", { name: "Details" })).toBeDisabled();
    expect(screen.queryByRole("link", { name: /View/ })).toBeNull();
    fireEvent.click(getRowList()[1]);
    await userEvent.click(screen.getByRole("button", { name: "Details" }));
    expect(navigateTo).toHaveBeenLastCalledWith(makePayload().rows[1].detail_url);
  });

  it("tombol Filter row nyembunyiin baris filter, pilihannya diinget", async () => {
    localStorage.removeItem("alr_alv_filter_shown");
    render(<EntryTable initialPayload={makePayload()} />);
    expect(screen.getByRole("searchbox", { name: "Filter Title" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Filter row" }));
    expect(screen.queryByRole("searchbox", { name: "Filter Title" })).toBeNull();
    expect(localStorage.getItem("alr_alv_filter_shown")).toBe("0");
    localStorage.removeItem("alr_alv_filter_shown");
  });

  it("filter yg lagi kepake bikin baris filter tetep tampil walau disembunyiin", () => {
    localStorage.setItem("alr_alv_filter_shown", "0");
    const payload = makePayload();
    payload.columns[0].filter = { ...payload.columns[0].filter, value: "portal*" };
    render(<EntryTable initialPayload={payload} />);
    expect(screen.getByRole("searchbox", { name: "Filter Title" })).toHaveValue("portal*");
    localStorage.removeItem("alr_alv_filter_shown");
  });
});
