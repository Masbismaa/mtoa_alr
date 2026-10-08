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
    expect(screen.getByText("Seluruh link: 3 data")).toBeInTheDocument();
    expect(getRowList()).toHaveLength(3);
    expect(screen.getByRole("link", { name: /Export Excel/ })).toHaveAttribute("href", "/export?run=1");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("judul kolom tetep link beneran (Ctrl+klik buka tab baru)", () => {
    render(<EntryTable initialPayload={makePayload()} />);
    expect(screen.getByTitle("Urutkan Judul")).toHaveAttribute("href", "/entries/?run=1&sort=title#daftar_link");
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
      heading: { icon: "search", text: "Hasil pencarian: 0 data", count_text: null },
      empty: { icon: "search", title: "Tidak ada hasil.", subtitle: "Coba ubah kriteria.", action: null },
    });
    render(<EntryTable initialPayload={payload} />);
    expect(screen.getByRole("searchbox", { name: "Filter Judul" })).toBeInTheDocument();
    expect(screen.getByText("Tidak ada hasil.")).toBeInTheDocument();
  });

  it("belum ada data sama sekali: cuma pesan kosong + tombol tambah", () => {
    const payload = makePayload({
      rows: [], total: 0, pages: 0, page_list: [], export_url: null,
      empty: { icon: "link", title: "Belum ada data link", subtitle: "Yuk tambah.", action: { url: "/entries/new", label: "Tambah Link", icon: "plus", is_primary: true } },
    });
    render(<EntryTable initialPayload={payload} />);
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByRole("link", { name: /Tambah Link/ })).toHaveAttribute("href", "/entries/new");
  });
});

describe("ngambil data baru", () => {
  it("klik judul kolom -> API dgn urutan baru, URL browser & panel kriteria ikut ganti", async () => {
    const { pendingList } = mockFetchSequence();
    const queryEventList = [];
    const listener = (event) => queryEventList.push(event.detail.query);
    document.addEventListener(QUERY_CHANGED_EVENT, listener);
    render(<EntryTable initialPayload={makePayload()} />);

    await userEvent.click(screen.getByTitle("Urutkan Judul"));
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

    await userEvent.click(screen.getByTitle("Urutkan Judul"));
    await userEvent.click(screen.getByTitle("Urutkan Dibuat Oleh"));
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

    const inputEl = screen.getByRole("searchbox", { name: "Filter Judul" });
    await userEvent.type(inputEl, "portal*{Enter}");
    expect(pendingList[0].url).toBe("/entries/table-data?run=1&title=portal*");
  });

  it("filter pilihan: ganti pilihan langsung diterapin, kosongin = filternya dibuang", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload({ query: { run: ["1"], visibility: ["public"] } })} />);

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Filter Visibilitas" }), "");
    expect(pendingList[0].url).toBe("/entries/table-data?run=1");
  });

  it("filter yg isinya lebih dari satu nilai (Multi Selection) dikunci", () => {
    const payload = makePayload();
    payload.columns[0].filter = { ...payload.columns[0].filter, is_locked: true };
    render(<EntryTable initialPayload={payload} />);
    expect(screen.getByRole("searchbox", { name: "Filter Judul" })).toBeDisabled();
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

    await userEvent.click(screen.getByTitle("Urutkan Judul"));
    await act(async () => pendingList[0].resolve(jsonResponse(null, 401, { message: "Sesi login habis, muat ulang halaman lalu login lagi" })));

    expect(screen.getByRole("alert")).toHaveTextContent("Sesi login habis");
    expect(screen.getByRole("button", { name: "Muat ulang" })).toBeInTheDocument();
    expect(getRowList()).toHaveLength(3);
    expect(statusSpy).toHaveBeenCalledWith("Sesi login habis, muat ulang halaman lalu login lagi", "danger", true);
  });

  it("server ngebales HTML (bukan JSON) -> pesan error, bukan crash", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload()} />);
    await userEvent.click(screen.getByTitle("Urutkan Judul"));
    await act(async () => pendingList[0].resolve({ ok: true, status: 200, redirected: false, json: async () => { throw new SyntaxError("bukan json"); } }));
    expect(screen.getByRole("alert")).toHaveTextContent("Respon server tidak valid");
  });
});

describe("layout kolom", () => {
  it("sembunyiin kolom -> langsung ilang, disimpen ke akun abis jeda (bawa token CSRF)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn(async () => jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<EntryTable initialPayload={makePayload()} />);

    await user.click(screen.getByRole("button", { name: /Kolom/ }));
    await user.click(screen.getByRole("checkbox", { name: "Kategori" }));
    expect(screen.queryByRole("columnheader", { name: /Kategori/ })).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();

    await act(async () => vi.advanceTimersByTime(700));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/settings/table-layout");
    expect(options.headers["X-CSRFToken"]).toBe("token-csrf");
    expect(JSON.parse(options.body)).toEqual({ table_key: "entry", hidden_list: ["category"], width_dict: {} });
  });

  it("simpan layout diantre: cuma 1 request jalan, perubahan selama nunggu dikirim sekali (snapshot terbaru) abis itu", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { fetchMock, pendingList } = mockFetchSequence();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<EntryTable initialPayload={makePayload()} />);
    await user.click(screen.getByRole("button", { name: /Kolom/ }));

    await user.click(screen.getByRole("checkbox", { name: "Kategori" }));
    await act(async () => vi.advanceTimersByTime(700));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // 2 perubahan lagi pas request pertama belum dibales -> belum boleh ada request kedua
    await user.click(screen.getByRole("checkbox", { name: "URL / Address" }));
    await act(async () => vi.advanceTimersByTime(700));
    await user.click(screen.getByRole("checkbox", { name: "Kategori" }));
    await act(async () => vi.advanceTimersByTime(700));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => pendingList[0].resolve(jsonResponse({})));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).hidden_list).toEqual(["access"]);
    await act(async () => pendingList[1].resolve(jsonResponse({})));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("layout ga ketimpa balasan API yg bawa layout lama", async () => {
    const { pendingList } = mockFetchSequence();
    render(<EntryTable initialPayload={makePayload()} />);
    await userEvent.click(screen.getByRole("button", { name: /Kolom/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Kategori" }));
    await userEvent.click(screen.getByTitle("Urutkan Judul"));
    const sortRequest = pendingList.find((item) => item.url.includes("table-data"));
    await act(async () => sortRequest.resolve(jsonResponse(makePayload({ layout: { hidden_list: [], width_dict: {} } }))));
    expect(screen.queryByRole("columnheader", { name: /Kategori/ })).toBeNull();
  });

  it("halaman ditutup pas simpanan masih nunggu -> langsung dikirim (keepalive)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn(async () => jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<EntryTable initialPayload={makePayload()} />);
    await user.click(screen.getByRole("button", { name: /Kolom/ }));
    await user.click(screen.getByRole("checkbox", { name: "Kategori" }));

    act(() => window.dispatchEvent(new Event("pagehide")));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1].keepalive).toBe(true);
  });

  it("lebar kolom bisa diatur pake keyboard (panah kanan)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn(async () => jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    render(<EntryTable initialPayload={makePayload()} />);
    const handleEl = screen.getByRole("separator", { name: /Lebar kolom Judul/ });
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

  it("klik kanan di sel -> Salin nilai sel itu", async () => {
    render(<EntryTable initialPayload={makePayload()} />);
    const cellEl = getRowList()[0].querySelector('td[data-column="category"]');
    fireEvent.contextMenu(cellEl, { clientX: 10, clientY: 10 });

    const menuEl = screen.getByRole("menu", { name: "Menu baris" });
    expect(within(menuEl).getAllByRole("menuitem").map((itemEl) => itemEl.textContent)).toEqual(["Buka", "Salin Kategori", "Salin baris"]);
    await userEvent.click(within(menuEl).getByRole("menuitem", { name: "Salin Kategori" }));
    expect(copyText).toHaveBeenCalledWith("Web › SAP");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("Salin baris = kolom yg tampil dipisah tab", async () => {
    render(<EntryTable initialPayload={makePayload()} />);
    fireEvent.contextMenu(getRowList()[0].querySelector('td[data-column="title"]'), { clientX: 10, clientY: 10 });
    await userEvent.click(screen.getByRole("menuitem", { name: "Salin baris" }));
    expect(copyText).toHaveBeenCalledWith("Link 1\tWeb › SAP\thttps://link1.spindo.com\tPublic\tUser Login");
  });

  it("Shift+F10 buka menu dari keyboard, Esc nutup & fokus balik ke baris", async () => {
    render(<EntryTable initialPayload={makePayload()} />);
    const firstRowEl = getRowList()[0];
    act(() => firstRowEl.focus());
    fireEvent.keyDown(firstRowEl, { key: "F10", shiftKey: true });
    const menuEl = screen.getByRole("menu");
    expect(within(menuEl).getByRole("menuitem", { name: "Buka" })).toHaveFocus();

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
    fireEvent.keyDown(screen.getByRole("menuitem", { name: "Buka" }), { key: "ArrowDown" });
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
    await userEvent.click(screen.getByRole("button", { name: /Kolom/ }));
    fireEvent.keyDown(screen.getByRole("checkbox", { name: "Kategori" }), { key: "Escape" });

    expect(bootstrapHitList).toEqual([]);
    expect(screen.queryByRole("menu")).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "Kategori" })).toBeNull();
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
