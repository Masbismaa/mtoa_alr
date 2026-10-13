// Tabel versi lama (Users, js/components/data_table.js): simpan layout kolom diantrekan, perubahan yg belum
// kekirim tetep kesimpen pas pindah halaman (keepalive), tiap kiriman bawa client_id + sequence.
import { BASE, check, evaluate, login, navigate, onEvent, runScenario, sleep } from "./browser.mjs";

const hiddenColumns = () => evaluate(`Array.from(document.querySelectorAll("[data-table-column-toggle]")).filter((el) => !el.checked).map((el) => el.value)`);
async function toggleColumn(key) {
  await evaluate(`(() => { const el = document.querySelector('[data-table-column-toggle][value="${key}"]'); el.checked = !el.checked; el.dispatchEvent(new Event("change", { bubbles: true })); })()`);
}

await runScenario("monitor", async () => {
  const layoutBodyList = [];
  onEvent((data) => {
    if (data.method === "Network.requestWillBeSent" && data.params.request.url.endsWith("/settings/table-layout")) {
      layoutBodyList.push(JSON.parse(data.params.request.postData || "{}"));
    }
  });
  await login("e2e.admin");
  await navigate(BASE + "/users/?run=1");
  const keyList = await evaluate(`Array.from(document.querySelectorAll("[data-table-column-toggle]")).map((el) => el.value)`);
  check("ada kolom yg bisa disembunyiin", keyList.length >= 2, keyList.join(","));
  const [firstKey, secondKey] = keyList;

  // 1. sembunyiin, tunggu kesimpen, reload -> tetep ilang
  await toggleColumn(firstKey);
  await sleep(1500);
  await navigate(BASE + "/users/?run=1");
  check("abis reload kolom 1 tetep disembunyiin", (await hiddenColumns()).includes(firstKey), (await hiddenColumns()).join(","));

  // 2. sembunyiin terus LANGSUNG pindah halaman (belum lewat jeda simpan 600 ms) -> tetep kesimpen lewat keepalive
  await toggleColumn(secondKey);
  await navigate(BASE + "/");
  await sleep(800);
  await navigate(BASE + "/users/?run=1");
  const hiddenAfter = await hiddenColumns();
  check("pindah halaman sebelum jeda simpan -> perubahan tetep kesimpen", hiddenAfter.includes(firstKey) && hiddenAfter.includes(secondKey), hiddenAfter.join(","));

  // kiriman keepalive pas halaman ditutup ga ketangkep CDP, jadi yg dicek kiriman yg ketangkep aja
  check("tiap kiriman bawa client_id + sequence", layoutBodyList.length >= 1
    && layoutBodyList.every((body) => /^[A-Za-z0-9_-]{8,64}$/.test(body.client_id) && body.sequence >= 1), JSON.stringify(layoutBodyList.map((body) => body.sequence)));
});
