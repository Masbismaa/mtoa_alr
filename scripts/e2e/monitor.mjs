// Link Monitoring dgn worker beneran: peringatan muncul sendiri kalau worker mati, progres jalan sendiri
// tanpa reload, halaman muat ulang otomatis pas selesai & ringkasan keupdate.
import { join } from "node:path";
import {
  BASE, PROJECT_DIR, check, evaluate, login, navigate, runScenario, screenshot, sleep, startProcess, waitFor, waitLoad,
} from "./browser.mjs";

const statusText = () => evaluate(`(document.querySelector("[data-monitor-message]") || {}).textContent || ""`);
const isWarningShown = `(() => { const el = document.querySelector("[data-monitor-warning]"); return Boolean(el && !el.hidden); })()`;

await runScenario("monitor", async (server) => {
  await login("e2e.admin");
  await navigate(BASE + "/link-monitoring/");
  check("awal: belum ada panel status", !(await evaluate(`Boolean(document.getElementById("monitor_status"))`)));

  // 1. klik cek pas worker belum jalan (form.submit() ngelewatin dialog konfirmasi)
  await waitLoad(() => evaluate(`document.querySelector("form[action$='/run']").submit()`));
  check("abis klik: menunggu pemeriksaan", (await statusText()).includes("Waiting for the check"), await statusText());
  check("tombol cek dikunci", await evaluate(`document.querySelector("form[action$='/run'] button").disabled`));
  check("peringatan belum muncul (baru diklik)", !(await evaluate(isWarningShown)));
  check("worker ga jalan -> peringatan muncul sendiri tanpa reload", await waitFor(isWarningShown, 12000));
  check("peringatan bawa perintah worker", (await evaluate(`document.querySelector("[data-monitor-warning]").textContent`)).includes("monitor-worker"));
  await screenshot("monitor_1_peringatan.png");

  // 2. worker dinyalain -> progres jalan sendiri
  startProcess([join(PROJECT_DIR, "scripts", "e2e", "worker_monitor.py")], server.env);
  check("worker jalan -> status 'berjalan' muncul sendiri", await waitFor(`((document.querySelector("[data-monitor-message]") || {}).textContent || "").includes("Check running")`, 15000), await statusText());
  check("peringatan ilang sendiri", !(await evaluate(isWarningShown)));
  check("progress bar tampil", await evaluate(`!document.querySelector("[data-monitor-progress]").hidden`));
  const firstText = await statusText();
  await sleep(3500);
  const secondText = await statusText();
  check("angka progres naik sendiri", firstText !== secondText, `${firstText} -> ${secondText}`);

  // 3. selesai -> reload otomatis, ringkasan keupdate
  check("selesai -> halaman muat ulang sendiri & bilang selesai", await waitFor(`((document.querySelector("[data-monitor-message]") || {}).textContent || "").includes("Check finished")`, 30000), await statusText());
  check("selesai: 60 data diperiksa", (await statusText()).includes("60 links"));
  check("tombol cek bisa diklik lagi", !(await evaluate(`document.querySelector("form[action$='/run'] button").disabled`)));
  check("ringkasan: 45 aktif, 15 tidak aktif", (await evaluate("document.body.innerText")).match(/Up\s+45[\s\S]*Down\s+15/) !== null);
  await screenshot("monitor_2_selesai.png");
});
