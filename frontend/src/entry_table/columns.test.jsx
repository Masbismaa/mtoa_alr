// test isi sel per kolom: potong teks, nilai yg disalin, kolom yg belum punya renderer
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeRow } from "../test/makePayload.js";
import { COLUMN_RENDERER_DICT, getColumnRenderer, truncateText } from "./columns.jsx";

describe("truncateText (sama kayak Jinja truncate(n, true, '…', 0))", () => {
  it("pas batas ga dipotong, lewat batas jadi n karakter termasuk …", () => {
    expect(truncateText("A".repeat(60), 60)).toBe("A".repeat(60));
    expect(truncateText("A".repeat(200), 60)).toBe("A".repeat(59) + "…");
  });
});

describe("renderer kolom", () => {
  it("deskripsi panjang dipotong, teks lengkap di tooltip", () => {
    const longText = "A".repeat(200);
    const { container } = render(COLUMN_RENDERER_DICT.description.render(makeRow(1, { description: longText })));
    expect(container.textContent).toBe("A".repeat(59) + "…");
    expect(container.querySelector("span")).toHaveAttribute("title", longText);
  });

  it("URL / Address kosong -> tanda strip, ada isinya -> tombol copy", () => {
    const { container: emptyEl } = render(COLUMN_RENDERER_DICT.access.render(makeRow(1, { access_text: "" })));
    expect(emptyEl.textContent).toBe("-");
    const { getByRole } = render(COLUMN_RENDERER_DICT.access.render(makeRow(1)));
    expect(getByRole("button", { name: "Copy link" })).toBeInTheDocument();
  });

  it("status dapet warna badge sesuai badge.html, tooltip-nya dari server", () => {
    const { container } = render(COLUMN_RENDERER_DICT.status.render(makeRow(1, { status: "down", status_label: "Tidak aktif", status_title: "Dicek 5 menit lalu" })));
    expect(container.querySelector(".badge")).toHaveClass("bg-red-lt");
    expect(container.querySelector(".badge")).toHaveAttribute("title", "Dicek 5 menit lalu");
  });

  it("nilai yg disalin = teks lengkap (bukan yg kepotong)", () => {
    const row = makeRow(1, { title: "B".repeat(80), attachment_count: 2 });
    expect(COLUMN_RENDERER_DICT.title.copyValue(row)).toBe("B".repeat(80));
    expect(COLUMN_RENDERER_DICT.attachment.copyValue(row)).toBe("2");
  });

  it("kolom baru dari server yg lupa dibikinin renderer -> '-' + peringatan di console, bukan crash", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const renderer = getColumnRenderer("kolom_baru");
    const { container } = render(renderer.render(makeRow(1)));
    expect(container.textContent).toBe("-");
    expect(renderer.copyValue(makeRow(1))).toBe("");
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("kolom_baru"));
  });
});
