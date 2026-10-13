// Daftar + verifikasi email (termasuk skenario "orang lain daftar pakai email yg sama"), login, dan blokir
// salah password per email+IP. Kode verifikasi/OTP acak, dibaca dari output email mode console server uji.
import {
  BASE, check, evaluate, navigate, pageText, path, runScenario, screenshot, send, submitForm,
} from "./browser.mjs";

const REGISTER = { full_name: "Budi Baru", department: "ICT", job_title: "Staff", password: "PasswordKuat123", confirm_password: "PasswordKuat123" };
const REGISTER_SUBJECT = "ALR registration verification code";
const LOGIN_SUBJECT = "ALR login code";

async function getCookies() { return (await send("Network.getAllCookies")).cookies; }
async function useCookies(cookieList) {
  await send("Network.clearBrowserCookies");
  if (cookieList.length) await send("Network.setCookies", { cookies: cookieList });
}

await runScenario("auth", async (server) => {
  // kode terbaru yg "dikirim" ke email tertentu (format email console: app/services/notification_service.py)
  function latestCode(email, subject) {
    const pattern = new RegExp(`Email ke ${email.replace(/[.]/g, "\\.")}: ${subject} =====\\r?\\n${subject}: (\\d{6})`, "g");
    const matchList = [...server.output().matchAll(pattern)];
    return matchList.length ? matchList[matchList.length - 1][1] : null;
  }

  // 1. daftar email baru -> verifikasi -> login
  await navigate(BASE + "/auth/register");
  await submitForm({ email: "budi.baru", ...REGISTER });
  check("daftar -> halaman verifikasi email", (await path()) === "/auth/register/verify", await path());
  const text = await pageText();
  check("email disamarkan + pesan cek email", text.includes("bu*******@spindo.com") && text.includes("Check your email"));
  check("tombol kirim ulang nunggu jeda", await evaluate("document.getElementById('resend_button').disabled"));
  await submitForm({ otp_code: "000000" });
  check("kode salah -> pesan Incorrect OTP code", (await pageText()).includes("Incorrect OTP code"));

  const budiCookies = await getCookies();
  await navigate(BASE + "/auth/login");
  await submitForm({ email: "budi.baru", password: "PasswordKuat123" });
  check("belum verifikasi -> belum bisa login", (await pageText()).includes("Incorrect email or password"));
  await useCookies(budiCookies);
  await navigate(BASE + "/auth/register/verify");
  await submitForm({ otp_code: latestCode("budi.baru@spindo.com", REGISTER_SUBJECT) });
  check("kode benar -> ke login + akun aktif", (await path()) === "/auth/login" && (await pageText()).includes("Email verified"), await path());
  await submitForm({ email: "budi.baru", password: "PasswordKuat123" });
  await submitForm({ otp_code: latestCode("budi.baru@spindo.com", LOGIN_SUBJECT) });
  check("login password + OTP -> masuk beranda", (await path()) === "/", await path());

  // 2. pemilik daftar, orang lain daftar email yg sama, pemilik verifikasi kodenya sendiri
  await useCookies([]);
  await navigate(BASE + "/auth/register");
  await submitForm({ email: "cici.asli", ...REGISTER, full_name: "Cici Asli", password: "PasswordPemilik1", confirm_password: "PasswordPemilik1" });
  const ownerCode = latestCode("cici.asli@spindo.com", REGISTER_SUBJECT);
  const ownerCookies = await getCookies();
  await useCookies([]);
  await navigate(BASE + "/auth/register");
  await submitForm({ email: "cici.asli", ...REGISTER, full_name: "Penyerang", password: "PasswordLain22", confirm_password: "PasswordLain22" });
  const otherCode = latestCode("cici.asli@spindo.com", REGISTER_SUBJECT);
  check("2 percobaan dapet kode beda", ownerCode && otherCode && ownerCode !== otherCode, `${ownerCode} vs ${otherCode}`);
  await useCookies(ownerCookies);
  await navigate(BASE + "/auth/register/verify");
  await submitForm({ otp_code: otherCode });
  check("kode punya orang lain di halaman pemilik -> salah", (await pageText()).includes("Incorrect OTP code"));
  await submitForm({ otp_code: ownerCode });
  check("kode pemilik sendiri -> akun jadi", (await path()) === "/auth/login", await path());
  await submitForm({ email: "cici.asli", password: "PasswordLain22" });
  check("password orang lain ga berlaku", (await pageText()).includes("Incorrect email or password"));
  await submitForm({ email: "cici.asli", password: "PasswordPemilik1" });
  check("password pemilik berlaku", (await path()) === "/auth/otp", await path());

  // 3. daftar pakai email yg udah terdaftar -> tampilan sama
  await useCookies([]);
  await navigate(BASE + "/auth/register");
  await submitForm({ email: "e2e.user", ...REGISTER });
  const existingText = await pageText();
  check("email terdaftar -> tampilan sama (ga ada 'sudah terdaftar')",
    (await path()) === "/auth/register/verify" && existingText.includes("Check your email") && !existingText.includes("already registered"));
  await submitForm({ otp_code: "123456" });
  check("email terdaftar: kode apa pun -> Incorrect OTP code", (await pageText()).includes("Incorrect OTP code"));

  // 4. blokir salah password per email+IP
  await navigate(BASE + "/auth/login");
  for (let index = 0; index < 5; index++) await submitForm({ email: "e2e.user", password: "SalahTerus123" });
  await submitForm({ email: "e2e.user", password: "PasswordKuat123" });
  check("5x salah -> password bener pun diblokir dari perangkat ini", (await pageText()).includes("Too many login attempts from this device"));
  await screenshot("auth_blokir.png");
  await submitForm({ email: "budi.baru", password: "PasswordKuat123" });
  check("akun lain dari IP yg sama tetep bisa login", (await path()) === "/auth/otp", await path());
});
