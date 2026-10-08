// test modul bersama: susun/baca query string & bungkus fetch API
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getJson, postJson } from "./api.js";
import { buildQueryText, buildUrl, parseQueryText, withQueryValue } from "./queryString.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("queryString", () => {
  it("nilai banyak (Multi Selection) & karakter khusus aman", () => {
    expect(buildQueryText({ title: ["a b", "c&d"], run: ["1"] }, 2)).toBe("title=a+b&title=c%26d&run=1&page=2");
    expect(buildUrl("/entries/", {}, 1, "daftar_link")).toBe("/entries/#daftar_link");
  });

  it("baca balik dari URL, halaman ngaco jadi 1", () => {
    expect(parseQueryText("?title=a&title=b&page=3")).toEqual({ query: { title: ["a", "b"] }, page: 3 });
    expect(parseQueryText("?page=-5").page).toBe(1);
    expect(parseQueryText("?page=abc").page).toBe(1);
  });

  it("ganti satu nilai, kosong = parameternya dibuang, object lama ga diubah", () => {
    const query = { run: ["1"], title: ["a", "b"] };
    expect(withQueryValue(query, "title", " portal* ")).toEqual({ run: ["1"], title: ["portal*"] });
    expect(withQueryValue(query, "title", "   ")).toEqual({ run: ["1"] });
    expect(query).toEqual({ run: ["1"], title: ["a", "b"] });
  });
});

describe("api", () => {
  it("balasan sukses -> isi data", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, redirected: false, json: async () => ({ is_success: true, data: { a: 1 } }) })));
    await expect(getJson("/x")).resolves.toEqual({ a: 1 });
  });

  it("kena redirect (endpoint lama ke halaman login) -> dianggep sesi habis", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, redirected: true, json: async () => ({}) })));
    const error = await getJson("/x").catch((caught) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.isSessionExpired).toBe(true);
  });

  it("jaringan putus -> pesan jelas", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    await expect(getJson("/x")).rejects.toThrow("Koneksi ke server gagal");
  });

  it("request dibatalin -> AbortError diterusin apa adanya (bukan dianggep error jaringan)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new DOMException("batal", "AbortError"); }));
    await expect(getJson("/x")).rejects.toMatchObject({ name: "AbortError" });
  });

  it("server nolak (400) -> pesan dari server", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 400, redirected: false, json: async () => ({ is_success: false, message: "Layout tabel tidak valid" }) })));
    await expect(postJson("/x", {})).rejects.toThrow("Layout tabel tidak valid");
  });
});
