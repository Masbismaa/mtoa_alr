# Frontend React (tabel link ALV)

Dokumen ini buat siapa pun yang mau ngubah atau merawat bagian React di ALR.
Baca bagian **Aturan wajib** dulu sebelum ngubah apa pun.

## Cakupan

Sebagian besar halaman ALR tetap dirender server (Flask + Jinja + Tabler). React **cuma** dipakai di bagian
yang interaksinya berat: tabel link ala ALV SAP di dua halaman:

| Halaman | URL | API yg dipanggil React |
|---|---|---|
| Daftar Link | `/entries/?run=1` | `/entries/table-data` |
| Isi satu kategori | `/categories/<id>` | `/categories/<id>/table-data` |

Yang dikerjain React di tabel itu, semuanya **tanpa reload halaman**:

- urutkan kolom, filter per kolom, pindah halaman (URL browser ikut berubah, tombol Back/Forward jalan)
- geser lebar kolom, sembunyikan kolom (disimpan ke akun lewat `POST /settings/table-layout`)
- baris aktif + keyboard (panah atas/bawah, Home/End, Enter buka detail)
- menu klik kanan (juga Shift+F10 / tombol Menu): Buka, Salin nilai sel, Salin baris
- pesan jelas kalau sesi login habis / jaringan putus, data lama tetep tampil

Tabel **Users** dan **Audit Logs** masih versi Jinja lama (`components/data_table.html` + `js/components/data_table.js`).
Kalau mau dipindah ke React, ikuti pola di bawah (lihat "Nambah halaman React baru").

## Alur data

```
Browser buka /entries/?run=1
  └─ Flask: entries.index
       └─ entry_table_service.build_entry_table_payload(user, args, scope)   <- SATU-SATUNYA tempat logika tabel
            ├─ filter + hak akses (access_entry_service.search_visible_entries)
            ├─ layout kolom user (preference_service.get_table_layout)
            └─ label, tanggal WIB, URL detail + alamat balik, teks kosong, URL export
       └─ template: components/entry_table.html
            <div id="daftar_link" data-entry-table='{payload JSON}'>   <- data awal, tabel langsung tampil
            <script type="module" src="/static/dist/assets/entry_table-<hash>.js">

React (frontend/src/entry_table/main.jsx) baca data-entry-table -> render EntryTable
User klik judul kolom / filter / halaman
  └─ useTableData.load(kriteria, halaman)
       └─ GET /entries/table-data?<kriteria>   -> build_entry_table_payload yg SAMA
       └─ payload diganti seluruhnya pake balasan server
       └─ history.pushState(URL halaman)        -> refresh/bookmark/Back tetep bener
       └─ event "alr:table-query-changed"       -> js/components/selection_panel.js nyamain isian
                                                  panel Kriteria Pencarian (biar "Jalankan" ga ngirim nilai lama)
```

## Aturan wajib

1. **Semua logika ada di server.** Hak akses, filter, urutan, label, format tanggal, URL: di Python
   (`app/services/entry_table_service.py`). React cuma nampilin. Jangan pernah nyaring/ngurutin data di browser.
2. **Jangan pakai `dangerouslySetInnerHTML`.** React otomatis nampilin teks sebagai teks (aman dari XSS).
3. **Jangan pakai class `.dropdown-menu` di komponen React.** Bootstrap (`tabler.min.js`) dengerin panah/Esc di semua
   `.dropdown-menu` lewat `document` fase *capture* (jalan sebelum React, ga bisa dicegah) dan nyari tombol
   `data-bs-toggle` yg ga ada -> `TypeError` di console. Pake class `.app-menu` (`static/css/components/table.css`),
   tampilannya sama persis.
4. **Elemen `position: fixed` (popup, menu klik kanan) dirender lewat portal ke `document.body`.**
   Kartu punya animasi `transform` (`app-fade-up`) yang bikin `fixed` di dalemnya dihitung dari kartu, bukan layar.
5. **Popup jangan ditutup pake event `scroll`.** Sisa scroll halus (`scroll-behavior: smooth`) bisa dateng abis
   popup kebuka dan langsung nutup lagi. Pake `wheel` / `touchmove` / `resize` / klik di luar.
6. **Request lama wajib dibatalin** (`AbortController` di `useTableData.js`), biar klik cepet berkali-kali ga
   nampilin hasil klik sebelumnya.
7. **Hasil build (`app/static/dist/`) ikut di-commit.** Server production & CI Python ga punya Node.
   Abis ngubah apa pun di `frontend/src`, jalankan `npm run build` lalu commit `app/static/dist` juga.
   Job CI `frontend_test` gagal kalau lupa.
8. **Script inline dilarang** (CSP `script-src 'self'`). Data ke React lewat atribut `data-*` JSON, bukan `<script>`.

## Struktur file

```
frontend/
  package.json, package-lock.json   versi library dikunci persis
  vite.config.js                    build ke app/static/dist + konfigurasi test (Vitest)
  src/
    shared/                         dipake bareng semua komponen React
      api.js                        getJson/postJson: format balasan ALR, CSRF, sesi habis (401), redirect
      queryString.js                kriteria {key: [nilai]} <-> query string
      clipboard.js                  salin teks (ada cadangan buat http biasa)
      statusBar.js                  kirim pesan ke status bar bawah (window.AlrStatusBar)
      navigation.js                 pindah halaman / reload (dibungkus biar bisa di-mock di test)
      events.js                     isPlainClick, isInteractiveTarget
      Icon.jsx                      ikon SVG (path disalin dari templates/components/icon.html)
      ErrorBoundary.jsx             kalau komponen error: pesan + tombol Muat ulang, bukan kartu kosong
    entry_table/
      main.jsx                      titik masuk: cari [data-entry-table], pasang React
      EntryTable.jsx                komponen utama (judul, Export/Kolom, tabel, navigasi halaman, menu klik kanan)
      useTableData.js               ambil data, batalin request lama, history, event ke panel kriteria
      useColumnLayout.js            lebar & kolom tersembunyi + simpan ke akun (debounce, keepalive pas tutup halaman)
      useActiveRow.js               baris aktif & fokus keyboard
      columns.jsx                   isi sel per kolom + teks buat "Salin"
      TableHead.jsx                 judul kolom (urut), geser lebar, baris filter
      ColumnMenu.jsx, RowContextMenu.jsx, Pagination.jsx, EmptyState.jsx, CopyButton.jsx
      *.test.jsx                    test Vitest
    test/                           setup Vitest + contoh payload (makePayload.js)

app/services/entry_table_service.py      bikin payload (dipake halaman & API)
app/templates/components/entry_table.html tempat React dipasang + tag script
app/utils/vite_manifest.py               {{ vite_tags("entry_table") }} -> tag script ber-hash dari manifest Vite
app/security/role_guard.py               api_login_required: API belum login -> 401 JSON (bukan redirect)
tests/test_entry_table_api.py            test API, kontrak bentuk data, keamanan, manifest
```

## Development

Butuh **Node.js 24 LTS** (`winget install OpenJS.NodeJS.LTS`) cuma di laptop developer.

```powershell
cd frontend
npm ci              # pasang library persis sesuai package-lock.json
npm run watch       # build ulang otomatis tiap file berubah (terminal ini biarin jalan)
```

Di terminal lain jalankan Flask kayak biasa (`python -m flask --app run run`). Abis ngubah file React,
refresh browser. Flask baca ulang `manifest.json` sendiri kalau berubah.

Sebelum commit:

```powershell
cd frontend
npm test            # test React (Vitest)
npm run build       # build production ke app/static/dist
cd ..
.\.venv\Scripts\python.exe -m pytest -q
git add frontend app/static/dist   # dist WAJIB ikut
```

## Nambah kolom di tabel link

1. `app/schemas/table_schema.py` -> `ENTRY_COLUMN_LIST`: judul, lebar, bisa diurutin/disembunyiin, filter_key.
2. `app/services/entry_table_service.py` -> `build_entry_row`: tambah data yg dibutuhin kolom itu.
   Update juga `ROW_KEY_SET` di `tests/test_entry_table_api.py` dan `makeRow` di `frontend/src/test/makePayload.js`.
3. `frontend/src/entry_table/columns.jsx` -> `COLUMN_RENDERER_DICT`: cara nampilin + `copyValue`.
   (Lupa langkah ini: sel tampil "-" + peringatan di console, ga crash.)
4. Kalau bisa diurutin: `app/services/access_entry_service.py` -> `ENTRY_SORT_COLUMN_DICT`.
5. Kalau kolomnya masuk Excel: `app/services/export_service.py`.

## Nambah halaman React baru (misal tabel Users)

1. Bikin builder payload di `app/services/` (pola sama kayak `entry_table_service.py`) + route halaman & route API
   (`@api_login_required`, balas `success_response(data=...)`).
2. Template: `<div data-xxx='{{ payload | tojson }}'>` + `{{ vite_tags("xxx") }}`.
3. `frontend/src/xxx/main.jsx` + tambah entry di `rollupOptions.input` (`vite.config.js`).
4. Pake lagi `shared/` & hook yg ada. Test: Vitest buat komponen, pytest buat API & kontrak data.

## Test

| Apa | Perintah | Isinya |
|---|---|---|
| Python | `pytest -q` | API, hak akses, kontrak bentuk data, data awal = balasan API, XSS, CSP, manifest |
| React | `cd frontend && npm test` | urut/filter/halaman, request balapan, layout + CSRF + keepalive, keyboard, menu klik kanan, sesi habis, respon rusak |

Hal yg cuma kebukti di browser beneran (posisi popup, CSS, Bootstrap, scroll halus) dites manual sebelum rilis:
login -> Daftar Link -> urutkan, filter kolom, halaman 2, Back browser, klik kanan baris (menu muncul di titik klik),
Esc, sembunyikan kolom lalu reload, buka detail lalu Kembali. Console browser (F12) harus bersih.

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| Error 500 `manifest.json belum ada` | `app/static/dist` belum di-build / ga ke-commit | `cd frontend && npm ci && npm run build` |
| Error `Entry Vite "xxx" ga ada di manifest` | salah nama di `vite_tags()` | samain dgn kunci `rollupOptions.input` |
| Tabel nyangkut "Memuat tabel…" | script React gagal dimuat / error | buka console (F12): file 404 -> build ulang; error CSP -> ada script inline |
| Pesan "Sesi login habis" | cookie login udah ga berlaku (logout di tab lain / 8 jam) | klik Muat ulang, login lagi (emang disengaja) |
| Kolom baru tampil "-" | renderer belum ada di `columns.jsx` | lihat "Nambah kolom" langkah 3 |
