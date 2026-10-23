# Uji E2E di browser (Chrome)

Hal yang cuma kebukti di browser beneran: posisi popup, Bootstrap yang nyegat keyboard, scroll halus, request
yang dikirim pas halaman ditutup, progres yang jalan sendiri. Bug-bug itu pernah kejadian dan lolos dari
pytest/Vitest, jadi skenario ini **wajib dijalankan sebelum rilis** (CI kantor belum punya Chrome).

Butuh: Node.js 24, Google Chrome, venv Python project. Tiap skenario nyalain server uji sendiri
(port 5077, database SQLite sementara, CSRF nyala), jadi server ALR biasa ga perlu & ga kesentuh.

```powershell
node scripts/e2e/table.mjs     # tabel link React: urut, filter, halaman, Back, keyboard, klik kanan, layout, sesi habis
node scripts/e2e/auth.mjs      # daftar + verifikasi email, orang lain daftar email yg sama, login, blokir salah password
node scripts/e2e/group.mjs     # detail group: link per halaman
node scripts/e2e/monitor.mjs   # Link Monitoring + worker: peringatan, progres otomatis, selesai
node scripts/e2e/layout.mjs    # tabel versi lama (Users): simpan layout diantrekan & pas pindah halaman
node scripts/e2e/category.mjs  # form link: kategori dipilih bertingkat, boleh berhenti di tingkat mana aja
node scripts/e2e/editor.mjs    # editor teks ala Word di field tambahan: gaya, font, warna, rata, list bertingkat, lolos sanitizer
node scripts/e2e/account.mjs   # lupa & ganti password, edit profil, Show password (kecatat History), favorit, import
node scripts/e2e/sap.mjs       # admin hapus banyak (centang), tombol fungsi F3/F8/Ctrl+S/Shift+F2, variant, status bar
```

Tiap baris hasil `PASS`/`FAIL`, baris terakhir ngecek console browser bersih (ga ada error/peringatan/CSP).
Exit code 1 kalau ada yang `FAIL`. Screenshot disimpen di `scripts/e2e/shots/` (ga di-commit).

Chrome di lokasi lain: `$env:CHROME_PATH = "D:\path\ke\chrome.exe"` sebelum jalanin.

| File | Isi |
|---|---|
| `browser.mjs` | alat bersama: nyalain server uji & Chrome, klik/ketik/tunggu, catat hasil |
| `server.py` | server uji per skenario (data contoh + login `e2e.user` / `e2e.admin`, password `PasswordKuat123`) |
| `worker_monitor.py` | worker uji buat `monitor.mjs` (pemeriksaan jaringan diganti nunggu 1 detik per link) |
