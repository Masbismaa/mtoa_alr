// halaman Backup & Restore: user milih folder di KOMPUTERNYA SENDIRI, tombol Download langsung nyimpen ke situ.
// Pake File System Access API (cuma Chrome/Edge); browser lain kartunya ga muncul, Download jalan biasa ke Downloads.
// Folder yg dipilih diinget per browser (IndexedDB), ga pernah dikirim ke server.
(function () {
  "use strict";

  const cardEl = document.querySelector("[data-download-folder]");
  if (!cardEl || !window.showDirectoryPicker || !window.indexedDB) return;

  const nameEl = cardEl.querySelector("[data-download-folder-name]");
  const chooseEl = cardEl.querySelector("[data-download-folder-choose]");
  const resetEl = cardEl.querySelector("[data-download-folder-reset]");
  const messageEl = cardEl.querySelector("[data-download-folder-message]");
  const DEFAULT_NAME = nameEl.textContent;
  const STORE = "handle";
  const KEY = "backup_download_folder";
  let folderHandle = null;

  function openDb() {
    return new Promise(function (resolve, reject) {
      const request = indexedDB.open("alr_backup", 1);
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

  function render() {
    nameEl.textContent = folderHandle ? folderHandle.name : DEFAULT_NAME;
    resetEl.hidden = !folderHandle;
  }

  chooseEl.addEventListener("click", async function () {
    try {
      folderHandle = await window.showDirectoryPicker({ id: KEY, mode: "readwrite" });
      await runStore("readwrite", function (store) { return store.put(folderHandle, KEY); });
      messageEl.textContent = "Backups you download will be saved in this folder.";
    } catch (error) {
      // AbortError = user nutup jendela pilih folder, ga perlu pesan
      if (error.name !== "AbortError") messageEl.textContent = "This folder cannot be used. Choose another one.";
    }
    render();
  });

  resetEl.addEventListener("click", async function () {
    folderHandle = null;
    try { await runStore("readwrite", function (store) { return store.delete(KEY); }); } catch (error) { /* ga penting */ }
    messageEl.textContent = "Downloads go to the browser's default folder again.";
    render();
  });

  document.querySelectorAll("[data-backup-download]").forEach(function (linkEl) {
    linkEl.addEventListener("click", async function (event) {
      if (!folderHandle) return; // belum milih folder: download biasa
      event.preventDefault();
      try {
        // izin nulis harus diminta selagi masih dalam klik user, sebelum await lain
        if (await folderHandle.requestPermission({ mode: "readwrite" }) !== "granted") {
          messageEl.textContent = "Permission to the folder was denied. Choose the folder again.";
          return;
        }
        messageEl.textContent = "Saving " + linkEl.dataset.name + "...";
        const response = await fetch(linkEl.href, { credentials: "same-origin" });
        if (!response.ok) throw new Error("download failed");
        const fileHandle = await folderHandle.getFileHandle(linkEl.dataset.name, { create: true });
        // dialirin langsung ke file, backup gede ga ditampung di memori
        await response.body.pipeTo(await fileHandle.createWritable());
        messageEl.textContent = linkEl.dataset.name + " saved in " + folderHandle.name + ".";
      } catch (error) {
        messageEl.textContent = "Saving to the folder failed. Downloading the normal way instead.";
        window.location.href = linkEl.href;
      }
    });
  });

  cardEl.hidden = false;
  runStore("readonly", function (store) { return store.get(KEY); })
    .then(function (handle) { folderHandle = handle || null; render(); })
    .catch(render);
})();
