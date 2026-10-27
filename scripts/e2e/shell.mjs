// Jendela ala SAP GUI: command field (kode transaksi), menu bar, toolbar sistem.
import { BASE, check, clickSelector, evaluate, login, navigate, path, pressKey, runScenario, screenshot, typeText, waitFor, waitLoad } from "./browser.mjs";

const statusText = () => evaluate(`document.querySelector("[data-status-text]").textContent`);

async function runCommand(code) {
  await evaluate(`document.querySelector("[data-command-input]").focus()`);
  await typeText(code);
  await waitLoad(() => pressKey("Enter", "Enter", 13));
}

await runScenario("group", async () => {
  await login("e2e.user");

  await runCommand("ll");
  check("ketik LL + Enter -> Link List", (await path()) === "/entries/", await path());
  await runCommand("/nGR");
  check("/nGR -> Groups", (await path()) === "/groups/", await path());
  await runCommand("/n");
  check("/n -> Home", (await path()) === "/", await path());

  await evaluate(`document.querySelector("[data-command-input]").focus()`);
  await typeText("zz");
  await pressKey("Enter", "Enter", 13);
  await waitFor(`document.querySelector("[data-status-text]").textContent.includes("ZZ")`);
  check("kode ga dikenal -> pesan di status bar, tetep di layar ini", (await statusText()) === "Transaction ZZ does not exist" && (await path()) === "/", await statusText());

  await evaluate(`document.activeElement.blur()`);
  await pressKey("/", "Slash", 191, 2);
  check("Ctrl+/ -> fokus ke command field", await evaluate(`document.activeElement.matches("[data-command-input]")`));

  await clickSelector('.app-menubar [accesskey="m"]');
  await waitFor(`document.querySelector('.app-menubar [accesskey="m"] + .dropdown-menu.show')`);
  const menuText = await evaluate(`document.querySelector('.app-menubar [accesskey="m"] + .dropdown-menu').innerText`);
  check("menu Menu isinya transaksi + kodenya", menuText.includes("Link List") && menuText.includes("LL") && !menuText.includes("Users"), menuText.replace(/\n/g, " | "));
  await screenshot("shell_menu.png");

  // Easy Access: buka folder Data > Links, klik transaksi; garis pemisah digeser
  await navigate(BASE + "/");
  await evaluate(`document.querySelector(".app-menubar .dropdown-menu.show")?.classList.remove("show")`);
  const folderSelector = (label) => `[...document.querySelectorAll(".ea-folder > summary")].find((el) => el.textContent.trim() === "${label}")`;
  await evaluate(`${folderSelector("Data")}.click()`);
  await evaluate(`${folderSelector("Links")}.click()`);
  check("buka folder -> aria-expanded ikut", await evaluate(`${folderSelector("Links")}.getAttribute("aria-expanded") === "true"`));
  const treeWidth = () => evaluate(`Math.round(document.querySelector(".ea-tree-panel").getBoundingClientRect().width)`);
  const beforeWidth = await treeWidth();
  await evaluate(`document.querySelector("[data-easy-access-splitter]").focus()`);
  await pressKey("ArrowRight", "ArrowRight", 39);
  check("panah kanan di garis pemisah -> pohon melebar", (await treeWidth()) > beforeWidth, `${beforeWidth} -> ${await treeWidth()}`);
  await screenshot("easy_access.png");
  await waitLoad(() => evaluate(`[...document.querySelectorAll(".ea-leaf")].find((el) => el.textContent.includes("Link List")).click()`));
  check("klik transaksi di pohon -> pindah layar", (await path()) === "/entries/", await path());

  await navigate(BASE + "/entries/1");
  await clickSelector('.app-systembar [data-fkey="F3"]');
  await waitFor(`location.pathname !== "/entries/1"`);
  check("tombol Back di toolbar sistem jalan", (await path()) !== "/entries/1", await path());
});
