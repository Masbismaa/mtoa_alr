// konfigurasi build & test komponen React ALR.
// hasil build: app/static/dist/ (+ .vite/manifest.json yg dibaca Flask lewat app/utils/vite_manifest.py)
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const outDir = fileURLToPath(new URL("../app/static/dist", import.meta.url));

export default defineConfig({
  plugins: [react()],
  // URL file hasil build di server Flask (folder static)
  base: "/static/dist/",
  build: {
    outDir,
    emptyOutDir: true,
    // manifest = peta "nama entry -> nama file ber-hash", dibaca Flask buat nulis tag <script>
    manifest: true,
    // polyfill modulepreload nyuntik script inline -> bentrok sama CSP script-src 'self', jadi dimatiin
    modulePreload: { polyfill: false },
    // satu entry per halaman yg pake React. Nambah halaman baru = tambah entry di sini
    rollupOptions: {
      input: {
        entry_table: fileURLToPath(new URL("./src/entry_table/main.jsx", import.meta.url)),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    restoreMocks: true,
  },
});
