// Nuansa SAP + hapus banyak (admin): centang baris -> Delete selected -> konfirmasi, tombol fungsi keyboard
// (F3/F8/Ctrl+S), Save as Variant / Get Variant, info user & jam di status bar.
// Pake data skenario monitor: e2e.admin punya 60 link Web.
import { BASE, check, clickSelector, evaluate, login, navigate, path, pressKey, runScenario, screenshot, typeText, waitFor, waitLoad } from "./browser.mjs";

const rowCount = `document.querySelectorAll("#daftar_link tbody tr[data-row-url]").length`;
const headingText = () => evaluate(`document.querySelector("#daftar_link .card-title").textContent`);

await runScenario("monitor", async () => {
  await login("e2e.admin");

  // 1. hapus banyak
  await navigate(BASE + "/entries/?run=1");
  await waitFor(`${rowCount} === 10`);
  check("admin dapet kolom centang", await evaluate(`document.querySelectorAll("#daftar_link tbody .cell-select input").length`) === 10);
  check("tombol Delete selected awalnya mati", await evaluate(`Array.from(document.querySelectorAll("#daftar_link button")).find((el) => el.textContent.includes("Delete selected")).disabled`));
  await clickSelector(`#daftar_link thead .cell-select input`);
  const buttonText = await evaluate(`Array.from(document.querySelectorAll("#daftar_link button")).find((el) => el.textContent.includes("Delete selected")).textContent`);
  check("centang semua -> 10 kepilih", buttonText.includes("(10)"), buttonText);
  await screenshot("sap_1_centang.png");
  await pressKey("F2", "F2", 113, 8);
  check("Shift+F2 -> dialog konfirmasi muncul", await waitFor(`document.getElementById("confirm_dialog").open`));
  await clickSelector(`#confirm_dialog [data-confirm-ok]`);
  check("abis hapus: total jadi 50", await waitFor(`document.querySelector("#daftar_link .card-title").textContent.includes("All links: 50")`, 8000), await headingText());
  check("status bar bilang kehapus", (await evaluate(`document.querySelector("[data-status-text]").textContent`)).includes("10 links deleted"));

  // 2. tombol fungsi: F3 di detail balik ke tabel
  const detailUrl = await evaluate(`document.querySelector("#daftar_link tbody tr[data-row-url]").dataset.rowUrl`);
  await navigate(BASE + detailUrl);
  await waitLoad(() => pressKey("F3", "F3", 114));
  check("F3 di detail -> balik ke Link List", (await path()) === "/entries/", await path());

  // 3. Variant: isi kriteria -> Save as Variant -> kriterianya kesimpen & bisa dipanggil lagi
  await navigate(BASE + "/entries/");
  await evaluate(`document.getElementById("sel_title").value = "portal 1*"; true`);
  await clickSelector(`.selection-panel .card-actions [data-bs-toggle="dropdown"]`);
  await clickSelector(`input[name="name"][form="variant_save_form"]`);
  await typeText("Portal satu");
  await waitLoad(() => evaluate(`document.querySelector('button[form="variant_save_form"]').click()`));
  const savedSearch = await evaluate("decodeURIComponent(location.search)");
  check("variant kesimpen -> layar kebuka dgn kriterianya", savedSearch.includes("title=portal+1*"), savedSearch);
  await navigate(BASE + "/entries/");
  const variantHref = await evaluate(`Array.from(document.querySelectorAll(".selection-variant-item a")).find((el) => el.textContent.trim() === "Portal satu")?.getAttribute("href")`);
  check("variant muncul di Get Variant", Boolean(variantHref), variantHref);
  await screenshot("sap_2_variant.png");

  // 4. F8 = Execute
  await waitLoad(() => pressKey("F8", "F8", 119));
  check("F8 -> Execute (tabel tampil)", await waitFor(`${rowCount} > 0`), await evaluate("location.search"));

  // 5. Ctrl+S = Save di form edit
  await navigate(BASE + detailUrl.replace(/\?.*$/, "") + "/edit");
  await waitLoad(() => pressKey("s", "KeyS", 83, 2));
  check("Ctrl+S di form edit -> kesimpen", (await evaluate("document.body.innerText")).includes("Changes saved"));

  // 6. status bar: user & jam
  const clockText = await evaluate(`document.querySelector("[data-status-clock]").textContent`);
  check("status bar ada jam HH:MM", /^\d{2}:\d{2}$/.test(clockText), clockText);
  check("status bar ada user", (await evaluate(`document.querySelector(".app-statusbar").textContent`)).includes("e2e.admin"));
  await screenshot("sap_3_statusbar.png");
});
