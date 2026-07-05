/** Label designer — JSON layout editor with live server preview. */

(function () {
  const ANCHOR_OFFSETS = {
    "top-left": [0, 0],
    "top-center": [-0.5, 0],
    "top-right": [-1, 0],
    "center-left": [0, -0.5],
    center: [-0.5, -0.5],
    "center-right": [-1, -0.5],
    "bottom-left": [0, -1],
    "bottom-center": [-0.5, -1],
    "bottom-right": [-1, -1],
  };

  const TYPE_LABELS = {
    text: "Static text",
    dynamic_text: "Dynamic text",
    qr: "QR code",
    image: "Image",
    box: "Box",
  };

  let design = null;
  let selectedId = null;
  let previewTimer = null;
  let previewRequest = 0;

  const els = {
    designName: document.getElementById("design-name"),
    designSelect: document.getElementById("design-select"),
    saveStatus: document.getElementById("save-status"),
    labelWidth: document.getElementById("label-width"),
    labelHeight: document.getElementById("label-height"),
    elementList: document.getElementById("element-list"),
    previewImage: document.getElementById("preview-image"),
    previewStatus: document.getElementById("preview-status"),
    overlay: document.getElementById("overlay"),
    canvasWrap: document.getElementById("canvas-wrap"),
    noSelection: document.getElementById("no-selection"),
    propertiesForm: document.getElementById("properties-form"),
    variablesList: document.getElementById("variables-list"),
    previewValuesForm: document.getElementById("preview-values-form"),
    propId: document.getElementById("prop-id"),
    propTypeLabel: document.getElementById("prop-type-label"),
    propX: document.getElementById("prop-x"),
    propY: document.getElementById("prop-y"),
    propWidth: document.getElementById("prop-width"),
    propHeight: document.getElementById("prop-height"),
    propAnchor: document.getElementById("prop-anchor"),
    propsTextStatic: document.getElementById("props-text-static"),
    propsTextDynamic: document.getElementById("props-text-dynamic"),
    propContent: document.getElementById("prop-content"),
    propVariable: document.getElementById("prop-variable"),
    propFont: document.getElementById("prop-font"),
    propLineSpacing: document.getElementById("prop-line-spacing"),
    propAlign: document.getElementById("prop-align"),
    propBold: document.getElementById("prop-bold"),
    propFontDynamic: document.getElementById("prop-font-dynamic"),
    propLineSpacingDynamic: document.getElementById("prop-line-spacing-dynamic"),
    propAlignDynamic: document.getElementById("prop-align-dynamic"),
    propBoldDynamic: document.getElementById("prop-bold-dynamic"),
    propsQr: document.getElementById("props-qr"),
    propQrVariable: document.getElementById("prop-qr-variable"),
    propsImage: document.getElementById("props-image"),
    propImageFile: document.getElementById("prop-image-file"),
    propsBox: document.getElementById("props-box"),
    propBorder: document.getElementById("prop-border"),
    propFill: document.getElementById("prop-fill"),
  };

  function defaultDesign() {
    return {
      name: "Untitled",
      version: 1,
      setup: {
        label_width_mm: 75,
        label_length_mm: 50,
        gap_mm: 2,
        darkness: 8,
        speed: 4,
        copies: 1,
        dpi: 203,
        page_direction: "Portrait",
      },
      variables: [
        { name: "evse_id", label: "EVSE-ID", default: "DE*CIQ*ABC*1", computed: "" },
        { name: "qr_base_url", label: "QR base URL", default: "https://qr.chargeIQ.de/", computed: "" },
        { name: "qr_url", label: "QR URL", default: "", computed: "{qr_base_url}/{evse_id}" },
      ],
      elements: [
        {
          id: "text_evse_label",
          type: "text",
          x_mm: 3,
          y_mm: 3,
          width_mm: 40,
          height_mm: 5,
          anchor: "top-left",
          content: "EVSE-ID:",
          variable: "",
          font_size_pt: 9,
          alignment: "left",
          bold: false,
        },
        {
          id: "text_evse_value",
          type: "dynamic_text",
          x_mm: 3,
          y_mm: 9,
          width_mm: 40,
          height_mm: 6,
          anchor: "top-left",
          variable: "evse_id",
          font_size_pt: 10,
          alignment: "left",
          bold: true,
        },
        {
          id: "qr_main",
          type: "qr",
          x_mm: 55,
          y_mm: 10,
          width_mm: 18,
          height_mm: 18,
          anchor: "top-left",
          variable: "qr_url",
          content: "",
        },
      ],
    };
  }

  function normalizeElement(el) {
    if (el.type === "text-dynamic" || el.type === "text_dynamic") {
      el.type = "dynamic_text";
    }
    if (
      el.type === "text" &&
      (el.variable || (el.content && /^\{[^}]+\}$/.test(el.content.trim())))
    ) {
      el.type = "dynamic_text";
      if (!el.variable && el.content) {
        el.variable = el.content.trim().slice(1, -1);
      }
    }
    if (el.type === "text") {
      delete el.variable;
    }
    if (el.type === "dynamic_text") {
      delete el.content;
    }
    return el;
  }

  function normalizeDesign(data) {
    data.elements = (data.elements || []).map(normalizeElement);
    return data;
  }

  function typeLabel(type) {
    return TYPE_LABELS[type] || type;
  }

  let previewValuesCache = {};

  function sanitizeVarName(raw) {
    return String(raw || "")
      .trim()
      .replace(/[^a-zA-Z0-9_]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/^(\d)/, "_$1");
  }

  function variableUsage(name) {
    if (!name) {
      return [];
    }
    return design.elements.filter(
      (el) =>
        (el.type === "dynamic_text" && el.variable === name) ||
        (el.type === "qr" && el.variable === name),
    );
  }

  function capturePreviewValues() {
    if (!els.previewValuesForm) {
      return;
    }
    els.previewValuesForm.querySelectorAll("input[data-var-name]").forEach((input) => {
      previewValuesCache[input.dataset.varName] = input.value;
    });
  }

  function syncVariablesFromCards() {
    const cards = els.variablesList.querySelectorAll(".variable-card");
    const previous = design.variables.slice();
    const next = [];

    cards.forEach((card, index) => {
      const old = previous[index] || {};
      const name = sanitizeVarName(card.querySelector('[data-field="name"]').value) || old.name || "";
      const label = card.querySelector('[data-field="label"]').value.trim();
      const defaultValue = card.querySelector('[data-field="default"]').value;
      const computed = card.querySelector('[data-field="computed"]').value.trim();

      if (!name) {
        return;
      }

      if (old.name && old.name !== name) {
        design.elements.forEach((el) => {
          if (
            (el.type === "dynamic_text" || el.type === "qr") &&
            el.variable === old.name
          ) {
            el.variable = name;
          }
        });
        if (previewValuesCache[old.name] !== undefined) {
          previewValuesCache[name] = previewValuesCache[old.name];
          delete previewValuesCache[old.name];
        }
      }

      next.push({
        name,
        label,
        default: defaultValue,
        computed,
      });
    });

    design.variables = next;
  }

  function renderVariablesList() {
    els.variablesList.innerHTML = "";
    design.variables.forEach((variable, index) => {
      const card = document.createElement("div");
      card.className = "variable-card" + (variable.computed ? " is-computed" : "");
      card.dataset.index = String(index);

      const header = document.createElement("div");
      header.className = "variable-card-header";
      header.innerHTML = `<strong>${variable.name || "new_variable"}</strong>`;

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn btn-secondary btn-sm btn-icon btn-danger";
      deleteBtn.title = "Delete variable";
      deleteBtn.textContent = "×";
      deleteBtn.addEventListener("click", () => deleteVariable(index));
      header.appendChild(deleteBtn);
      card.appendChild(header);

      const fields = [
        { key: "name", label: "Name", placeholder: "evse_id", mono: true },
        { key: "label", label: "Label", placeholder: "EVSE-ID" },
        { key: "default", label: "Default", placeholder: "Sample value" },
        {
          key: "computed",
          label: "Computed",
          placeholder: "{qr_base_url}/{evse_id}",
        },
      ];

      fields.forEach(({ key, label, placeholder }) => {
        const wrap = document.createElement("div");
        wrap.className = "field";
        const fieldLabel = document.createElement("label");
        fieldLabel.textContent = label;
        const input = document.createElement("input");
        input.type = "text";
        input.dataset.field = key;
        input.placeholder = placeholder || "";
        input.value = variable[key] || "";
        input.addEventListener("input", () => {
          syncVariablesFromCards();
          const name = sanitizeVarName(
            card.querySelector('[data-field="name"]').value,
          );
          card.querySelector(".variable-card-header strong").textContent =
            name || "new_variable";
          card.classList.toggle(
            "is-computed",
            !!card.querySelector('[data-field="computed"]').value.trim(),
          );
          renderPreviewValuesForm();
          if (selectedId) {
            renderProperties();
          }
          schedulePreview();
        });
        wrap.appendChild(fieldLabel);
        wrap.appendChild(input);
        card.appendChild(wrap);
      });

      els.variablesList.appendChild(card);
    });
  }

  function renderPreviewValuesForm() {
    capturePreviewValues();
    els.previewValuesForm.innerHTML = "";

    design.variables.forEach((variable) => {
      if (variable.computed) {
        const note = document.createElement("p");
        note.className = "preview-computed";
        note.innerHTML = `<strong>${variable.label || variable.name}</strong> · computed: <span>${variable.computed}</span>`;
        els.previewValuesForm.appendChild(note);
        return;
      }

      const wrap = document.createElement("div");
      wrap.className = "field";
      const label = document.createElement("label");
      label.textContent = variable.label || variable.name;
      label.htmlFor = `preview-${variable.name}`;
      const input = document.createElement("input");
      input.type = "text";
      input.id = `preview-${variable.name}`;
      input.dataset.varName = variable.name;
      input.value =
        previewValuesCache[variable.name] ??
        variable.default ??
        "";
      input.addEventListener("input", schedulePreview);
      wrap.appendChild(label);
      wrap.appendChild(input);
      els.previewValuesForm.appendChild(wrap);
    });
  }

  function refreshVariableUi() {
    renderVariablesList();
    renderPreviewValuesForm();
    if (selectedId) {
      renderProperties();
    }
    schedulePreview();
  }

  function addVariable() {
    let index = 1;
    let name = "variable_1";
    while (design.variables.some((item) => item.name === name)) {
      index += 1;
      name = `variable_${index}`;
    }
    design.variables.push({
      name,
      label: "",
      default: "",
      computed: "",
    });
    refreshVariableUi();
    els.saveStatus.textContent = `Added variable ${name}.`;
  }

  function deleteVariable(index) {
    const variable = design.variables[index];
    if (!variable) {
      return;
    }
    const usedBy = variableUsage(variable.name);
    if (usedBy.length) {
      els.saveStatus.textContent = `Cannot delete ${variable.name}: used by ${usedBy.length} element(s).`;
      return;
    }
    design.variables.splice(index, 1);
    delete previewValuesCache[variable.name];
    refreshVariableUi();
    els.saveStatus.textContent = `Deleted variable ${variable.name}.`;
  }

  function populateVariableSelect(select, selected) {
    const current = selected || select.value;
    select.innerHTML = '<option value="">Choose variable…</option>';
    (design.variables || []).forEach((variable) => {
      const option = document.createElement("option");
      option.value = variable.name;
      const kind = variable.computed ? "computed" : "input";
      option.textContent = variable.label
        ? `${variable.label} (${variable.name}) · ${kind}`
        : `${variable.name} · ${kind}`;
      select.appendChild(option);
    });
    select.value = current;
    if (current && !select.value) {
      const custom = document.createElement("option");
      custom.value = current;
      custom.textContent = `${current} (custom)`;
      select.appendChild(custom);
      select.value = current;
    }
  }

  function setTypeBadge(type) {
    els.propTypeLabel.textContent = typeLabel(type);
    els.propTypeLabel.className = "element-type-badge";
    if (type) {
      els.propTypeLabel.classList.add(`type-${type}`);
    }
  }

  function uid(prefix) {
    return `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function getElement(id) {
    return design.elements.find((el) => el.id === id);
  }

  function selectedElement() {
    return selectedId ? getElement(selectedId) : null;
  }

  function syncSetupFromInputs() {
    design.setup.label_width_mm = parseFloat(els.labelWidth.value) || 75;
    design.setup.label_length_mm = parseFloat(els.labelHeight.value) || 50;
    design.name = els.designName.value.trim() || "Untitled";
  }

  function syncSetupToInputs() {
    els.labelWidth.value = design.setup.label_width_mm;
    els.labelHeight.value = design.setup.label_length_mm;
    els.designName.value = design.name;
  }

  function elementSummary(el) {
    if (el.type === "text") {
      return el.content || "(empty)";
    }
    if (el.type === "dynamic_text") {
      return el.variable ? `{${el.variable}}` : "(no variable)";
    }
    if (el.type === "qr") {
      return el.variable ? `{${el.variable}}` : el.content || "(empty)";
    }
    if (el.type === "image") {
      return el.image_data ? "Image loaded" : "No image";
    }
    return `${el.width_mm}×${el.height_mm} mm`;
  }

  function renderElementList() {
    els.elementList.innerHTML = "";
    design.elements.forEach((el) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = el.id === selectedId ? "selected" : "";
      btn.innerHTML = `<strong>${typeLabel(el.type)}</strong> <span class="element-meta">${el.id} · ${elementSummary(el)}</span>`;
      btn.addEventListener("click", () => selectElement(el.id));
      li.appendChild(btn);
      els.elementList.appendChild(li);
    });
  }

  function previewVariableValues() {
    const values = {};
    els.previewValuesForm.querySelectorAll("input[data-var-name]").forEach((input) => {
      values[input.dataset.varName] = input.value;
    });
    return values;
  }

  function hideTypeProps() {
    els.propsTextStatic.hidden = true;
    els.propsTextDynamic.hidden = true;
    els.propsQr.hidden = true;
    els.propsImage.hidden = true;
    els.propsBox.hidden = true;
  }

  function renderProperties() {
    const el = selectedElement();
    if (!el) {
      els.noSelection.hidden = false;
      els.propertiesForm.hidden = true;
      return;
    }

    els.noSelection.hidden = true;
    els.propertiesForm.hidden = false;
    hideTypeProps();

    els.propId.value = el.id;
    setTypeBadge(el.type);
    els.propX.value = el.x_mm;
    els.propY.value = el.y_mm;
    els.propWidth.value = el.width_mm;
    els.propHeight.value = el.height_mm;
    els.propAnchor.value = el.anchor || "top-left";

    if (el.type === "text") {
      els.propsTextStatic.hidden = false;
      els.propContent.value = el.content || "";
      els.propFont.value = el.font_size_pt || 10;
      els.propLineSpacing.value = el.line_spacing_mm || "";
      els.propAlign.value = el.alignment || "left";
      els.propBold.checked = !!el.bold;
    } else if (el.type === "dynamic_text") {
      els.propsTextDynamic.hidden = false;
      populateVariableSelect(els.propVariable, el.variable || "");
      els.propFontDynamic.value = el.font_size_pt || 10;
      els.propLineSpacingDynamic.value = el.line_spacing_mm || "";
      els.propAlignDynamic.value = el.alignment || "left";
      els.propBoldDynamic.checked = !!el.bold;
    } else if (el.type === "qr") {
      els.propsQr.hidden = false;
      populateVariableSelect(els.propQrVariable, el.variable || "");
    } else if (el.type === "image") {
      els.propsImage.hidden = false;
    } else if (el.type === "box") {
      els.propsBox.hidden = false;
      els.propBorder.value = el.border_width ?? 1;
      els.propFill.checked = !!el.fill;
    }
  }

  function bboxTopLeft(el) {
    const anchor = el.anchor || "top-left";
    const [ox, oy] = ANCHOR_OFFSETS[anchor] || [0, 0];
    return {
      x: el.x_mm + ox * el.width_mm,
      y: el.y_mm + oy * el.height_mm,
    };
  }

  function renderOverlay() {
    const img = els.previewImage;
    if (!img.complete || !img.naturalWidth) {
      return;
    }

    const labelW = design.setup.label_width_mm;
    const labelH = design.setup.label_length_mm;
    const scaleX = img.clientWidth / labelW;
    const scaleY = img.clientHeight / labelH;

    els.overlay.setAttribute("width", img.clientWidth);
    els.overlay.setAttribute("height", img.clientHeight);
    els.overlay.setAttribute("viewBox", `0 0 ${img.clientWidth} ${img.clientHeight}`);
    els.overlay.style.width = `${img.clientWidth}px`;
    els.overlay.style.height = `${img.clientHeight}px`;

    els.overlay.innerHTML = "";
    design.elements.forEach((el) => {
      const topLeft = bboxTopLeft(el);
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", topLeft.x * scaleX);
      rect.setAttribute("y", topLeft.y * scaleY);
      rect.setAttribute("width", el.width_mm * scaleX);
      rect.setAttribute("height", el.height_mm * scaleY);
      rect.classList.add("overlay-rect");
      if (el.id === selectedId) {
        rect.classList.add("selected");
      }
      rect.dataset.id = el.id;
      rect.addEventListener("click", (event) => {
        event.stopPropagation();
        selectElement(el.id);
      });

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", topLeft.x * scaleX + 4);
      label.setAttribute("y", topLeft.y * scaleY + 12);
      label.classList.add("overlay-label");
      label.textContent = typeLabel(el.type);

      els.overlay.appendChild(rect);
      els.overlay.appendChild(label);
    });
  }

  function selectElement(id) {
    selectedId = id;
    renderElementList();
    renderProperties();
    renderOverlay();
  }

  function readLineSpacing(input) {
    const value = parseFloat(input.value);
    return Number.isFinite(value) && value > 0 ? value : 0;
  }

  function applyPropertiesFromForm() {
    const el = selectedElement();
    if (!el) {
      return;
    }

    const newId = els.propId.value.trim();
    if (newId && newId !== el.id) {
      if (design.elements.some((item) => item.id === newId && item.id !== el.id)) {
        els.saveStatus.textContent = "ID already in use.";
        return;
      }
      el.id = newId;
      selectedId = newId;
    }

    el.x_mm = parseFloat(els.propX.value) || 0;
    el.y_mm = parseFloat(els.propY.value) || 0;
    el.width_mm = Math.max(1, parseFloat(els.propWidth.value) || 1);
    el.height_mm = Math.max(1, parseFloat(els.propHeight.value) || 1);
    el.anchor = els.propAnchor.value;

    if (el.type === "text") {
      el.content = els.propContent.value;
      el.font_size_pt = parseFloat(els.propFont.value) || 10;
      el.line_spacing_mm = readLineSpacing(els.propLineSpacing);
      el.alignment = els.propAlign.value;
      el.bold = els.propBold.checked;
    } else if (el.type === "dynamic_text") {
      el.variable = els.propVariable.value.trim();
      el.font_size_pt = parseFloat(els.propFontDynamic.value) || 10;
      el.line_spacing_mm = readLineSpacing(els.propLineSpacingDynamic);
      el.alignment = els.propAlignDynamic.value;
      el.bold = els.propBoldDynamic.checked;
    } else if (el.type === "qr") {
      el.variable = els.propQrVariable.value.trim();
      delete el.content;
    } else if (el.type === "box") {
      el.border_width = parseFloat(els.propBorder.value) || 1;
      el.fill = els.propFill.checked;
    }

    renderElementList();
    renderOverlay();
    schedulePreview();
  }

  function addElement(type) {
    const base = {
      id: uid(type),
      type,
      x_mm: 5,
      y_mm: 5,
      width_mm: 20,
      height_mm: 8,
      anchor: "top-left",
    };

    if (type === "text") {
      Object.assign(base, {
        type: "text",
        content: "New text",
        font_size_pt: 10,
        line_spacing_mm: 0,
        alignment: "left",
        bold: false,
      });
    } else if (type === "text-dynamic") {
      Object.assign(base, {
        type: "dynamic_text",
        variable: "evse_id",
        font_size_pt: 10,
        line_spacing_mm: 0,
        alignment: "left",
        bold: false,
      });
    } else if (type === "qr") {
      Object.assign(base, {
        type: "qr",
        width_mm: 18,
        height_mm: 18,
        variable: "qr_url",
        content: "",
      });
    } else if (type === "image") {
      Object.assign(base, {
        type: "image",
        width_mm: 20,
        height_mm: 12,
        image_data: "",
      });
    } else if (type === "box") {
      Object.assign(base, {
        type: "box",
        width_mm: 30,
        height_mm: 15,
        border_width: 0.3,
        fill: false,
      });
    }

    design.elements.push(base);
    selectElement(base.id);
    schedulePreview();
  }

  async function updatePreview() {
    syncSetupFromInputs();
    syncVariablesFromCards();
    const requestId = ++previewRequest;
    els.previewStatus.textContent = "Updating preview…";

    try {
      const resp = await fetch("/designer/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          design,
          variables: previewVariableValues(),
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || "Preview failed");
      }
      if (requestId !== previewRequest) {
        return;
      }
      const blob = await resp.blob();
      els.previewImage.src = URL.createObjectURL(blob);
      els.previewStatus.textContent = "Preview";
    } catch (err) {
      els.previewStatus.textContent = err.message || "Preview failed";
    }
  }

  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(updatePreview, 300);
  }

  async function saveDesign() {
    syncSetupFromInputs();
    syncVariablesFromCards();
    const name = els.designName.value.trim();
    if (!name) {
      els.saveStatus.textContent = "Enter a design name before saving.";
      return;
    }

    els.saveStatus.textContent = "Saving…";
    try {
      const resp = await fetch(`/designer/api/designs/${encodeURIComponent(name)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(design),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Save failed");
      }

      if (!Array.from(els.designSelect.options).some((opt) => opt.value === name)) {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        els.designSelect.appendChild(option);
      }
      els.designSelect.value = name;
      els.saveStatus.textContent = "Saved.";
    } catch (err) {
      els.saveStatus.textContent = err.message || "Save failed";
    }
  }

  async function loadDesign(name) {
    if (!name) {
      return;
    }
    els.saveStatus.textContent = "Loading…";
    try {
      const resp = await fetch(`/designer/api/designs/${encodeURIComponent(name)}`);
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Load failed");
      }
      design = normalizeDesign(data);
      previewValuesCache = {};
      selectedId = design.elements[0]?.id || null;
      syncSetupToInputs();
      renderElementList();
      renderVariablesList();
      renderPreviewValuesForm();
      renderProperties();
      schedulePreview();
      els.saveStatus.textContent = `Loaded ${name}.`;
    } catch (err) {
      els.saveStatus.textContent = err.message || "Load failed";
    }
  }

  function bindEvents() {
    document.getElementById("btn-new").addEventListener("click", () => {
      design = defaultDesign();
      previewValuesCache = {};
      selectedId = design.elements[0]?.id || null;
      els.designSelect.value = "";
      syncSetupToInputs();
      renderElementList();
      renderVariablesList();
      renderPreviewValuesForm();
      renderProperties();
      schedulePreview();
      els.saveStatus.textContent = "New design.";
    });

    document.getElementById("btn-save").addEventListener("click", saveDesign);
    els.designSelect.addEventListener("change", () => {
      if (els.designSelect.value) {
        loadDesign(els.designSelect.value);
      }
    });
    document.getElementById("btn-add-variable").addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      addVariable();
    });
    document.getElementById("btn-delete").addEventListener("click", () => {
      if (!selectedId) {
        return;
      }
      design.elements = design.elements.filter((el) => el.id !== selectedId);
      selectedId = design.elements[0]?.id || null;
      renderElementList();
      renderProperties();
      schedulePreview();
    });

    document.querySelectorAll("[data-add]").forEach((btn) => {
      btn.addEventListener("click", () => addElement(btn.dataset.add));
    });

    [
      els.labelWidth,
      els.labelHeight,
      els.designName,
      els.propId,
      els.propX,
      els.propY,
      els.propWidth,
      els.propHeight,
      els.propAnchor,
      els.propContent,
      els.propFont,
      els.propLineSpacing,
      els.propAlign,
      els.propBold,
      els.propVariable,
      els.propFontDynamic,
      els.propLineSpacingDynamic,
      els.propAlignDynamic,
      els.propBoldDynamic,
      els.propQrVariable,
      els.propBorder,
      els.propFill,
    ].forEach((input) => {
      input.addEventListener("input", applyPropertiesFromForm);
      input.addEventListener("change", applyPropertiesFromForm);
    });

    els.propImageFile.addEventListener("change", () => {
      const el = selectedElement();
      const file = els.propImageFile.files?.[0];
      if (!el || el.type !== "image" || !file) {
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        el.image_data = reader.result;
        renderElementList();
        schedulePreview();
      };
      reader.readAsDataURL(file);
    });

    els.previewImage.addEventListener("load", renderOverlay);
    window.addEventListener("resize", renderOverlay);
  }

  function init() {
    design = defaultDesign();
    previewValuesCache = {};
    selectedId = design.elements[0]?.id || null;
    syncSetupToInputs();
    renderElementList();
    renderVariablesList();
    renderPreviewValuesForm();
    renderProperties();
    bindEvents();
    schedulePreview();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
