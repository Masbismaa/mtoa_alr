// Jendela ala SAP GUI: menu bar, toolbar sistem.
import { BASE, check, clickSelector, evaluate, login, navigate, path, runScenario, screenshot, waitFor, waitLoad } from "./browser.mjs";

await runScenario("group", async () => {
  await login("e2e.user");

  check("kolom kode menu udah ga ada", await evaluate(`!document.querySelector("[data-command-input]")`));

  await clickSelector('.app-menubar [accesskey="m"]');
  await waitFor(`document.querySelector('.app-menubar [accesskey="m"] + .dropdown-menu.show')`);
  const menuText = await evaluate(`document.querySelector('.app-menubar [accesskey="m"] + .dropdown-menu').innerText`);
  check("menu Menu isinya menu yg boleh dibuka", menuText.includes("Link List") && !menuText.includes("Users"), menuText.replace(/\n/g, " | "));
  await screenshot("shell_menu.png");

  // Easy Access: buka folder Data > Links, klik transaksi; lebar pohon paten (ga ada garis geser)
  await navigate(BASE + "/");
  await evaluate(`document.querySelector(".app-menubar .dropdown-menu.show")?.classList.remove("show")`);
  const folderSelector = (label) => `[...document.querySelectorAll(".ea-folder > summary")].find((el) => el.textContent.trim() === "${label}")`;
  await evaluate(`${folderSelector("Data")}.click()`);
  await evaluate(`${folderSelector("Links")}.click()`);
  check("buka folder -> aria-expanded ikut", await evaluate(`${folderSelector("Links")}.getAttribute("aria-expanded") === "true"`));
  check("pohon menu ga bisa digeser", await evaluate(`!document.querySelector("[data-easy-access-splitter]")`));
  await screenshot("easy_access.png");
  await waitLoad(() => evaluate(`[...document.querySelectorAll(".ea-leaf")].find((el) => el.textContent.includes("Link List")).click()`));
  check("klik transaksi di pohon -> pindah layar", (await path()) === "/entries/", await path());

  await navigate(BASE + "/entries/1");
  await clickSelector('.app-systembar [data-fkey="F3"]');
  await waitFor(`location.pathname !== "/entries/1"`);
  check("tombol Back di toolbar sistem jalan", (await path()) !== "/entries/1", await path());
});
