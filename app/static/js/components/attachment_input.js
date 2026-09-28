// pilih lampiran: tampilin daftar file + cek ukuran/tipe/jumlah sebelum dikirim.
// ini cuma biar enak dipake, pengecekan beneran tetep di server
(function () {
  "use strict";

  const inputEl = document.querySelector("[data-attachment-input]");
  if (!inputEl) return;

  const dropzoneEl = inputEl.closest("[data-dropzone]");
  const previewEl = document.querySelector("[data-attachment-preview]");
  const warningEl = document.querySelector("[data-attachment-warning]");
  const maxTotal = parseInt(inputEl.dataset.maxTotal, 10) || 5;
  const maxSize = parseInt(inputEl.dataset.maxSize, 10) || 10485760;
  const existingCount = parseInt(inputEl.dataset.existingCount, 10) || 0;
  const allowedExtensionList = (inputEl.dataset.allowedExtension || "").split(",");

  function formatSize(sizeBytes) {
    if (sizeBytes < 1024) return sizeBytes + " B";
    if (sizeBytes < 1048576) return (sizeBytes / 1024).toFixed(1) + " KB";
    return (sizeBytes / 1048576).toFixed(1) + " MB";
  }

  function getExtension(fileName) {
    const dotIndex = fileName.lastIndexOf(".");
    return dotIndex >= 0 ? fileName.slice(dotIndex + 1).toLowerCase() : "";
  }

  // cek 1 file, balikin pesan masalahnya (kosong = aman)
  function getProblem(file) {
    if (!allowedExtensionList.includes(getExtension(file.name))) return "tipe file tidak diizinkan";
    if (file.size === 0) return "file kosong";
    if (file.size > maxSize) return "lebih dari " + Math.floor(maxSize / 1048576) + "MB";
    return "";
  }

  // lampiran lama yg ga dicentang hapus
  function countKeptExisting() {
    const checkedCount = document.querySelectorAll("[data-attachment-delete]:checked").length;
    return existingCount - checkedCount;
  }

  // gabungin file lama + baru (FileList ga bisa diedit langsung, jadi pake DataTransfer)
  function setFileList(fileList) {
    const dataTransfer = new DataTransfer();
    fileList.forEach(function (file) {
      dataTransfer.items.add(file);
    });
    inputEl.files = dataTransfer.files;
    render();
  }

  function render() {
    previewEl.replaceChildren();
    const fileList = Array.from(inputEl.files);
    let hasProblem = false;

    fileList.forEach(function (file, index) {
      const problem = getProblem(file);
      hasProblem = hasProblem || Boolean(problem);

      const itemEl = document.createElement("li");
      itemEl.className = "attachment-item is-entering" + (problem ? " is-invalid" : "");

      // pake textContent biar nama file aneh ga dijalanin sebagai HTML
      const nameEl = document.createElement("span");
      nameEl.className = "attachment-name";
      nameEl.textContent = file.name;
      nameEl.title = file.name;

      const metaEl = document.createElement("small");
      metaEl.textContent = problem || formatSize(file.size);

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "btn-icon btn-icon-small btn-icon-danger";
      removeButton.setAttribute("aria-label", "Batal pilih " + file.name);
      removeButton.textContent = "\u00d7";
      removeButton.addEventListener("click", function () {
        setFileList(Array.from(inputEl.files).filter(function (_, fileIndex) {
          return fileIndex !== index;
        }));
      });

      itemEl.append(nameEl, metaEl, removeButton);
      previewEl.append(itemEl);
    });

    const totalCount = countKeptExisting() + fileList.length;
    if (totalCount > maxTotal) {
      warningEl.textContent = "Kebanyakan file: maks " + maxTotal + " (termasuk lampiran yang sudah ada).";
    } else if (hasProblem) {
      warningEl.textContent = "Ada file yang bakal ditolak, cek yang warna merah.";
    } else {
      warningEl.textContent = "";
    }
  }

  inputEl.addEventListener("change", render);

  // centang "Hapus" di lampiran lama -> coret namanya + hitung ulang
  document.querySelectorAll("[data-attachment-delete]").forEach(function (checkboxEl) {
    checkboxEl.addEventListener("change", function () {
      checkboxEl.closest(".attachment-item").classList.toggle("is-marked-delete", checkboxEl.checked);
      render();
    });
  });

  // efek drag & drop
  ["dragenter", "dragover"].forEach(function (eventName) {
    dropzoneEl.addEventListener(eventName, function (event) {
      event.preventDefault();
      dropzoneEl.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach(function (eventName) {
    dropzoneEl.addEventListener(eventName, function (event) {
      event.preventDefault();
      dropzoneEl.classList.remove("is-dragover");
    });
  });

  // file yg di-drop ditambahin ke yg udah dipilih
  dropzoneEl.addEventListener("drop", function (event) {
    if (!event.dataTransfer || !event.dataTransfer.files.length) return;
    setFileList(Array.from(inputEl.files).concat(Array.from(event.dataTransfer.files)));
  });
})();