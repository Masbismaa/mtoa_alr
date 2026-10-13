// Detail group: link dibagi per halaman (10), total di badge, pindah ke halaman 2.
import { BASE, check, clickSelector, evaluate, login, navigate, runScenario, screenshot, waitFor } from "./browser.mjs";

const rowCount = `document.querySelectorAll("#daftar_link_group tbody tr").length`;

await runScenario("group", async ({ info }) => {
  await login("e2e.user");
  await navigate(`${BASE}/groups/${info.group_id}`);
  check("halaman 1 isi 10 link", (await evaluate(rowCount)) === 10, String(await evaluate(rowCount)));
  check("badge total 12", (await evaluate(`document.querySelector("#daftar_link_group .badge").textContent.trim()`)) === "12");
  check("ada navigasi halaman", await evaluate(`Boolean(document.querySelector("#daftar_link_group .pagination"))`));
  await clickSelector('#daftar_link_group .pagination a[href*="page=2"]');
  await waitFor(`location.search.includes("page=2") && document.readyState === "complete"`);
  await waitFor(`${rowCount} === 2`);
  check("klik halaman 2 -> isi 2 link", (await evaluate(rowCount)) === 2, String(await evaluate(rowCount)));
  check("URL bawa page=2 + anchor kartu", (await evaluate("location.search + location.hash")) === "?page=2#daftar_link_group", await evaluate("location.search + location.hash"));
  await screenshot("group_halaman_2.png");
});
