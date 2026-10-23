// form data link: field muncul sesuai kategori + field tambahan buat General
(function () {
  "use strict";

  const LEAVE_ANIMATION_MS = 200;
  const formEl = document.querySelector("[data-entry-form]");
  if (!formEl) return;

  const categorySelect = formEl.querySelector("#category_id");
  const customSectionEl = formEl.querySelector("[data-custom-field-section]");
  const listEl = formEl.querySelector("[data-custom-field-list]");
  const emptyEl = formEl.querySelector("[data-custom-field-empty]");
  const addButton = formEl.querySelector("[data-custom-field-add]");
  const templateEl = document.getElementById("custom_field_template");
  const credentialEl = formEl.querySelector("[data-credential-field]");
  const maxCount = parseInt(customSectionEl.dataset.maxCount, 10);

  function parseList(text) {
    return (text || "").split(",").filter(Boolean);
  }

  // ===== field per kategori =====
  function applyCategoryRule() {
    const optionEl = categorySelect.options[categorySelect.selectedIndex];
    if (!optionEl) return;

    const fieldList = parseList(optionEl.dataset.fieldList);
    const requiredList = parseList(optionEl.dataset.requiredFieldList);

    formEl.querySelectorAll("[data-category-field]").forEach(function (groupEl) {
      const fieldName = groupEl.dataset.categoryField;
      const isVisible = fieldList.includes(fieldName);
      const isRequired = requiredList.includes(fieldName);
      groupEl.hidden = !isVisible;

      // field yg disembunyiin ga ikut dikirim
      const inputEl = groupEl.querySelector("input, textarea, select");
      if (inputEl) {
        inputEl.disabled = !isVisible;
        inputEl.setAttribute("aria-required", String(isVisible && isRequired));
      }
    });

    // username & access note disembunyiin + ga ikut dikirim buat kategori tanpa kredensial (General)
    const hasCredentialField = optionEl.dataset.hasCredentialField === "true";
    credentialEl.hidden = !hasCredentialField;
    credentialEl.querySelectorAll("input, textarea").forEach(function (inputEl) {
      inputEl.disabled = !hasCredentialField;
    });

    // field tambahan cuma buat kategori yg punya "Add field" (General)
    const hasCustomField = optionEl.dataset.hasCustomField === "true";
    customSectionEl.hidden = !hasCustomField;
    listEl.querySelectorAll("input, textarea").forEach(function (inputEl) {
      inputEl.disabled = !hasCustomField;
    });
  }

  // ===== kategori bertingkat =====
  // dropdown asli tetep yg dikirim (name=category_id); di layar diganti 1 dropdown per tingkat.
  // boleh berhenti di tingkat mana aja: yg kesimpen tingkat terakhir yg dipilih
  const LEVEL_LABEL_LIST = ["Category", "Sub-category", "Sub-category 2", "Sub-category 3"];
  const cascadeEl = formEl.querySelector("[data-category-cascade]");

  function buildChildDict() {
    const idSet = new Set(Array.from(categorySelect.options, function (optionEl) { return optionEl.value; }));
    const childDict = {};
    Array.from(categorySelect.options).forEach(function (optionEl) {
      // induk ga ada di daftar (kategori lama yg induknya dinonaktifin) -> ditaruh di tingkat paling atas
      const parentId = idSet.has(optionEl.dataset.parentId) ? optionEl.dataset.parentId : "";
      (childDict[parentId] = childDict[parentId] || []).push(optionEl);
    });
    return childDict;
  }

  function buildSelectedPath(childDict) {
    const parentById = {};
    Object.keys(childDict).forEach(function (parentId) {
      childDict[parentId].forEach(function (optionEl) { parentById[optionEl.value] = parentId; });
    });
    const pathList = [];
    for (let id = categorySelect.value; id; id = parentById[id]) pathList.unshift(id);
    return pathList;
  }

  // bikin ulang dropdown mulai fromLevel ke bawah; yg di atasnya (termasuk yg lagi dipake keyboard) ga disentuh
  function renderCascade(childDict, pathList, fromLevel) {
    cascadeEl.querySelectorAll("[data-level-box]").forEach(function (boxEl) {
      if (Number(boxEl.dataset.levelBox) >= fromLevel) boxEl.remove();
    });
    let parentId = fromLevel ? pathList[fromLevel - 1] : "";
    for (let level = fromLevel; parentId !== undefined && childDict[parentId]; level++) {
      const levelLabel = LEVEL_LABEL_LIST[level] || "Sub-category";
      const boxEl = document.createElement("div");
      boxEl.dataset.levelBox = String(level);
      const labelEl = document.createElement("label");
      labelEl.className = "form-label" + (level === 0 ? " required" : "");
      labelEl.htmlFor = "category_level_" + level;
      labelEl.textContent = levelLabel;
      const levelSelect = document.createElement("select");
      levelSelect.className = categorySelect.className;
      levelSelect.id = "category_level_" + level;
      levelSelect.dataset.level = String(level);
      if (level > 0) levelSelect.append(new Option("— Optional —", ""));
      childDict[parentId].forEach(function (optionEl) {
        levelSelect.append(new Option(optionEl.dataset.name, optionEl.value));
      });
      levelSelect.value = pathList[level] || "";
      boxEl.append(labelEl, levelSelect);
      cascadeEl.append(boxEl);
      if (!levelSelect.value) break;
      parentId = levelSelect.value;
    }
  }

  function initCascade() {
    if (!cascadeEl || !categorySelect.options.length) return;
    const childDict = buildChildDict();
    renderCascade(childDict, buildSelectedPath(childDict), 0);
    categorySelect.hidden = true;
    cascadeEl.hidden = false;
    // label bawaan diganti label per tingkat
    const labelEl = formEl.querySelector('label[for="category_id"]');
    if (labelEl) labelEl.hidden = true;

    cascadeEl.addEventListener("change", function (event) {
      const level = Number(event.target.dataset.level);
      const pathList = buildSelectedPath(childDict).slice(0, level);
      if (event.target.value) pathList.push(event.target.value);
      // pilih "(optional)" = berhenti di tingkat atasnya
      categorySelect.value = pathList[pathList.length - 1];
      renderCascade(childDict, pathList, level + 1);
      categorySelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  // ===== field tambahan =====
  function getRowList() {
    return listEl.querySelectorAll("[data-custom-field]");
  }

  // nomor urut, tombol naik/turun, dan batas maksimal
  function refreshCustomFieldState() {
    const rowList = getRowList();
    rowList.forEach(function (rowEl, index) {
      rowEl.querySelector("[data-custom-field-number]").textContent = "Field " + (index + 1);
      rowEl.querySelector('[data-custom-field-move="up"]').disabled = index === 0;
      rowEl.querySelector('[data-custom-field-move="down"]').disabled = index === rowList.length - 1;
    });
    addButton.disabled = rowList.length >= maxCount;
    addButton.title = addButton.disabled ? "Reached the limit of " + maxCount + " fields" : "";
    if (emptyEl) emptyEl.hidden = rowList.length > 0;
  }

  // klik "Add field" = nambah 1 field
  function addRow() {
    if (getRowList().length >= maxCount) return;

    const fragment = templateEl.content.cloneNode(true);
    const rowEl = fragment.querySelector("[data-custom-field]");
    listEl.append(fragment);

    if (window.AlrRichTextEditor) window.AlrRichTextEditor.init(rowEl);
    rowEl.classList.add("is-entering");
    refreshCustomFieldState();
    rowEl.querySelector('input[name="custom_field_label"]').focus();
  }

  async function removeRow(rowEl) {
    const labelText = rowEl.querySelector('input[name="custom_field_label"]').value.trim();
    const contentText = rowEl.querySelector("[data-rte-content]").textContent.trim();

    // kalau udah ada isinya, tanya dulu
    if ((labelText || contentText) && window.AlrConfirm) {
      const isConfirmed = await window.AlrConfirm.open({
        title: "Delete this field?",
        message: "Anything typed in this field will be lost.",
        okLabel: "Yes, delete"
      });
      if (!isConfirmed) return;
    }

    rowEl.classList.add("is-leaving");
    window.setTimeout(function () {
      rowEl.remove();
      refreshCustomFieldState();
    }, LEAVE_ANIMATION_MS);
  }

  function moveRow(rowEl, direction) {
    if (direction === "up" && rowEl.previousElementSibling) {
      listEl.insertBefore(rowEl, rowEl.previousElementSibling);
    } else if (direction === "down" && rowEl.nextElementSibling) {
      listEl.insertBefore(rowEl.nextElementSibling, rowEl);
    }
    refreshCustomFieldState();
    rowEl.querySelector('[data-custom-field-move="' + direction + '"]').focus();
  }

  // satu listener buat semua tombol di dalam list (termasuk field yg baru ditambah)
  listEl.addEventListener("click", function (event) {
    const buttonEl = event.target.closest("button");
    if (!buttonEl) return;
    const rowEl = buttonEl.closest("[data-custom-field]");
    if (!rowEl) return;

    if (buttonEl.hasAttribute("data-custom-field-remove")) {
      removeRow(rowEl);
    } else if (buttonEl.dataset.customFieldMove) {
      moveRow(rowEl, buttonEl.dataset.customFieldMove);
    }
  });

  addButton.addEventListener("click", addRow);
  categorySelect.addEventListener("change", applyCategoryRule);

  initCascade();
  applyCategoryRule();
  refreshCustomFieldState();
})();