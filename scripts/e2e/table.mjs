// Tabel link React (Daftar Link & isi kategori): urut, filter kolom, halaman, Back browser, keyboard,
// menu klik kanan (posisi & Bootstrap), simpan layout, tombol Kembali, sesi habis.
import {
  BASE, check, clickSelector, evaluate, login, navigate, pressKey, runScenario, screenshot, typeText, waitFor,
} from "./browser.mjs";

const rowTitles = `Array.from(document.querySelectorAll("#daftar_link tbody tr[data-row-url] td[data-column=title]")).map((td) => td.textContent)`;
const rowCount = `document.querySelectorAll("#daftar_link tbody tr[data-row-url]").length`;

// error 401 dari langkah "sesi habis" emang disengaja
await runScenario("table", async ({ info }) => {
  await login("e2e.user");
  check("login password + OTP", true);

  await navigate(BASE + "/entries/?run=1");
  check("React render 10 baris dari data awal", await waitFor(`${rowCount} === 10`), String(await evaluate(rowCount)));
  check("judul jumlah data", (await evaluate(`document.querySelector("#daftar_link .card-title").textContent`)).includes("All links: 25"));
  check("placeholder 'Memuat tabel' udah ilang", !(await evaluate(`Boolean(document.querySelector("[data-entry-table-loading]"))`)));
  await screenshot("table_1_daftar_link.png");

  // urutkan
  await clickSelector('#daftar_link a.col-sort[title="Sort by Title"]');
  await waitFor(`${rowTitles}[0] === "Portal 00"`);
  const sortedTitles = await evaluate(rowTitles);
  check("klik Judul -> urut naik tanpa reload", sortedTitles[0] === "Portal 00" && sortedTitles[1] === "Portal 02", sortedTitles.slice(0, 3).join(","));
  check("URL browser ikut berubah", (await evaluate("location.search")) === "?run=1&sort=title", await evaluate("location.search"));
  check("panel kriteria: hidden sort ikut", (await evaluate(`document.querySelector('[data-selection-form] input[name=sort]')?.value`)) === "title");

  // filter kolom Judul
  await clickSelector('#daftar_link input[aria-label="Filter Title"]');
  await typeText("router*");
  await pressKey("Enter", "Enter", 13);
  await waitFor(`(${rowTitles}).every((t) => t.startsWith("Router"))`);
  check("filter kolom Judul router*", await evaluate(`(${rowTitles}).every((t) => t.startsWith("Router"))`), (await evaluate(rowTitles)).join(","));
  check("panel kriteria isian Judul ikut keisi", (await evaluate(`document.querySelector("#sel_title").value`)) === "router*");
  check("judul jadi Hasil pencarian", (await evaluate(`document.querySelector("#daftar_link .card-title").textContent`)).includes("Search results: 12"));
  check("tombol export bawa filter", (await evaluate(`document.querySelector("#daftar_link a[href^='/export']").getAttribute("href")`)) === "/export?run=1&sort=title&title=router*");

  // pindah halaman + Back browser
  await clickSelector('#daftar_link a.page-link[aria-label="Next page"]');
  await waitFor(`location.search.includes("page=2") && ${rowCount} === 2`);
  check("halaman 2 berisi 2 baris", (await evaluate(rowCount)) === 2);
  check("fokus pindah ke judul tabel", await evaluate(`document.activeElement === document.querySelector("#daftar_link .card-title")`));
  await evaluate("history.back(); true");
  await waitFor(`!location.search.includes("page=2") && ${rowCount} === 10`);
  check("Back -> balik ke halaman 1", (await evaluate("location.search")) === "?run=1&sort=title&title=router*", await evaluate("location.search"));

  // keyboard
  await evaluate(`document.querySelector("#daftar_link tbody tr[data-row-url]").focus(); true`);
  await pressKey("ArrowDown", "ArrowDown", 40);
  check("panah bawah -> baris ke-2 aktif", await evaluate(`document.querySelectorAll("#daftar_link tbody tr[data-row-url]")[1].classList.contains("is-active") && document.activeElement === document.querySelectorAll("#daftar_link tbody tr[data-row-url]")[1]`));

  // menu klik kanan: harus muncul pas di titik klik (bug lama: kegeser karena animasi transform kartu)
  const clickPoint = await clickSelector('#daftar_link tbody tr[data-row-url]:nth-child(2) td[data-column="owner"]', "right");
  await waitFor(`Boolean(document.querySelector(".row-context-menu"))`);
  const menuItems = await evaluate(`Array.from(document.querySelectorAll(".row-context-menu [role=menuitem]")).map((el) => el.textContent)`);
  check("klik kanan -> menu baris", JSON.stringify(menuItems) === JSON.stringify(["Open", "Copy Created By", "Copy row"]), JSON.stringify(menuItems));
  const menuRect = await evaluate(`(() => { const r = document.querySelector(".row-context-menu").getBoundingClientRect();
    return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, vw: innerWidth, vh: innerHeight}; })()`);
  check("menu muncul di titik klik & utuh di dalam layar",
    Math.abs(menuRect.left - clickPoint.x) < 2 && Math.abs(menuRect.top - clickPoint.y) < 2 && menuRect.right <= menuRect.vw && menuRect.bottom <= menuRect.vh,
    JSON.stringify({ click: clickPoint, menu: menuRect }));
  await screenshot("table_2_menu_klik_kanan.png");
  // Esc: bug lama Bootstrap nyegat keyboard di .dropdown-menu -> TypeError di console (dicek di akhir)
  await pressKey("Escape", "Escape", 27);
  check("Esc nutup menu", await waitFor(`!document.querySelector(".row-context-menu")`));

  // sembunyiin kolom + simpan ke akun (CSRF nyala)
  await clickSelector("#daftar_link [data-table-menu] > button");
  await waitFor(`Boolean(document.querySelector(".table-column-menu"))`);
  await evaluate(`Array.from(document.querySelectorAll(".table-column-menu label")).find((el) => el.textContent.includes("Category")).querySelector("input").click(); true`);
  check("kolom Kategori langsung ilang", await waitFor(`!document.querySelector('#daftar_link th a[title="Sort by Category"]')`));
  const saved = await waitFor(`document.querySelector(".table-column-menu [role=status]").textContent === "Table layout saved"`, 4000);
  check("layout tersimpan ke server (token CSRF diterima)", saved, await evaluate(`document.querySelector(".table-column-menu [role=status]")?.textContent`));
  await navigate(BASE + "/entries/?run=1");
  await waitFor(`${rowCount} === 10`);
  check("abis reload kolom Kategori tetep ilang", !(await evaluate(`Boolean(document.querySelector('#daftar_link th a[title="Sort by Category"]'))`)));
  await evaluate(`document.querySelector('#daftar_link [data-table-menu] > button').click(); true`);
  await waitFor(`Boolean(document.querySelector(".table-column-menu"))`);
  await evaluate(`Array.from(document.querySelectorAll(".table-column-menu button")).find((el) => el.textContent.includes("Restore")).click(); true`);
  await waitFor(`document.querySelector(".table-column-menu [role=status]").textContent === "Table layout saved"`, 4000);

  // halaman kategori
  await navigate(`${BASE}/categories/${info.sub_category_id}`);
  await waitFor(`${rowCount} > 0`);
  check("halaman kategori SAP: tabel React jalan, tanpa kolom Kategori",
    (await evaluate(rowCount)) === 5 && !(await evaluate(`Boolean(document.querySelector('#daftar_link th a[title="Sort by Category"]'))`)),
    String(await evaluate(rowCount)));

  // detail -> balik ke tabel bawa filter
  await navigate(BASE + "/entries/?run=1&title=portal*");
  await waitFor(`${rowCount} > 0`);
  await evaluate(`document.querySelector("#daftar_link tbody tr[data-row-url] td[data-column=title] a").click(); true`);
  await waitFor(`location.pathname.startsWith("/entries/") && location.pathname !== "/entries/" && document.readyState === "complete"`);
  const backHref = await evaluate(`document.querySelector(".app-toolbar a[data-fkey='F3']")?.getAttribute("href")`);
  check("tombol Kembali di detail balik ke tabel + filter", backHref === "/entries/?run=1&title=portal*#daftar_link", backHref);

  // sesi habis: logout di "tab lain" lalu urutkan
  await navigate(BASE + "/entries/?run=1");
  await waitFor(`${rowCount} === 10`);
  await evaluate(`fetch("/auth/logout", {method: "POST", headers: {"X-CSRFToken": document.querySelector('meta[name=csrf-token]').content}}).then(() => true)`);
  await clickSelector('#daftar_link a.col-sort[title="Sort by Title"]');
  check("sesi habis -> pesan + tombol Muat ulang", await waitFor(`document.querySelector("#daftar_link .alert-danger")?.textContent.includes("Your login session expired")`), await evaluate(`document.querySelector("#daftar_link .alert-danger")?.textContent`));
  check("data lama tetep tampil", (await evaluate(rowCount)) === 10);
}, { ignoreProblem: /401/ });
