// Alat bersama uji E2E: nyalain server uji (scripts/e2e/server.py) + Chrome headless, terus nyetir Chrome
// lewat Chrome DevTools Protocol (CDP) tanpa library tambahan. Dipake semua skenario di folder ini.
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const PROJECT_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
export const PYTHON = join(PROJECT_DIR, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
export const BASE = "http://127.0.0.1:5077";
const CHROME = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const SHOT_DIR = join(PROJECT_DIR, "scripts", "e2e", "shots");
const DEBUG_PORT = 9333;

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const problems = [];
const eventWaiters = [];
let ws = null;
let chrome = null;
let nextId = 1;
const pending = new Map();
const cleanupList = [];

export function check(name, ok, detail = "") {
  results.push(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  -> " + detail : ""}`);
}

export function onEvent(listener) {
  eventWaiters.push(listener);
}

// server uji: database SQLite baru di folder sementara, CSRF nyala. Return {info, output(), dbPath}
export async function startServer(scenario) {
  const dbPath = join(mkdtempSync(join(tmpdir(), "alr-e2e-db-")), "e2e.sqlite");
  const env = { ...process.env, E2E_DB_PATH: dbPath, PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" };
  const server = spawn(PYTHON, [join(PROJECT_DIR, "scripts", "e2e", "server.py"), scenario], { cwd: PROJECT_DIR, env });
  cleanupList.push(() => server.kill());
  let output = "";
  server.stdout.on("data", (chunk) => { output += chunk; });
  server.stderr.on("data", (chunk) => { output += chunk; });
  for (let attempt = 0; attempt < 100; attempt++) {
    const match = output.match(/^SIAP (.*)$/m);
    if (match) {
      try {
        await fetch(BASE + "/health");
        return { info: JSON.parse(match[1]), output: () => output, dbPath, env };
      } catch (error) { /* server belum nerima koneksi */ }
    }
    await sleep(200);
  }
  throw new Error("server uji ga nyala:\n" + output.slice(-2000));
}

// proses tambahan yg ikut dimatiin di akhir (misal worker monitoring)
export function startProcess(args, env) {
  const child = spawn(PYTHON, args, { cwd: PROJECT_DIR, env, stdio: "ignore" });
  cleanupList.push(() => child.kill());
  return child;
}

export async function startBrowser() {
  const profileDir = mkdtempSync(join(tmpdir(), "alr-e2e-chrome-"));
  chrome = spawn(CHROME, [
    "--headless=new", `--remote-debugging-port=${DEBUG_PORT}`, `--user-data-dir=${profileDir}`,
    "--no-first-run", "--no-default-browser-check", "--window-size=1366,900", "about:blank",
  ], { stdio: "ignore" });
  cleanupList.push(() => chrome.kill());
  let wsUrl = null;
  for (let attempt = 0; attempt < 50 && !wsUrl; attempt++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`)).json();
      wsUrl = list.find((item) => item.type === "page")?.webSocketDebuggerUrl;
    } catch (error) { /* chrome belum siap */ }
    if (!wsUrl) await sleep(200);
  }
  if (!wsUrl) throw new Error(`Chrome ga nyala (path: ${CHROME}, atur lewat env CHROME_PATH)`);
  ws = new WebSocket(wsUrl);
  await new Promise((resolve) => ws.addEventListener("open", resolve));
  ws.addEventListener("message", (message) => {
    const data = JSON.parse(message.data);
    if (data.id && pending.has(data.id)) {
      const { resolve, reject } = pending.get(data.id);
      pending.delete(data.id);
      if (data.error) reject(new Error(JSON.stringify(data.error)));
      else resolve(data.result);
      return;
    }
    // semua error/peringatan di console & pelanggaran CSP dicatat; di akhir harus kosong
    if (data.method === "Runtime.exceptionThrown") {
      problems.push("EXCEPTION " + (data.params.exceptionDetails.exception?.description || data.params.exceptionDetails.text));
    }
    if (data.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(data.params.type)) {
      problems.push(`CONSOLE.${data.params.type} ` + data.params.args.map((arg) => arg.value ?? arg.description).join(" "));
    }
    if (data.method === "Log.entryAdded" && ["error", "warning"].includes(data.params.entry.level)) {
      problems.push(`LOG.${data.params.entry.level} ${data.params.entry.source}: ${data.params.entry.text} ${data.params.entry.url || ""}`);
    }
    eventWaiters.slice().forEach((waiter) => waiter(data));
  });
  for (const domain of ["Page", "Runtime", "Log", "Network"]) await send(`${domain}.enable`);
}

export function send(method, params = {}) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

export async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error("eval error: " + JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

export async function waitFor(expression, timeout = 5000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await evaluate(expression)) return true;
    await sleep(100);
  }
  return false;
}

// jalanin aksi yg bikin pindah halaman, tunggu halaman barunya selesai dimuat
export async function waitLoad(action) {
  const loaded = new Promise((resolve) => {
    const waiter = (data) => {
      if (data.method === "Page.loadEventFired") {
        eventWaiters.splice(eventWaiters.indexOf(waiter), 1);
        resolve();
      }
    };
    eventWaiters.push(waiter);
  });
  await action();
  await loaded;
}

export const navigate = (url) => waitLoad(() => send("Page.navigate", { url }));
export const pageText = () => evaluate("document.body.innerText");
export const path = () => evaluate("location.pathname");

// isi field form (pakai name) terus klik tombol submit-nya
export async function submitForm(fieldDict, formSelector = "form") {
  await waitLoad(() => evaluate(`(() => { const form = document.querySelector(${JSON.stringify(formSelector)});
    for (const [name, value] of Object.entries(${JSON.stringify(fieldDict)})) form.querySelector('[name="' + name + '"]').value = value;
    form.querySelector('[type=submit]').click(); })()`));
}

// login 2 langkah. otpCode: string, atau fungsi yg ngasih kode (skenario yg OTP-nya acak)
export async function login(email, otpCode = "123456", password = "PasswordKuat123") {
  await navigate(BASE + "/auth/login");
  await submitForm({ email, password });
  if ((await path()) !== "/auth/otp") throw new Error("login gagal di langkah password: " + (await pageText()).slice(0, 200));
  await submitForm({ otp_code: typeof otpCode === "function" ? otpCode() : otpCode });
  if ((await path()) !== "/") throw new Error("login gagal di langkah OTP: " + (await pageText()).slice(0, 200));
}

export async function screenshot(name) {
  mkdirSync(SHOT_DIR, { recursive: true });
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(SHOT_DIR, name), Buffer.from(data, "base64"));
}

export async function clickSelector(selector, button = "left") {
  const box = await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return null;
    el.scrollIntoView({block: "center", behavior: "instant"}); const r = el.getBoundingClientRect(); return {x: r.left + Math.min(r.width/2, 30), y: r.top + r.height/2}; })()`);
  if (!box) throw new Error("ga ketemu: " + selector);
  for (const type of ["mousePressed", "mouseReleased"]) {
    await send("Input.dispatchMouseEvent", { type, x: box.x, y: box.y, button, clickCount: 1 });
  }
  return box;
}

export async function pressKey(key, code, keyCode, modifiers = 0) {
  await send("Input.dispatchKeyEvent", { type: "keyDown", key, code, windowsVirtualKeyCode: keyCode, modifiers });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode: keyCode, modifiers });
}

export const typeText = (text) => send("Input.insertText", { text });

// jalanin skenario: siapin server & browser, cetak hasil, beresin semua proses. Exit 1 kalau ada yg gagal.
// ignoreProblem: pola pesan console yg emang disengaja (misal 401 di tes sesi habis)
export async function runScenario(scenario, body, { ignoreProblem = null } = {}) {
  try {
    const server = await startServer(scenario);
    await startBrowser();
    await body(server);
  } catch (error) {
    results.push("FAIL  skrip berhenti: " + error.message);
  } finally {
    const unexpected = problems.filter((text) => !(ignoreProblem && ignoreProblem.test(text)));
    results.push(unexpected.length ? "FAIL  error/peringatan browser:\n    " + unexpected.join("\n    ") : "PASS  ga ada error console / CSP");
    console.log(`== ${basename(process.argv[1])} ==\n` + results.join("\n"));
    if (ws) ws.close();
    cleanupList.reverse().forEach((cleanup) => cleanup());
    process.exit(results.some((line) => line.startsWith("FAIL")) ? 1 : 0);
  }
}
