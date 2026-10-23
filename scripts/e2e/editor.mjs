// Editor teks ala Word di field tambahan (kategori General): gaya paragraf, font, ukuran, warna, rata, list bertingkat,
// garis, quote. Hasil HTML browser (execCommand) harus lolos sanitizer server & tampil sama di halaman detail.
import { BASE, check, clickSelector, evaluate, login, navigate, path, pressKey, runScenario, screenshot, send, sleep, typeText, waitFor, waitLoad } from "./browser.mjs";

const EDITOR = "[data-rte-content]";
const editorHtml = () => evaluate(`document.querySelector("${EDITOR}").innerHTML`);
const viewHtml = () => evaluate(`document.querySelector(".rich-text-view").innerHTML`);

// blok isi elemen terakhir yg cocok (kayak user nge-drag teksnya), terus tunggu selectionchange kebaca editor
async function selectLast(selector) {
  await evaluate(`(() => { const list = document.querySelectorAll("${EDITOR} ${selector}"); const range = document.createRange();
    range.selectNodeContents(list[list.length - 1]); const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range); })()`);
  await sleep(100);
}

// taruh kursor di akhir elemen terakhir yg cocok
async function caretEnd(selector) {
  await evaluate(`(() => { const list = document.querySelectorAll("${EDITOR} ${selector}"); const range = document.createRange();
    range.selectNodeContents(list[list.length - 1]); range.collapse(false); const selection = getSelection();
    selection.removeAllRanges(); selection.addRange(range); })()`);
  await sleep(100);
}

const clickTool = (selector) => evaluate(`document.querySelector('.rte-toolbar ${selector}').click()`);
async function chooseTool(command, value) {
  await evaluate(`(() => { const el = document.querySelector('[data-rte-select="${command}"]'); el.value = ${JSON.stringify(value)};
    el.dispatchEvent(new Event("change", { bubbles: true })); })()`);
  await sleep(100);
}
const toolValue = (command) => evaluate(`document.querySelector('[data-rte-select="${command}"]').value`);
// Enter beneran (pake text "\r") biar browser bikin paragraf / poin list baru
async function pressEnter() {
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r" });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await sleep(100);
}

await runScenario("table", async () => {
  await login("e2e.user");
  await navigate(BASE + "/entries/new");
  await evaluate(`(() => { const el = document.querySelector('[data-category-cascade] select[data-level="0"]');
    el.value = Array.from(el.options).find((option) => option.text === "General").value; el.dispatchEvent(new Event("change", { bubbles: true })); })()`);
  await evaluate(`document.querySelector("[data-custom-field-add]").click()`);
  check("Add field -> editor + toolbar ala Word muncul",
    await evaluate(`!!document.querySelector("${EDITOR}") && document.querySelectorAll(".rte-toolbar [data-rte-select]").length === 3`));

  // judul: Heading 1
  await evaluate(`document.querySelector("${EDITOR}").focus()`);
  await typeText("Panduan VPN");
  await chooseTool("formatBlock", "h1");
  check("gaya paragraf Heading 1 -> <h1>", (await editorHtml()).includes("<h1>Panduan VPN</h1>"), await editorHtml());

  // paragraf: font, ukuran, warna, rata tengah
  await caretEnd("h1");
  await pressEnter();
  await chooseTool("formatBlock", "p");
  await typeText("Penting dibaca");
  await selectLast("p");
  await chooseTool("fontName", "Times New Roman");
  await chooseTool("fontSize", "5");
  const colorMenuShown = () => evaluate(`getComputedStyle(document.querySelector(".rte-color-menu")).display !== "none"`);
  check("menu warna ketutup sebelum diklik", !(await colorMenuShown()));
  await clickSelector('.rte-toolbar [title="Text color"]');
  check("klik tombol warna -> pilihan warna kebuka", await waitFor(`getComputedStyle(document.querySelector(".rte-color-menu")).display !== "none"`));
  await clickSelector('.rte-toolbar [data-rte-value="#d63939"]');
  check("pilih warna -> menu ketutup lagi", await waitFor(`getComputedStyle(document.querySelector(".rte-color-menu")).display === "none"`));
  await clickTool('[data-rte-command="justifyCenter"]');
  const styledHtml = await editorHtml();
  check("font, ukuran, warna kepasang (tag <font> nilai dari toolbar)",
    /<font[^>]*face="Times New Roman"/.test(styledHtml) && /<font[^>]*size="5"/.test(styledHtml) && /<font[^>]*color="#d63939"/.test(styledHtml),
    styledHtml);
  check("rata tengah kepasang", /text-align: center|align="center"/.test(styledHtml), styledHtml);
  await selectLast("font");
  check("toolbar ikut posisi kursor: font & ukuran kebaca",
    (await toolValue("fontName")) === "Times New Roman" && (await toolValue("fontSize")) === "5",
    `${await toolValue("fontName")} / ${await toolValue("fontSize")}`);
  await caretEnd("h1");
  check("kursor di judul -> dropdown gaya nunjuk Heading 1", (await toolValue("formatBlock")) === "h1", await toolValue("formatBlock"));

  // list bertingkat pake Tab
  await caretEnd("p");
  await pressEnter();
  await clickTool('[data-rte-command="justifyLeft"]');
  await clickTool('[data-rte-command="insertOrderedList"]');
  await typeText("Buka FortiClient");
  await pressEnter();
  await pressKey("Tab", "Tab", 9);
  await typeText("Pilih profil kantor");
  check("Tab di list -> sub-list (bertingkat)", /<ol>(?:(?!<\/ol>).)*<ol>/s.test(await editorHtml()), await editorHtml());
  check("Tab di list ga mindahin fokus keluar editor", await evaluate(`document.activeElement === document.querySelector("${EDITOR}")`));

  // keluar list, garis + quote + coret
  await pressEnter();
  await pressKey("Tab", "Tab", 9, 8);
  await pressEnter();
  await pressEnter();
  await clickTool('[data-rte-command="insertHorizontalRule"]');
  await typeText("Hubungi helpdesk");
  await chooseTool("formatBlock", "blockquote");
  await selectLast("blockquote");
  await clickTool('[data-rte-command="strikeThrough"]');
  const finalHtml = await editorHtml();
  check("garis, quote, coret kepasang", finalHtml.includes("<hr>") && finalHtml.includes("<blockquote") && /<strike>|<s>/.test(finalHtml), finalHtml);
  await screenshot("editor_form.png");

  // simpan -> detail: format yg sama lolos sanitizer
  await evaluate(`(() => { const form = document.getElementById("entry_form");
    form.querySelector('[name="title"]').value = "Panduan VPN Kantor";
    form.querySelector('[name="custom_field_label"]').value = "Cara akses"; })()`);
  await waitLoad(() => evaluate(`document.getElementById("entry_form").requestSubmit()`));
  const entryId = (await path()).split("/").filter(Boolean).pop();
  check("link kesimpen", /^\d+$/.test(entryId), await path());
  const savedHtml = await viewHtml();
  check("detail: heading, font, warna, rata, list bertingkat, garis, quote, coret tetep ada",
    savedHtml.includes("<h1>Panduan VPN</h1>") && /face="Times New Roman"/.test(savedHtml) && /color="#d63939"/.test(savedHtml)
      && /size="5"/.test(savedHtml) && /text-align:\s?center|align="center"/.test(savedHtml)
      && /<ol>(?:(?!<\/ol>).)*<ol>/s.test(savedHtml) && savedHtml.includes("<hr>") && savedHtml.includes("<blockquote")
      && /<strike>|<s>/.test(savedHtml),
    savedHtml);
  check("detail: judul pake gaya heading (lebih gede dari teks biasa)",
    await evaluate(`parseFloat(getComputedStyle(document.querySelector(".rich-text-view h1")).fontSize) > parseFloat(getComputedStyle(document.querySelector(".rich-text-view")).fontSize)`));
  await screenshot("editor_detail.png");

  // edit lagi: isi kebuka utuh di editor
  await navigate(`${BASE}/entries/${entryId}/edit`);
  check("buka edit -> format kebaca lagi di editor", /face="Times New Roman"/.test(await editorHtml()) && (await editorHtml()).includes("<h1>"),
    await editorHtml());
});
