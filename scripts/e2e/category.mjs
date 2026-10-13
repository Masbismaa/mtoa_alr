// Form link: kategori dipilih bertingkat (Category -> Sub-category -> ...), boleh berhenti di tingkat mana aja.
// Yg dikirim tetep dropdown asli category_id = tingkat terakhir yg dipilih.
import { BASE, check, evaluate, login, navigate, path, pressKey, runScenario, screenshot, waitLoad } from "./browser.mjs";

const cascadeValues = () => evaluate(`Array.from(document.querySelectorAll("[data-category-cascade] select"), (el) => el.value)`);
const sentCategory = () => evaluate(`document.getElementById("category_id").value`);
async function chooseLevel(level, value) {
  await evaluate(`(() => { const el = document.querySelector('[data-category-cascade] select[data-level="${level}"]');
    el.value = ${JSON.stringify(String(value))}; el.dispatchEvent(new Event("change", { bubbles: true })); })()`);
}

await runScenario("table", async (server) => {
  const sapId = String(server.info.sub_category_id);
  await login("e2e.user");

  // tingkat ketiga: Web > SAP > Modul FI, dibikin lewat form "add sub" aplikasinya
  await navigate(`${BASE}/categories/${sapId}/sub/new`);
  await waitLoad(() => evaluate(`(() => { const form = document.getElementById("category_form");
    form.querySelector('[name="name"]').value = "Modul FI"; form.requestSubmit(); })()`));
  const fiId = (await path()).split("/").pop();
  check("sub-kategori tingkat 3 kebikin", /^\d+$/.test(fiId), await path());

  await navigate(BASE + "/entries/new");
  const webId = await evaluate(`document.querySelector('[data-category-cascade] select[data-level="0"]').value`);
  check("dropdown asli disembunyiin, diganti dropdown bertingkat",
    await evaluate(`document.getElementById("category_id").hidden && !document.querySelector("[data-category-cascade]").hidden`));
  check("awal: Category = Web, Sub-category (optional) kosong", JSON.stringify(await cascadeValues()) === JSON.stringify([webId, ""]),
    JSON.stringify(await cascadeValues()));
  check("label Category nunjuk ke dropdown tingkat pertama",
    await evaluate(`document.querySelector('label[for="category_level_0"]') !== null`));

  await chooseLevel(1, sapId);
  check("pilih SAP -> muncul dropdown tingkat 3, yg dikirim SAP",
    JSON.stringify(await cascadeValues()) === JSON.stringify([webId, sapId, ""]) && (await sentCategory()) === sapId,
    `${JSON.stringify(await cascadeValues())} kirim=${await sentCategory()}`);

  await chooseLevel(2, fiId);
  await screenshot("category_cascade.png");
  check("pilih Modul FI -> ga ada tingkat lagi, yg dikirim Modul FI",
    JSON.stringify(await cascadeValues()) === JSON.stringify([webId, sapId, fiId]) && (await sentCategory()) === fiId,
    `${JSON.stringify(await cascadeValues())} kirim=${await sentCategory()}`);

  await chooseLevel(1, "");
  check("Sub-category balik ke (optional) -> berhenti di Web, tingkat 3 ilang",
    JSON.stringify(await cascadeValues()) === JSON.stringify([webId, ""]) && (await sentCategory()) === webId,
    `${JSON.stringify(await cascadeValues())} kirim=${await sentCategory()}`);

  // keyboard: panah di dropdown tingkat 2 ga bikin fokus loncat (dropdown yg dipake ga dibikin ulang)
  await evaluate(`document.querySelector('[data-category-cascade] select[data-level="1"]').focus()`);
  await pressKey("ArrowDown", "ArrowDown", 40);
  check("panah bawah di Sub-category -> fokus tetep di dropdown itu",
    await evaluate(`document.activeElement && document.activeElement.dataset.level === "1"`),
    await evaluate(`document.activeElement && document.activeElement.outerHTML.slice(0, 80)`));

  // ganti ke General: ga punya sub -> cuma 1 dropdown, field tambahan muncul (aturan kategori tetep jalan)
  const generalId = await evaluate(`Array.from(document.querySelectorAll('[data-category-cascade] select[data-level="0"] option')).find((el) => el.text === "General").value`);
  await chooseLevel(0, generalId);
  check("pilih General -> cuma 1 dropdown + field tambahan tampil",
    (await cascadeValues()).length === 1 && await evaluate(`!document.querySelector("[data-custom-field-section]").hidden`),
    JSON.stringify(await cascadeValues()));

  // simpan di tingkat 3, terus buka edit: jalurnya kepilih lagi
  await chooseLevel(0, webId);
  await chooseLevel(1, sapId);
  await chooseLevel(2, fiId);
  await evaluate(`(() => { const form = document.getElementById("entry_form");
    form.querySelector('[name="title"]').value = "Link Modul FI";
    form.querySelector('[name="url"]').value = "https://fi.spindo.com"; })()`);
  await waitLoad(() => evaluate(`document.getElementById("entry_form").requestSubmit()`));
  const entryId = (await path()).split("/").filter(Boolean).pop();
  check("link kesimpen", /^\d+$/.test(entryId), await path());
  await navigate(`${BASE}/entries/${entryId}/edit`);
  check("buka edit -> Web > SAP > Modul FI kepilih lagi",
    JSON.stringify(await cascadeValues()) === JSON.stringify([webId, sapId, fiId]) && (await sentCategory()) === fiId,
    JSON.stringify(await cascadeValues()));
});
