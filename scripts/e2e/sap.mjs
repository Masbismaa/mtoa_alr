// Nuansa SAP + hapus banyak (admin): centang baris -> Delete selected -> konfirmasi, tombol toolbar (Back, Execute,
// Save, Cancel, Exit, Help, Find), shortcut keyboard udah dihapus, Save as Variant / Get Variant, user & jam di status bar.
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
  await evaluate(`Array.from(document.querySelectorAll("#daftar_link button")).find((el) => el.textContent.includes("Delete selected")).click(); true`);
  check("Delete selected -> dialog konfirmasi muncul", await waitFor(`document.getElementById("confirm_dialog").open`));
  await clickSelector(`#confirm_dialog [data-confirm-ok]`);
  check("abis hapus: total jadi 50", await waitFor(`document.querySelector("#daftar_link .card-title").textContent.includes("All links: 50")`, 8000), await headingText());
  check("status bar bilang kehapus", (await evaluate(`document.querySelector("[data-status-text]").textContent`)).includes("10 links deleted"));

  // 2. tombol Back di detail balik ke tabel
  const detailUrl = await evaluate(`document.querySelector("#daftar_link tbody tr[data-row-url]").dataset.rowUrl`);
  await navigate(BASE + detailUrl);
  await waitLoad(() => clickSelector('.app-systembar a[aria-label="Back"]'));
  check("Back di detail -> balik ke Link List", (await path()) === "/entries/", await path());

  // 3. Variant: isi kriteria -> Save as Variant -> kriterianya kesimpen & bisa dipanggil lagi
  await navigate(BASE + "/entries/");
  await evaluate(`document.getElementById("sel_title").value = "portal 1*"; true`);
  await clickSelector(`.app-toolbar-actions [title="Get / save variants"]`);
  await clickSelector(`input[name="name"][form="variant_save_form"]`);
  await typeText("Portal satu");
  await waitLoad(() => evaluate(`document.querySelector('button[form="variant_save_form"]').click()`));
  const savedSearch = await evaluate("decodeURIComponent(location.search)");
  check("variant kesimpen -> layar kebuka dgn kriterianya", savedSearch.includes("title=portal+1*"), savedSearch);
  await navigate(BASE + "/entries/");
  const variantHref = await evaluate(`Array.from(document.querySelectorAll(".selection-variant-item a")).find((el) => el.textContent.trim() === "Portal satu")?.getAttribute("href")`);
  check("variant muncul di Get Variant", Boolean(variantHref), variantHref);
  await screenshot("sap_2_variant.png");

  // 4. Execute
  await waitLoad(() => clickSelector('button[title="Execute"]'));
  check("Execute -> tabel tampil", await waitFor(`${rowCount} > 0`), await evaluate("location.search"));

  // 5. Save di form edit
  const editUrl = BASE + detailUrl.replace(/\?.*$/, "") + "/edit";
  await navigate(editUrl);
  await waitLoad(() => clickSelector('.app-systembar button[aria-label="Save"]'));
  check("Save di form edit -> kesimpen", (await evaluate("document.body.innerText")).includes("Changes saved"));

  // 6. shortcut keyboard udah dihapus total: F1, F3, Shift+F3, F8, F12, Ctrl+S, Shift+F2, "/" ga ngapa-ngapain
  const isHelpOpen = `document.getElementById("help_dialog").open`;
  await navigate(editUrl);
  for (const [key, code, keyCode, modifiers] of [["F1", "F1", 112, 0], ["F3", "F3", 114, 0], ["F3", "F3", 114, 8], ["F8", "F8", 119, 0],
    ["F12", "F12", 123, 0], ["s", "KeyS", 83, 2], ["F2", "F2", 113, 8], ["/", "Slash", 191, 0]]) {
    await pressKey(key, code, keyCode, modifiers);
  }
  await new Promise((resolve) => setTimeout(resolve, 800));
  check("tombol keyboard ga mbuka Help / pindah layar / nyimpen", !(await evaluate(isHelpOpen)) && (await path()).endsWith("/edit")
    && !(await evaluate(`document.activeElement?.hasAttribute("data-selection-quick") === true`)), await path());
  await navigate(BASE + "/entries/");
  await clickSelector('.app-systembar button[aria-label="Help"]');
  check("tombol Help -> dialog Help kebuka", await waitFor(isHelpOpen));
  check("Help ga nampilin daftar tombol keyboard", !(await evaluate(`Boolean(document.querySelector("#help_dialog kbd"))`)));
  await screenshot("sap_4_help.png");
  await evaluate(`document.querySelector("[data-help-close]").click(); true`);
  check("Close -> Help ketutup", await waitFor(`!${isHelpOpen}`));
  await clickSelector('.app-systembar button[aria-label="Find"]');
  check("tombol Find -> fokus ke Quick search", await waitFor(`document.activeElement?.hasAttribute("data-selection-quick")`));
  await navigate(editUrl);
  await waitLoad(() => clickSelector('.app-systembar a[aria-label="Cancel"]'));
  check("Cancel di form edit -> keluar dari form", !(await path()).endsWith("/edit"), await path());
  await navigate(BASE + "/entries/");
  await waitLoad(() => clickSelector('.app-systembar a[aria-label="Exit"]'));
  check("Exit -> Home", (await path()) === "/", await path());

  // 7. status bar: user & jam
  const clockText = await evaluate(`document.querySelector("[data-status-clock]").textContent`);
  check("status bar ada jam HH:MM", /^\d{2}:\d{2}$/.test(clockText), clockText);
  check("status bar ada user", (await evaluate(`document.querySelector(".app-statusbar").textContent`)).includes("e2e.admin"));
  await screenshot("sap_3_statusbar.png");
});
