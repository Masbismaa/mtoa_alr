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
  const maxCount = parseInt(customSectionEl.dataset.maxCount, 10) || 20;

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
      const markEl = groupEl.querySelector("[data-required-mark]");
      if (markEl) markEl.hidden = !isRequired;
    });

    // field tambahan cuma buat kategori yg punya "Add field" (General)
    const hasCustomField = optionEl.dataset.hasCustomField === "true";
    customSectionEl.hidden = !hasCustomField;
    listEl.querySelectorAll("input, textarea").forEach(function (inputEl) {
      inputEl.disabled = !hasCustomField;
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
    addButton.title = addButton.disabled ? "Sudah mencapai batas " + maxCount + " field" : "";
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
        title: "Hapus field ini?",
        message: "Isi field yang sudah diketik bakal hilang.",
        okLabel: "Ya, hapus"
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

  applyCategoryRule();
  refreshCustomFieldState();
})();