// Folder download di LAPTOP USER (bukan server), per jenis file: "attachment" & "backup".
// - Halaman Manage: kartu [data-download-folder=jenis] + tombol Browse (jendela pilih folder Windows)
// - Halaman yg ada tombol download: link [data-download-kind=jenis] langsung nyimpen ke folder itu
// Pake File System Access API (cuma Chrome/Edge, wajib HTTPS / localhost); browser lain download biasa ke Downloads.
// Folder yg dipilih diinget per browser (IndexedDB), ga pernah dikirim ke server.
(function () {
  "use strict";

  const isSupported = Boolean(window.showDirectoryPicker && window.indexedDB);
  const STORE = "handle";

  function openDb() {
    return new Promise(function (resolve, reject) {
      const request = indexedDB.open("alr_download_folder", 1);
      request.onupgradeneeded = function () { request.result.createObjectStore(STORE); };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
  }

  async function runStore(mode, action) {
    const db = await openDb();
    return new Promise(function (resolve, reject) {
      const request = action(db.transaction(STORE, mode).objectStore(STORE));
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
  }

  function readHandle(kind) {
    return runStore("readonly", function (store) { return store.get(kind); }).catch(function () { return null; });
  }

  // ===== halaman Manage: pilih folder =====
  const unsupportedEl = document.querySelector("[data-download-folder-unsupported]");
  if (unsupportedEl) unsupportedEl.hidden = isSupported;

  if (isSupported) {
    document.querySelectorAll("[data-download-folder]").forEach(function (cardEl) {
      const kind = cardEl.dataset.downloadFolder;
      const nameEl = cardEl.querySelector("[data-download-folder-name]");
      const chooseEl = cardEl.querySelector("[data-download-folder-choose]");
      const resetEl = cardEl.querySelector("[data-download-folder-reset]");
      const messageEl = cardEl.querySelector("[data-download-folder-message]");
      const defaultName = nameEl.textContent;

      function render(handle) {
        nameEl.textContent = handle ? handle.name : defaultName;
        resetEl.hidden = !handle;
      }

      chooseEl.hidden = false;
      chooseEl.addEventListener("click", async function () {
        try {
          const handle = await window.showDirectoryPicker({ id: "alr_" + kind, mode: "readwrite" });
          await runStore("readwrite", function (store) { return store.put(handle, kind); });
          messageEl.textContent = "Files you download will be saved in this folder.";
          render(handle);
        } catch (error) {
          // AbortError = user nutup jendela pilih folder, ga perlu pesan
          if (error.name !== "AbortError") messageEl.textContent = "This folder cannot be used. Choose another one.";
        }
      });

      resetEl.addEventListener("click", async function () {
        await runStore("readwrite", function (store) { return store.delete(kind); }).catch(function () {});
        messageEl.textContent = "Downloads go to the browser's default folder again.";
        render(null);
      });

      readHandle(kind).then(render);
    });
  }

  // ===== tombol download: simpen ke folder pilihan =====
  if (!isSupported) return;
  document.querySelectorAll("[data-download-kind]").forEach(function (linkEl) {
    let handle = null;
    readHandle(linkEl.dataset.downloadKind).then(function (result) { handle = result; });

    linkEl.addEventListener("click", async function (event) {
      if (!handle) return; // belum milih folder: download biasa
      event.preventDefault();
      try {
        // izin nulis harus diminta selagi masih dalam klik user, sebelum await lain
        if (await handle.requestPermission({ mode: "readwrite" }) !== "granted") throw new Error("denied");
        const response = await fetch(linkEl.href, { credentials: "same-origin" });
        if (!response.ok) throw new Error("download failed");
        const fileHandle = await handle.getFileHandle(linkEl.dataset.name, { create: true });
        // dialirin langsung ke file, file gede ga ditampung di memori
        await response.body.pipeTo(await fileHandle.createWritable());
        linkEl.title = "Saved in " + handle.name;
        linkEl.classList.add("btn-success");
      } catch (error) {
        // izin ditolak / nama file ga valid / gagal nulis: download biar tetap dapet filenya
        window.location.href = linkEl.href;
      }
    });
  });
})();
