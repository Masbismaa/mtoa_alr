// Akun baru dari admin + link aktivasi (link lama mati setelah kirim ulang, link cuma sekali pakai), login, dan
// blokir salah password per email+IP. Link aktivasi & OTP acak, dibaca dari output email mode console server uji.
import {
  BASE, check, evaluate, login, navigate, pageText, path, runScenario, screenshot, send, sleep, submitForm, waitLoad,
} from "./browser.mjs";

const LOGIN_SUBJECT = "Kode login ALR";
const NEW_PASSWORD = "PasswordAktivasi1";

await runScenario("auth", async (server) => {
  // kode / link terbaru yg "dikirim" ke email tertentu (format email console: app/services/notification_service.py)
  function latestCode(email, subject) {
    // kode OTP = baris pertama yg isinya cuma 6 angka setelah judul email
    const pattern = new RegExp(`Email ke ${email.replace(/[.]/g, "\\.")}: ${subject} =====[\\s\\S]*?^(\\d{6})\\r?$`, "gm");
    const matchList = [...server.output().matchAll(pattern)];
    return matchList.length ? matchList[matchList.length - 1][1] : null;
  }
  function latestActivationLink() {
    const matchList = [...server.output().matchAll(/http:\/\/127\.0\.0\.1:5077\/auth\/activate\/\S+/g)];
    return matchList.length ? matchList[matchList.length - 1][0] : null;
  }
  const sendActivationLink = () => submitForm({}, 'form[action$="/send-activation"]');

  // 1. admin bikin akun -> Pending Activation, belum bisa login
  await login("e2e.admin@spindo.com", () => latestCode("e2e.admin@spindo.com", LOGIN_SUBJECT));
  await navigate(BASE + "/users/new");
  await screenshot("auth_create_user.png");
  await waitLoad(() => evaluate(`(() => { const form = document.getElementById("user_form");
    form.querySelector('[name="email"]').value = "budi.baru";
    form.querySelector('[name="full_name"]').value = "Budi Baru";
    form.requestSubmit(); })()`));
  let text = await pageText();
  check("Create User -> balik ke daftar + pesan kirim link", (await path()) === "/users/" && text.includes("Send the activation link"), await path());
  check("status Pending Activation", text.includes("Pending Activation"));
  await screenshot("auth_users_pending.png");
  check("menu aksi ada Send Activation Link", await evaluate(`!!document.querySelector('form[action$="/send-activation"]')`));

  const adminCookies = (await send("Network.getAllCookies")).cookies;
  await send("Network.clearBrowserCookies");
  await navigate(BASE + "/auth/login");
  await submitForm({ email: "budi.baru", password: NEW_PASSWORD });
  check("belum aktivasi -> belum bisa login", (await pageText()).includes("Incorrect email or password"));

  // 2. admin kirim link, kirim ulang (abis jeda) -> link lama mati
  await send("Network.setCookies", { cookies: adminCookies });
  await navigate(BASE + "/users/?name=budi.baru%40spindo.com");
  await sendActivationLink();
  check("link aktivasi terkirim", (await pageText()).includes("Activation link sent to budi.baru@spindo.com"));
  const oldLink = latestActivationLink();
  await sendActivationLink();
  check("kirim ulang kecepetan -> disuruh nunggu", (await pageText()).includes("Wait a moment"));
  await sleep(61000);
  await sendActivationLink();
  const newLink = latestActivationLink();
  check("kirim ulang -> link baru", oldLink && newLink && oldLink !== newLink, `${oldLink} vs ${newLink}`);

  // 3. pemilik email buka link -> bikin password 2x -> login biasa (password + OTP)
  await send("Network.clearBrowserCookies");
  await navigate(oldLink);
  check("link lama -> ditolak, balik ke login", (await path()) === "/auth/login" && (await pageText()).includes("invalid or has expired"), await path());
  await navigate(newLink);
  text = await pageText();
  check("halaman Set Your Password + email akun", text.includes("Set Your Password") && text.includes("budi.baru@spindo.com"));
  await screenshot("auth_aktivasi.png");
  await submitForm({ password: NEW_PASSWORD, confirm_password: "BedaSendiri123" });
  check("password beda -> ditolak", (await pageText()).includes("Passwords do not match"));
  await submitForm({ password: NEW_PASSWORD, confirm_password: NEW_PASSWORD });
  check("aktivasi -> ke login + akun aktif", (await path()) === "/auth/login" && (await pageText()).includes("Your account is active"), await path());
  await navigate(newLink);
  check("link yg udah dipake -> ditolak", (await path()) === "/auth/login" && (await pageText()).includes("invalid or has expired"), await path());
  await submitForm({ email: "budi.baru", password: NEW_PASSWORD });
  await submitForm({ otp_code: latestCode("budi.baru@spindo.com", LOGIN_SUBJECT) });
  check("login password + OTP -> masuk beranda", (await path()) === "/", await path());

  // 4. halaman daftar udah ga ada
  await send("Network.clearBrowserCookies");
  await navigate(BASE + "/auth/login");
  check("login ga nawarin daftar", (await pageText()).includes("Contact the ICT admin") && !(await pageText()).includes("Register here"));

  // 5. salah password 3x -> akun dikunci
  for (let index = 0; index < 3; index++) await submitForm({ email: "e2e.user", password: "SalahTerus123" });
  await submitForm({ email: "e2e.user", password: "PasswordKuat123" });
  check("3x salah -> password bener pun diblokir", (await pageText()).includes("Too many login attempts"));
  await screenshot("auth_blokir.png");
  await submitForm({ email: "budi.baru", password: NEW_PASSWORD });
  check("akun lain dari IP yg sama tetep bisa login", (await path()) === "/auth/otp", await path());
});
