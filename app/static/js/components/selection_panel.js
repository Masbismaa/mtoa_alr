// panel Kriteria Pencarian (Select Screen ala SAP):
// dialog Multi Selection (banyak nilai, sertakan / kecualikan), ringkasan pilihan yg dicentang,
// isian kosong ga ikut dikirim biar URL rapi, tekan "/" buat langsung ke Cari cepat
(function () {
  "use strict";

  const formEl = document.querySelector("[data-selection-form]");
  if (!formEl) return;

  const MAX_VALUE_COUNT = 20;
  const EXCLUDE_SUFFIX = "__not";
  const dialogEl = document.getElementById("selection_dialog");
  const includeEl = document.getElementById("selection_include");
  const excludeEl = document.getElementById("selection_exclude");
  let activeKey = null;

  function splitLine(text) {
    return text.split(/\r?\n/).map(function (line) { return line.trim(); }).filter(Boolean);
  }

  // jumlah nilai di tiap kotak + peringatan kalau lewat batas. Kelebihan ga dibuang diem-diem: tombol Pakai dikunci
  const applyButton = dialogEl ? dialogEl.querySelector("[data-selection-apply]") : null;
  function updateCounter() {
    let isOverLimit = false;
    [["include", includeEl], ["exclude", excludeEl]].forEach(function (pair) {
      const count = splitLine(pair[1].value).length;
      const counterEl = dialogEl.querySelector('[data-selection-counter="' + pair[0] + '"]');
      const overCount = count - MAX_VALUE_COUNT;
      counterEl.textContent = count + " / " + MAX_VALUE_COUNT + " nilai" + (overCount > 0 ? " — kelebihan " + overCount + ", kurangi dulu" : "");
      counterEl.classList.toggle("text-danger", overCount > 0);
      pair[1].classList.toggle("is-invalid", overCount > 0);
      if (overCount > 0) isOverLimit = true;
    });
    applyButton.disabled = isOverLimit;
    applyButton.title = isOverLimit ? "Maksimal " + MAX_VALUE_COUNT + " nilai per kotak" : "";
  }

  function getTextBox(key) {
    return formEl.querySelector('[data-selection-text="' + key + '"]');
  }

  function readValue(key) {
    const boxEl = getTextBox(key);
    const mainValue = boxEl.querySelector('input[type="text"]').value.trim();
    const extraIncludeList = Array.from(boxEl.querySelectorAll('[data-selection-extra][name="' + key + '"]'), function (el) { return el.value; });
    const excludeList = Array.from(boxEl.querySelectorAll('[name="' + key + EXCLUDE_SUFFIX + '"]'), function (el) { return el.value; });
    return { includeList: [mainValue].concat(extraIncludeList).filter(Boolean), excludeList: excludeList };
  }

  function buildHidden(name, value) {
    const inputEl = document.createElement("input");
    inputEl.type = "hidden";
    inputEl.name = name;
    inputEl.value = value;
    inputEl.dataset.selectionExtra = "";
    return inputEl;
  }

  // nilai pertama masuk ke isian yg keliatan, sisanya jadi input tersembunyi
  function writeValue(key, includeList, excludeList) {
    const boxEl = getTextBox(key);
    boxEl.querySelectorAll("[data-selection-extra]").forEach(function (el) { el.remove(); });
    boxEl.querySelector('input[type="text"]').value = includeList[0] || "";
    includeList.slice(1).forEach(function (value) { boxEl.appendChild(buildHidden(key, value)); });
    excludeList.forEach(function (value) { boxEl.appendChild(buildHidden(key + EXCLUDE_SUFFIX, value)); });

    const countEl = boxEl.parentElement.querySelector("[data-selection-count]");
    const extraCount = Math.max(includeList.length - 1, 0) + excludeList.length;
    countEl.textContent = "+" + extraCount;
    countEl.hidden = extraCount === 0;
  }

  function closeDialog() {
    if (dialogEl.open) dialogEl.close();
    activeKey = null;
  }

  formEl.querySelectorAll("[data-selection-multi]").forEach(function (buttonEl) {
    buttonEl.addEventListener("click", function () {
      if (!dialogEl || typeof dialogEl.showModal !== "function") return;
      activeKey = buttonEl.dataset.selectionMulti;
      const valueDict = readValue(activeKey);
      dialogEl.querySelector("[data-selection-dialog-label]").textContent = buttonEl.dataset.selectionLabel;
      includeEl.value = valueDict.includeList.join("\n");
      excludeEl.value = valueDict.excludeList.join("\n");
      updateCounter();
      dialogEl.showModal();
      includeEl.focus();
    });
  });

  if (dialogEl) {
    includeEl.addEventListener("input", updateCounter);
    excludeEl.addEventListener("input", updateCounter);
    applyButton.addEventListener("click", function () {
      if (applyButton.disabled) return;
      if (activeKey) writeValue(activeKey, splitLine(includeEl.value), splitLine(excludeEl.value));
      closeDialog();
    });
    dialogEl.querySelector("[data-selection-cancel]").addEventListener("click", closeDialog);
    dialogEl.querySelector("[data-selection-clear]").addEventListener("click", function () {
      includeEl.value = "";
      excludeEl.value = "";
      updateCounter();
      includeEl.focus();
    });
    dialogEl.addEventListener("cancel", function () { activeKey = null; });
  }

  // tulisan di tombol pilihan ngikutin yg dicentang
  function updateChoiceSummary(choiceEl) {
    const summaryEl = choiceEl.querySelector("[data-selection-summary]");
    const labelList = Array.from(choiceEl.querySelectorAll("input:checked"), function (el) { return el.dataset.label; });
    summaryEl.textContent = labelList.length ? labelList.join(", ") : summaryEl.dataset.emptyText;
  }

  formEl.querySelectorAll("[data-selection-choice]").forEach(function (choiceEl) {
    choiceEl.addEventListener("change", function () { updateChoiceSummary(choiceEl); });
  });

  // tabel React (frontend/src/entry_table) ganti urutan / filter kolom tanpa reload halaman ->
  // isian panel ini disamain sama kriteria yg dipake tabel, biar Jalankan ga ngirim nilai lama.
  // query = { key: [nilai, ...] } dari server (udah dirapihin)
  function applyQuery(query) {
    function readList(key) { return query[key] || []; }

    if (quickEl) quickEl.value = readList("q")[0] || "";
    formEl.querySelectorAll("[data-selection-text]").forEach(function (boxEl) {
      const key = boxEl.dataset.selectionText;
      writeValue(key, readList(key), readList(key + EXCLUDE_SUFFIX));
    });
    formEl.querySelectorAll("[data-selection-choice]").forEach(function (choiceEl) {
      choiceEl.querySelectorAll('input[type="checkbox"]').forEach(function (checkboxEl) {
        checkboxEl.checked = readList(checkboxEl.name).includes(checkboxEl.value);
      });
      updateChoiceSummary(choiceEl);
    });
    formEl.querySelectorAll('input[type="date"]').forEach(function (inputEl) {
      inputEl.value = readList(inputEl.name)[0] || "";
    });

    // urutan tabel ikut kebawa pas Jalankan
    let sortEl = formEl.querySelector('input[type="hidden"][name="sort"]');
    const sortValue = readList("sort")[0] || "";
    if (sortValue && !sortEl) {
      sortEl = document.createElement("input");
      sortEl.type = "hidden";
      sortEl.name = "sort";
      formEl.prepend(sortEl);
    }
    if (sortEl) {
      if (sortValue) sortEl.value = sortValue;
      else sortEl.remove();
    }
  }

  document.addEventListener("alr:table-query-changed", function (event) {
    if (event.detail && event.detail.query) applyQuery(event.detail.query);
  });

  // isian kosong dimatiin pas dikirim, jadi ga nongol di URL
  formEl.addEventListener("submit", function () {
    formEl.querySelectorAll("input").forEach(function (inputEl) {
      if (inputEl.type !== "checkbox" && !inputEl.value.trim()) inputEl.disabled = true;
    });
  });

  // halaman dibuka lagi lewat tombol Back: isian dinyalain lagi
  window.addEventListener("pageshow", function () {
    formEl.querySelectorAll("input:disabled").forEach(function (inputEl) { inputEl.disabled = false; });
  });

  // tekan "/" buat langsung ke Cari cepat
  const quickEl = formEl.querySelector("[data-selection-quick]");
  document.addEventListener("keydown", function (event) {
    const activeEl = document.activeElement;
    const isTyping = activeEl && (["INPUT", "TEXTAREA", "SELECT"].includes(activeEl.tagName) || activeEl.isContentEditable);
    if (event.key === "/" && !isTyping && quickEl) {
      event.preventDefault();
      const bodyEl = document.getElementById("selection_body");
      if (bodyEl && !bodyEl.classList.contains("show") && window.bootstrap) window.bootstrap.Collapse.getOrCreateInstance(bodyEl).show();
      quickEl.focus();
    }
  });

  // abis Jalankan / pindah halaman (URL ada #id kartu hasil): fokus ke judul hasil, isinya udah nyebut jumlah data,
  // jadi pengguna keyboard & pembaca layar langsung di hasil, ga mulai dari menu lagi
  const resultCardEl = window.location.hash ? document.getElementById(window.location.hash.slice(1)) : null;
  const resultHeadingEl = resultCardEl ? resultCardEl.querySelector("[data-result-heading], .card-title") : null;
  if (resultHeadingEl) {
    resultHeadingEl.setAttribute("tabindex", "-1");
    // nunggu browser selesai lompat ke #id dulu, baru fokusnya dipindah (kalau kecepetan, fokusnya ilang lagi)
    window.addEventListener("load", function () {
      resultHeadingEl.focus({ preventScroll: true });
    });
  }
})();
