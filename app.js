// -------------------------
// Estado global
// -------------------------
let sessionMeta = { empresa: "", fecha: "", responsable: "" };
let items = []; // checklist items
let weightingModel = null; // Modelo salarial puesto+nivel (0–5)
let employees = []; // ✅ empleados importados
let currentStep = 1;
let currentFilter = "ALL";

// Plantilla inicial (puedes ampliar)
const TEMPLATE = [
  { req: "Definición y comunicación de bandas salariales por puesto", evidence: "", status: "PENDING", notes: "" },
  { req: "Criterios objetivos de progresión y promoción documentados", evidence: "", status: "PENDING", notes: "" },
  { req: "Registro retributivo actualizado (por sexo/categoría)", evidence: "", status: "PENDING", notes: "" },
  { req: "Metodología de valoración de puestos (job evaluation) consistente", evidence: "", status: "PENDING", notes: "" },
  { req: "Proceso para responder solicitudes de información salarial (candidatos/empleados)", evidence: "", status: "PENDING", notes: "" },
  { req: "Medidas correctoras ante brechas significativas", evidence: "", status: "PENDING", notes: "" },
  { req: "Gobernanza: roles y responsables (RRHH, Legal, Compliance)", evidence: "", status: "PENDING", notes: "" },
  { req: "Control de accesos y trazabilidad de datos salariales", evidence: "", status: "PENDING", notes: "" },
];

// -------------------------
// Helpers
// -------------------------
const $ = (id) => document.getElementById(id);

function saveLocal() {
  localStorage.setItem("audit_session_meta", JSON.stringify(sessionMeta));
  localStorage.setItem("audit_items", JSON.stringify(items));
  localStorage.setItem("audit_weighting_model", JSON.stringify(weightingModel));
  localStorage.setItem("audit_employees", JSON.stringify(employees));
}

function loadLocal() {
  try {
    const sm = localStorage.getItem("audit_session_meta");
    const it = localStorage.getItem("audit_items");
    const wm = localStorage.getItem("audit_weighting_model");
    const em = localStorage.getItem("audit_employees");

    if (sm) sessionMeta = JSON.parse(sm);
    if (it) items = JSON.parse(it);
    if (wm) weightingModel = JSON.parse(wm);
    if (em) employees = JSON.parse(em);
  } catch {}

  if (!items || items.length === 0) items = TEMPLATE.map((x) => ({ ...x }));
  if (!employees) employees = [];
}

function setHeader() {
  $("hdrEmpresa").textContent = sessionMeta.empresa || "—";
  $("hdrFecha").textContent = sessionMeta.fecha || "—";
  $("hdrResp").textContent = sessionMeta.responsable || "—";
  $("inpEmpresa").value = sessionMeta.empresa || "";
  $("inpFecha").value = sessionMeta.fecha || defaultDate();
  $("inpResp").value = sessionMeta.responsable || "";
}

function defaultDate() {
  return new Date().toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" });
}

function money(n) {
  return `${Number(n || 0).toLocaleString("es-ES")} €`;
}

// -------------------------
// Navegación por pasos
// -------------------------
function goStep(n) {
  currentStep = n;

  document.querySelectorAll(".view").forEach((v) => (v.style.display = "none"));
  const view = $(`view${n}`);
  if (view) view.style.display = "block";

  document.querySelectorAll(".step").forEach((s) => s.classList.remove("active"));
  const step = document.querySelector(`.step[data-step="${n}"]`);
  if (step) step.classList.add("active");

  if (n === 2) renderTable();
  if (n === 5) renderModelLists();
  if (n === 6) {
    refreshEmployeeFilters();
    renderEmployeesTable();
  }

  updateSummary();
}

// -------------------------
// Tabla checklist
// -------------------------
function statusTag(status) {
  if (status === "OK") return `<span class="tag ok">OK</span>`;
  if (status === "Mejora") return `<span class="tag warn">Mejora</span>`;
  if (status === "Riesgo") return `<span class="tag risk">Riesgo</span>`;
  return `<span class="tag" style="background:#e5e7eb;color:#111827">Pendiente</span>`;
}

function filterItems(list) {
  if (currentFilter === "ALL") return list;
  if (currentFilter === "PENDING") return list.filter((x) => x.status === "PENDING");
  return list.filter((x) => x.status === currentFilter);
}

function renderTable() {
  const tbody = $("tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const view = filterItems(items);

  view.forEach((it) => {
    const realIdx = items.indexOf(it);
    const tr = document.createElement("tr");

    const td1 = document.createElement("td");
    const req = document.createElement("textarea");
    req.value = it.req;
    req.oninput = () => {
      it.req = req.value;
      saveLocal();
    };
    td1.appendChild(req);

    const td2 = document.createElement("td");
    const ev = document.createElement("textarea");
    ev.value = it.evidence;
    ev.placeholder = "Ej: Política retributiva v2 (SharePoint/HR), Registro 2025, Procedimiento…";
    ev.oninput = () => {
      it.evidence = ev.value;
      saveLocal();
    };
    td2.appendChild(ev);

    const td3 = document.createElement("td");
    const sel = document.createElement("select");
    ["PENDING", "OK", "Mejora", "Riesgo"].forEach((v) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = v === "PENDING" ? "Pendiente" : v;
      if (it.status === v) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = () => {
      it.status = sel.value;
      saveLocal();
      updateSummary();
      renderTable();
    };
    td3.appendChild(sel);
    td3.insertAdjacentHTML("beforeend", `<div style="margin-top:8px">${statusTag(it.status)}</div>`);

    const td4 = document.createElement("td");
    const notes = document.createElement("textarea");
    notes.value = it.notes;
    notes.placeholder = "Qué falta / qué acción propones / responsable / plazo…";
    notes.oninput = () => {
      it.notes = notes.value;
      saveLocal();
    };
    td4.appendChild(notes);

    const td5 = document.createElement("td");
    const box = document.createElement("div");
    box.className = "actions";

    const btnSuggest = document.createElement("button");
    btnSuggest.className = "secondary";
    btnSuggest.textContent = "✨ Sugerir IA";
    btnSuggest.onclick = async () => {
      btnSuggest.disabled = true;
      btnSuggest.textContent = "Pensando…";

      const prompt =
        `Actúa como auditor experto en Pay Transparency (UE) y auditoría retributiva. ` +
        `Dado el requisito: "${it.req}". ` +
        `Evidencia actual: "${it.evidence || "(vacío)"}". ` +
        `Devuelve: (1) estado recomendado (OK/Mejora/Riesgo), (2) 2-4 frases de justificación, ` +
        `(3) acción concreta y evidencia sugerida. Responde claro y breve.`;

      const r = await callAgent(prompt);
      it.notes = r;

      const low = (r || "").toLowerCase();
      if (low.includes("riesgo")) it.status = "Riesgo";
      else if (low.includes("mejora")) it.status = "Mejora";
      else if (low.includes("ok")) it.status = "OK";

      saveLocal();
      btnSuggest.disabled = false;
      btnSuggest.textContent = "✨ Sugerir IA";
      updateSummary();
      renderTable();
    };

    const btnDel = document.createElement("button");
    btnDel.className = "ghost";
    btnDel.textContent = "Eliminar";
    btnDel.onclick = () => {
      items.splice(realIdx, 1);
      saveLocal();
      updateSummary();
      renderTable();
    };

    box.appendChild(btnSuggest);
    box.appendChild(btnDel);
    td5.appendChild(box);

    tr.appendChild(td1);
    tr.appendChild(td2);
    tr.appendChild(td3);
    tr.appendChild(td4);
    tr.appendChild(td5);

    tbody.appendChild(tr);
  });
}

// -------------------------
// Resumen / KPIs
// -------------------------
function updateSummary() {
  const total = items.length || 1;
  const ok = items.filter((i) => i.status === "OK").length;
  const warn = items.filter((i) => i.status === "Mejora").length;
  const risk = items.filter((i) => i.status === "Riesgo").length;
  const pending = items.filter((i) => i.status === "PENDING").length;

  const done = Math.round(((total - pending) / total) * 100);

  if ($("kpiDone")) $("kpiDone").textContent = `${done}%`;
  if ($("kpiPending")) $("kpiPending").textContent = `${pending}`;
  if ($("kpiRisk")) $("kpiRisk").textContent = `${risk}`;
  if ($("kpiWarn")) $("kpiWarn").textContent = `${warn}`;

  if ($("sumRisk")) {
    $("sumRisk").textContent = `${risk}`;
    $("sumWarn").textContent = `${warn}`;
    $("sumOK").textContent = `${ok}`;
    $("progressBar").style.width = `${done}%`;
    $("progressText").textContent = `${done}% completado (${total - pending}/${total})`;

    const pend = items
      .filter((i) => i.status === "PENDING")
      .slice(0, 5)
      .map((i) => `• ${i.req}`)
      .join("\n");
    $("pendingList").textContent = pend || "—";
  }
}

// -------------------------
// Import/Export (JSON)
// -------------------------
function exportJSON() {
  const payload = { sessionMeta, items, weightingModel, employees };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "auditretrib-export.json";
  a.click();
  URL.revokeObjectURL(a.href);
}

function importJSON() {
  const inp = document.createElement("input");
  inp.type = "file";
  inp.accept = "application/json";
  inp.onchange = async () => {
    const file = inp.files[0];
    if (!file) return;
    const txt = await file.text();
    const data = JSON.parse(txt);

    if (data.sessionMeta) sessionMeta = data.sessionMeta;
    if (data.items) items = data.items;
    if (data.weightingModel !== undefined) weightingModel = data.weightingModel;
    if (data.employees !== undefined) employees = data.employees;

    saveLocal();
    setHeader();
    updateSummary();
    renderTable();
    refreshEmployeeFilters();
    renderEmployeesTable();
  };
  inp.click();
}

// -------------------------
// IA calls (tu backend)
// -------------------------
async function callAgent(prompt) {
  try {
    const res = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    return data.text || "Sin respuesta.";
  } catch (e) {
    console.error(e);
    return "⚠️ No se pudo conectar con el asistente (/api/agent).";
  }
}

async function generateReportIA() {
  const payload = JSON.stringify({ sessionMeta, items, weightingModel, employees }, null, 2);
  const prompt =
    `Eres auditor experto en Pay Transparency (UE) y auditoría retributiva. ` +
    `Analiza la auditoría (JSON) y devuelve un informe en español con:\n` +
    `1) Resumen ejecutivo\n2) Hallazgos Riesgo (con evidencia faltante)\n3) Hallazgos Mejora\n4) Acciones prioritarias (top 10)\n` +
    `5) Evidencias/documentos a recopilar\n\n` +
    `Datos:\n${payload}`;

    $("modalIA").classList.add("on");
    $("iaText").textContent = "Generando informe…";
    const txt = await callAgent(prompt);
    $("iaText").textContent = txt;
}

async function generatePlanIA() {
  const payload = JSON.stringify({ sessionMeta, items, weightingModel, employees }, null, 2);
  const prompt =
    `Eres consultor experto en implementación. ` +
    `A partir de los items Riesgo/Mejora del JSON, crea un plan de acción en tabla (texto) con: ` +
    `Acción | Prioridad | Responsable sugerido | Evidencia a producir | Plazo.\n\nDatos:\n${payload}`;

  $("planText").textContent = "Generando plan…";
  const txt = await callAgent(prompt);
  $("planText").textContent = txt;
}

function copyPlan() {
  const txt = $("planText").textContent || "";
  navigator.clipboard.writeText(txt);
  alert("Plan copiado.");
}

// -------------------------
// Descarga de archivos desde backend (PDF / DOCX)
// -------------------------
async function downloadFromEndpoint(url, filename, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function exportPDF() {
  const empresa = (sessionMeta?.empresa || "Empresa").replace(/[\\/:*?"<>|]/g, "_");
  await downloadFromEndpoint("/api/report/pdf", `Informe_Auditoria_${empresa}.pdf`, {
    sessionMeta,
    items,
    weightingModel,
    employees,
  });
}

async function exportWord() {
  const empresa = (sessionMeta?.empresa || "Empresa").replace(/[\\/:*?"<>|]/g, "_");
  await downloadFromEndpoint("/api/report/docx", `Informe_Auditoria_${empresa}.docx`, {
    sessionMeta,
    items,
    weightingModel,
    employees,
  });
}

// -------------------------
// Excel import/export (checklist)
// -------------------------
function exportExcel() {
  const rows = items.map((it, idx) => ({
    "Nº": idx + 1,
    "Requisito": it.req || "",
    "Evidencia/Fuente": it.evidence || "",
    "Estado": it.status || "PENDING",
    "Notas/Acción": it.notes || "",
  }));

  if (typeof XLSX === "undefined") {
    alert("Falta la librería XLSX en index.html");
    return;
  }

  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Auditoria");

  const empresa = (sessionMeta?.empresa || "Empresa").replace(/[\\/:*?"<>|]/g, "_");
  XLSX.writeFile(wb, `Auditoria_${empresa}.xlsx`);
}

function importExcel() {
  if (typeof XLSX === "undefined") {
    alert("Falta la librería XLSX en index.html");
    return;
  }

  const inp = document.createElement("input");
  inp.type = "file";
  inp.accept = ".xlsx,.xls";
  inp.onchange = async () => {
    const file = inp.files[0];
    if (!file) return;

    const data = await file.arrayBuffer();
    const wb = XLSX.read(data, { type: "array" });
    const ws = wb.Sheets[wb.SheetNames[0]];
    const json = XLSX.utils.sheet_to_json(ws);

    items = json.map((r) => ({
      req: r["Requisito"] ?? r["requisito"] ?? "",
      evidence: r["Evidencia/Fuente"] ?? r["Evidencia"] ?? "",
      status: normalizeStatus(r["Estado"]),
      notes: r["Notas/Acción"] ?? r["Notas"] ?? "",
    }));

    saveLocal();
    updateSummary();
    renderTable();
    alert("Excel importado.");
  };
  inp.click();
}

function normalizeStatus(v) {
  const s = String(v ?? "PENDING").trim().toLowerCase();
  if (s === "ok") return "OK";
  if (s === "mejora") return "Mejora";
  if (s === "riesgo") return "Riesgo";
  if (s === "pendiente" || s === "pending" || s === "") return "PENDING";
  return "PENDING";
}

// -------------------------
// Empleados (Paso 6)
// -------------------------
function importEmployeesExcel() {
  if (typeof XLSX === "undefined") {
    alert("Falta la librería XLSX en index.html");
    return;
  }

  const inp = document.createElement("input");
  inp.type = "file";
  inp.accept = ".xlsx,.xls,.csv";
  inp.onchange = async () => {
    const file = inp.files[0];
    if (!file) return;

    const data = await file.arrayBuffer();
    const wb = XLSX.read(data, { type: "array" });
    const ws = wb.Sheets[wb.SheetNames[0]];
    const json = XLSX.utils.sheet_to_json(ws);

    const pick = (row, keys) => {
      for (const k of keys) {
        if (row[k] !== undefined) return row[k];
      }
      return "";
    };

    employees = json.map((r) => ({
      nombre: pick(r, ["nombre", "Nombre"]),
      apellido: pick(r, ["apellido", "Apellido"]),
      sexo: pick(r, ["sexo", "Sexo"]),
      departamento: pick(r, ["departamento", "Departamento"]),
      puesto: pick(r, ["puesto", "Puesto"]),
      nivel: pick(r, ["nivel", "Nivel"]),
      ubicacion: pick(r, ["ubicacion", "Ubicación", "Ubicacion"]),
      tipo_contrato: pick(r, ["tipo_contrato", "Tipo contrato", "Tipo_contrato"]),
      fecha_alta_empresa: pick(r, ["fecha_alta_empresa", "Fecha alta empresa", "Fecha_alta_empresa"]),
      base_salarial: Number(
  pick(r, [
    "base_salarial",
    "Base salarial",
    "Base_salarial",
    "BASE SALARIAL",
    "Salario base",
    "salario_base"
  ])
) || 0,

bonus: Number(
  pick(r, [
    "bonus",
    "Bonus",
    "BONUS",
    "Variable",
    "bonus_variable"
  ])
) || 0,    }));

    saveLocal();
    refreshEmployeeFilters();
    renderEmployeesTable();
    alert(`Empleados importados: ${employees.length}`);
  };
  inp.click();
}

function exportEmployeesExcel() {
  if (typeof XLSX === "undefined") {
    alert("Falta la librería XLSX en index.html");
    return;
  }
  if (!employees || employees.length === 0) {
    alert("No hay empleados cargados.");
    return;
  }

  const rows = employees.map((e, idx) => ({
    "Nº": idx + 1,
    nombre: e.nombre,
    apellido: e.apellido,
    sexo: e.sexo,
    departamento: e.departamento,
    puesto: e.puesto,
    nivel: e.nivel,
    ubicacion: e.ubicacion,
    tipo_contrato: e.tipo_contrato,
    fecha_alta_empresa: e.fecha_alta_empresa,
    base_salarial: e.base_salarial,
    bonus: e.bonus,
  }));

  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Empleados");

  const empresa = (sessionMeta?.empresa || "Empresa").replace(/[\\/:*?"<>|]/g, "_");
  XLSX.writeFile(wb, `Empleados_${empresa}.xlsx`);
}

function getFilteredEmployees() {
  const role = $("empFilterRole")?.value || "ALL";
  const level = $("empFilterLevel")?.value || "ALL";
  const sexo = $("empFilterSexo")?.value || "ALL";

  return employees.filter((e) => {
    const okRole = role === "ALL" || e.puesto === role;
    const okLevel = level === "ALL" || e.nivel === level;
    const okSexo = sexo === "ALL" || e.sexo === sexo;
    return okRole && okLevel && okSexo;
  });
}

function refreshEmployeeFilters() {
  if (!$("empFilterRole") || !$("empFilterLevel")) return;

  const currentRole = $("empFilterRole").value || "ALL";
  const currentLevel = $("empFilterLevel").value || "ALL";

  const roles = [...new Set(employees.map((e) => e.puesto).filter(Boolean))].sort();
  const levels = [...new Set(employees.map((e) => e.nivel).filter(Boolean))].sort();

  $("empFilterRole").innerHTML = `<option value="ALL">Todos</option>`;
  roles.forEach((r) => {
    const o = document.createElement("option");
    o.value = r;
    o.textContent = r;
    $("empFilterRole").appendChild(o);
  });

  $("empFilterLevel").innerHTML = `<option value="ALL">Todos</option>`;
  levels.forEach((l) => {
    const o = document.createElement("option");
    o.value = l;
    o.textContent = l;
    $("empFilterLevel").appendChild(o);
  });

  $("empFilterRole").value = roles.includes(currentRole) ? currentRole : "ALL";
  $("empFilterLevel").value = levels.includes(currentLevel) ? currentLevel : "ALL";
}

function renderEmployeesTable() {
  if (!$("employeesTbody")) return;

  const rows = getFilteredEmployees();
  const tbody = $("employeesTbody");
  tbody.innerHTML = "";

  rows.forEach((e) => {
    const tr = document.createElement("tr");
    const total = (Number(e.base_salarial) || 0) + (Number(e.bonus) || 0);

    tr.innerHTML = `
      <td>${e.nombre || ""}</td>
      <td>${e.apellido || ""}</td>
      <td>${e.sexo || ""}</td>
      <td>${e.departamento || ""}</td>
      <td>${e.puesto || ""}</td>
      <td>${e.nivel || ""}</td>
      <td>${e.ubicacion || ""}</td>
      <td>${e.tipo_contrato || ""}</td>
      <td>${e.fecha_alta_empresa || ""}</td>
      <td>${money(e.base_salarial)}</td>
      <td>${money(e.bonus)}</td>
      <td>${money(total)}</td>
    `;
    tbody.appendChild(tr);
  });

  const count = rows.length;
  const avgBase = count ? rows.reduce((a, e) => a + (Number(e.base_salarial) || 0), 0) / count : 0;
  const avgBonus = count ? rows.reduce((a, e) => a + (Number(e.bonus) || 0), 0) / count : 0;

  if ($("empCount")) $("empCount").textContent = String(count);
  if ($("empAvgBase")) $("empAvgBase").textContent = money(Math.round(avgBase));
  if ($("empAvgBonus")) $("empAvgBonus").textContent = money(Math.round(avgBonus));
}

// -------------------------
// Modelo salarial (puesto + nivel)
// -------------------------
function ensureWeightingModel() {
  if (!weightingModel) {
    weightingModel = {
      criteria: [],
      roles: [],
      notes: "",
    };
  }
}

function slugId(s) {
  return String(s || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_áéíóúñü]/gi, "");
}

function renderModelLists() {
  ensureWeightingModel();

  if (!$("critList") || !$("roleList") || !$("selRole") || !$("selLevel") || !$("weightTbody")) return;

  $("critList").textContent = weightingModel.criteria.length
    ? weightingModel.criteria.map((c) => `• ${c.name}${c.description ? " — " + c.description : ""}`).join("\n")
    : "—";

  $("roleList").textContent = weightingModel.roles.length
    ? weightingModel.roles.map((r) => `• ${r.roleName}: ${r.levels.join(", ")}`).join("\n")
    : "—";

  const selRole = $("selRole");
  selRole.innerHTML = "";
  weightingModel.roles.forEach((r) => {
    const o = document.createElement("option");
    o.value = r.roleName;
    o.textContent = r.roleName;
    selRole.appendChild(o);
  });

  if (weightingModel.roles.length === 0 || weightingModel.criteria.length === 0) {
    $("selLevel").innerHTML = "";
    $("weightTbody").innerHTML = `<tr><td colspan="3" class="small">Define primero criterios y puestos/niveles.</td></tr>`;
    if ($("scoreOut")) $("scoreOut").value = "0";
    return;
  }

  if (!selRole.value) selRole.value = weightingModel.roles[0].roleName;
  updateLevelsDropdown();
  renderWeightsTable();
}

function getSelectedRoleObj() {
  const roleName = $("selRole")?.value;
  return weightingModel.roles.find((r) => r.roleName === roleName) || null;
}

function updateLevelsDropdown() {
  const role = getSelectedRoleObj();
  const selLevel = $("selLevel");
  selLevel.innerHTML = "";
  if (!role) return;

  role.levels.forEach((lv) => {
    const o = document.createElement("option");
    o.value = lv;
    o.textContent = lv;
    selLevel.appendChild(o);
  });

  if (!selLevel.value) selLevel.value = role.levels[0];
}

function getWeightsForSelection() {
  const role = getSelectedRoleObj();
  const level = $("selLevel")?.value;
  if (!role) return {};

  role.weightsByLevel = role.weightsByLevel || {};
  role.weightsByLevel[level] = role.weightsByLevel[level] || {};
  return role.weightsByLevel[level];
}

function renderWeightsTable() {
  const tbody = $("weightTbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const weights = getWeightsForSelection();
  let score = 0;

  weightingModel.criteria.forEach((c) => {
    const tr = document.createElement("tr");

    const td1 = document.createElement("td");
    td1.innerHTML = `<b>${c.name}</b><div class="small">${c.description || ""}</div>`;

    const td2 = document.createElement("td");
    const sel = document.createElement("select");
    [0, 1, 2, 3, 4, 5].forEach((n) => {
      const o = document.createElement("option");
      o.value = String(n);
      o.textContent = String(n);
      sel.appendChild(o);
    });

    const current = Number(weights[c.id] ?? 0);
    sel.value = String(current);
    score += current;

    sel.onchange = () => {
      weights[c.id] = Number(sel.value);
      saveLocal();
      renderWeightsTable();
    };

    td2.appendChild(sel);

    const td3 = document.createElement("td");
    td3.className = "small";
    td3.textContent = "0 = no relevante · 3 = relevante · 5 = crítico/determinante";

    tr.appendChild(td1);
    tr.appendChild(td2);
    tr.appendChild(td3);
    tbody.appendChild(tr);
  });

  if ($("scoreOut")) $("scoreOut").value = String(score);
}

function addCriterion() {
  ensureWeightingModel();
  const name = $("critName").value.trim();
  const desc = $("critDesc").value.trim();
  if (!name) return alert("Escribe el nombre del criterio.");

  const id = slugId(name);
  if (weightingModel.criteria.some((c) => c.id === id)) return alert("Ya existe un criterio con ese nombre.");

  weightingModel.criteria.push({ id, name, description: desc });
  $("critName").value = "";
  $("critDesc").value = "";
  saveLocal();
  renderModelLists();
}

function addRoleWithLevels() {
  ensureWeightingModel();
  const roleName = $("roleName").value.trim();
  const levelsRaw = $("roleLevels").value.trim();
  if (!roleName) return alert("Escribe el puesto.");
  if (!levelsRaw) return alert("Escribe niveles separados por coma (ej: Junior, Senior).");

  const levels = levelsRaw.split(",").map((x) => x.trim()).filter(Boolean);
  if (levels.length === 0) return alert("No se han detectado niveles.");

  if (weightingModel.roles.some((r) => r.roleName.toLowerCase() === roleName.toLowerCase())) {
    return alert("Ya existe ese puesto.");
  }

  weightingModel.roles.push({ roleName, levels, weightsByLevel: {} });
  $("roleName").value = "";
  $("roleLevels").value = "";
  saveLocal();
  renderModelLists();
}

function saveWeights() {
  ensureWeightingModel();
  saveLocal();
  alert("Ponderaciones guardadas.");
}

function resetCriteria() {
  ensureWeightingModel();
  if (!confirm("¿Borrar todos los criterios?")) return;
  weightingModel.criteria = [];
  weightingModel.roles.forEach((r) => (r.weightsByLevel = {}));
  saveLocal();
  renderModelLists();
}

function resetRoles() {
  ensureWeightingModel();
  if (!confirm("¿Borrar todos los puestos y niveles?")) return;
  weightingModel.roles = [];
  saveLocal();
  renderModelLists();
}

function loadExampleModel() {
  ensureWeightingModel();
  weightingModel.criteria = [
    { id: "responsabilidad", name: "Responsabilidad", description: "Nivel de toma de decisiones y accountability" },
    { id: "complejidad", name: "Complejidad", description: "Dificultad técnica / ambigüedad / variedad de tareas" },
    { id: "impacto", name: "Impacto", description: "Efecto en resultados, clientes, riesgos" },
    { id: "personas", name: "Gestión de personas", description: "Liderazgo formal/informal, tamaño de equipo" },
    { id: "mercado", name: "Escasez/mercado", description: "Dificultad de encontrar perfil equivalente" },
  ];
  weightingModel.roles = [
    {
      roleName: "Analista",
      levels: ["Junior", "Senior"],
      weightsByLevel: {
        Junior: { responsabilidad: 2, complejidad: 2, impacto: 2, personas: 0, mercado: 2 },
        Senior: { responsabilidad: 4, complejidad: 4, impacto: 4, personas: 1, mercado: 3 },
      },
    },
    {
      roleName: "Manager",
      levels: ["I", "II", "III"],
      weightsByLevel: {
        I: { responsabilidad: 4, complejidad: 3, impacto: 3, personas: 3, mercado: 2 },
        II: { responsabilidad: 5, complejidad: 4, impacto: 4, personas: 4, mercado: 2 },
        III: { responsabilidad: 5, complejidad: 5, impacto: 5, personas: 5, mercado: 3 },
      },
    },
  ];
  saveLocal();
  renderModelLists();
}

// -------------------------
// Init
// -------------------------
document.addEventListener("DOMContentLoaded", () => {
  loadLocal();
  setHeader();
  updateSummary();

  document.querySelectorAll(".step").forEach((s) => {
    s.addEventListener("click", () => goStep(parseInt(s.dataset.step, 10)));
  });

  $("inpFecha").value = $("inpFecha").value || defaultDate();
  $("btnSaveSession").addEventListener("click", () => {
    sessionMeta.empresa = $("inpEmpresa").value.trim();
    sessionMeta.fecha = $("inpFecha").value.trim();
    sessionMeta.responsable = $("inpResp").value.trim();
    saveLocal();
    setHeader();
    goStep(2);
  });
  $("btnGoAudit").addEventListener("click", () => goStep(2));

  document.querySelectorAll("[data-filter]").forEach((b) => {
    b.addEventListener("click", () => {
      currentFilter = b.dataset.filter;
      renderTable();
    });
  });

  $("btnAddItem").addEventListener("click", () => {
    items.unshift({ req: "", evidence: "", status: "PENDING", notes: "" });
    saveLocal();
    renderTable();
    updateSummary();
  });

  $("btnExport").addEventListener("click", exportJSON);
  $("btnImport").addEventListener("click", importJSON);

  if ($("btnXlsxExport")) $("btnXlsxExport").addEventListener("click", exportExcel);
  if ($("btnXlsxImport")) $("btnXlsxImport").addEventListener("click", importExcel);

  if ($("btnPDF")) $("btnPDF").addEventListener("click", exportPDF);
  if ($("btnWord")) $("btnWord").addEventListener("click", exportWord);

  $("btnIA").addEventListener("click", generateReportIA);
  $("btnCloseIA").addEventListener("click", () => $("modalIA").classList.remove("on"));
  $("btnPlanIA").addEventListener("click", generatePlanIA);
  $("btnCopyPlan").addEventListener("click", copyPlan);

  if ($("btnAddCrit")) {
    $("btnAddCrit").addEventListener("click", addCriterion);
    $("btnResetCrit").addEventListener("click", resetCriteria);

    $("btnAddRole").addEventListener("click", addRoleWithLevels);
    $("btnResetRoles").addEventListener("click", resetRoles);

    $("selRole").addEventListener("change", () => {
      updateLevelsDropdown();
      renderWeightsTable();
    });
    $("selLevel").addEventListener("change", renderWeightsTable);

    $("btnSaveWeights").addEventListener("click", saveWeights);
    $("btnQuickDefaults").addEventListener("click", loadExampleModel);

    renderModelLists();
  }

  // Paso 6: Empleados
  if ($("btnEmpImport")) $("btnEmpImport").addEventListener("click", importEmployeesExcel);
  if ($("btnEmpExport")) $("btnEmpExport").addEventListener("click", exportEmployeesExcel);

  if ($("empFilterRole")) $("empFilterRole").addEventListener("change", renderEmployeesTable);
  if ($("empFilterLevel")) $("empFilterLevel").addEventListener("change", renderEmployeesTable);
  if ($("empFilterSexo")) $("empFilterSexo").addEventListener("change", renderEmployeesTable);

  $("btnReset").addEventListener("click", () => {
    if (!confirm("¿Seguro? Se borrará lo guardado en este navegador.")) return;
    localStorage.removeItem("audit_session_meta");
    localStorage.removeItem("audit_items");
    localStorage.removeItem("audit_weighting_model");
    localStorage.removeItem("audit_employees");

    sessionMeta = { empresa: "", fecha: "", responsable: "" };
    items = TEMPLATE.map((x) => ({ ...x }));
    weightingModel = null;
    employees = [];

    saveLocal();
    setHeader();
    updateSummary();
    goStep(1);
  });

  goStep(1);
});