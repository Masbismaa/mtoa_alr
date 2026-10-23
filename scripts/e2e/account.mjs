// Fitur akun & link baru: lupa password -> reset -> login, ganti password di Settings, edit profil,
// Show password di detail (diambil dari server + kecatat di History), favorit, halaman import.
import { BASE, check, clickSelector, evaluate, login, navigate, pageText, path, runScenario, screenshot, submitForm, waitFor, waitLoad } from "./browser.mjs";

const EMAIL = "e2e.user";
const RESET_PASSWORD = "PasswordReset789";
const SETTINGS_PASSWORD = "PasswordSettings321";
const SECRET = "SandiE2E!123";

await runScenario("table", async () => {
  // 1. lupa password (OTP selalu 123456 di server uji)
  await navigate(BASE + "/auth/login");
  check("halaman login ada link Forgot password", await evaluate(`Boolean(document.querySelector('a[href="/auth/forgot"]'))`));
  await navigate(BASE + "/auth/forgot");
  await submitForm({ email: EMAIL });
  check("minta kode -> halaman reset + pesan netral", (await path()) === "/auth/reset" && (await pageText()).includes("If the email is registered"), await path());
  await submitForm({ otp_code: "123456", password: RESET_PASSWORD, confirm_password: RESET_PASSWORD });
  check("reset berhasil -> ke login", (await path()) === "/auth/login" && (await pageText()).includes("Your password has been reset"), await path());
  await login(EMAIL + "@spindo.com", "123456", RESET_PASSWORD);
  check("login pake password hasil reset", (await path()) === "/");

  // 2. edit profil + ganti password di Settings (sesi ini tetep login)
  await navigate(BASE + "/settings/");
  await submitForm({ full_name: "User E2E Baru", department: "Finance", job_title: "Lead" }, "#profile_form");
  check("profil kesimpen", (await pageText()).includes("Profile saved") && (await evaluate(`document.getElementById("full_name").value`)) === "User E2E Baru");
  await submitForm({ current_password: RESET_PASSWORD, password: SETTINGS_PASSWORD, confirm_password: SETTINGS_PASSWORD }, "#password_form");
  await screenshot("account_settings.png");
  check("ganti password -> tetep login di halaman Settings", (await path()) === "/settings/" && (await pageText()).includes("Password changed"), await path());

  // 3. link dgn password: isinya ga ada di HTML, Show ngambil dari server
  await navigate(BASE + "/entries/new");
  await waitLoad(() => evaluate(`(() => { const form = document.getElementById("entry_form");
    form.querySelector('[name="title"]').value = "Link Rahasia E2E";
    form.querySelector('[name="url"]').value = "https://rahasia-e2e.spindo.com";
    form.querySelector('[name="access_note"]').value = ${JSON.stringify(SECRET)};
    form.requestSubmit(); })()`));
  const detailPath = await path();
  check("link kesimpen", /^\/entries\/\d+$/.test(detailPath), detailPath);
  check("password ga ada di source halaman detail", !(await evaluate("document.documentElement.outerHTML")).includes(SECRET));
  await clickSelector("[data-secret-toggle]");
  check("klik Show -> password tampil", await waitFor(`document.getElementById("access_note_value").textContent === ${JSON.stringify(SECRET)}`));
  await navigate(BASE + detailPath);
  check("History ga nyatet buka password", !(await evaluate(`document.querySelector(".entry-history")?.textContent || ""`)).toLowerCase().includes("reveal"));

  // 4. favorit
  await waitLoad(() => evaluate(`Array.from(document.querySelectorAll(".app-toolbar button")).find((el) => el.textContent.includes("Add to Favorites")).click()`));
  check("Add to Favorites -> tombol jadi Remove", (await pageText()).includes("Remove from Favorites"));
  await screenshot("account_detail.png");
  await navigate(BASE + "/entries/?favorite=1");
  check("menu Favorites cuma isi link favorit", await waitFor(`Array.from(document.querySelectorAll("#daftar_link tbody tr[data-row-url] td[data-column=title]")).map((td) => td.textContent).join() === "Link Rahasia E2E"`),
    await evaluate(`Array.from(document.querySelectorAll("#daftar_link tbody td[data-column=title]")).map((td) => td.textContent).join()`));

  // 5. halaman import + template
  await navigate(BASE + "/entries/import");
  check("halaman import kebuka", (await pageText()).includes("Import from Excel"));
  await screenshot("account_import.png");
  const templateStatus = await evaluate(`fetch("/entries/import/template").then((response) => response.status)`);
  check("template Excel bisa didownload", templateStatus === 200, String(templateStatus));

  // 6. password lama ga berlaku lagi, password dari Settings berlaku
  await waitLoad(() => evaluate(`document.querySelector('.user-menu form[action="/auth/logout"]').requestSubmit()`));
  await navigate(BASE + "/auth/login");
  await submitForm({ email: EMAIL, password: RESET_PASSWORD });
  check("password sebelum diganti ditolak", (await path()) === "/auth/login" && (await pageText()).includes("Incorrect email or password"));
  await login(EMAIL + "@spindo.com", "123456", SETTINGS_PASSWORD);
  check("login pake password dari Settings", (await path()) === "/");
});
