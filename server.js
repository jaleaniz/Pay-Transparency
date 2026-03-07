import express from "express";
import fetch from "node-fetch";
import PDFDocument from "pdfkit";
import { Document, Packer, Paragraph, HeadingLevel, TextRun } from "docx";

const app = express();
const PORT = process.env.PORT || 3000;

// Clave OpenAI (en local la pones por terminal; en DigitalOcean como ENV VAR)
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

app.use(express.json({ limit: "5mb" }));
app.use(express.static("./"));

// -------------------------
// Helpers: riesgos + plan temporal
// -------------------------
function getRisks(items = []) {
  return (items || []).filter((i) => i.status === "Riesgo");
}

function buildTimelinePlan(items = []) {
  const risks = getRisks(items);
  const improvements = (items || []).filter((i) => i.status === "Mejora");

  return [
    {
      fase: "0–30 días (Contención y evidencias)",
      acciones: [
        "Nombrar responsables (RRHH/Legal/Compliance) y calendario de trabajo.",
        "Recopilar evidencias faltantes de los puntos marcados como Riesgo.",
        "Centralizar evidencias en repositorio único (control de acceso, versionado).",
        `Priorizar ${risks.length} riesgos y documentar brechas.`,
      ],
    },
    {
      fase: "31–60 días (Remediación)",
      acciones: [
        "Actualizar políticas/procedimientos necesarios para cerrar riesgos.",
        "Implementar/ajustar criterios objetivos (promoción, bandas, progresión) donde falten.",
        `Abordar ${improvements.length} mejoras y convertirlas a OK con evidencia.`,
      ],
    },
    {
      fase: "61–90 días (Verificación y preparación)",
      acciones: [
        "Revisión interna del cumplimiento y prueba documental.",
        "Ensayo de respuesta a solicitudes de información y trazabilidad.",
        "Generar informe final con evidencias consolidadas.",
      ],
    },
  ];
}

// -------------------------
// Helpers: ponderaciones por puesto (0–5)
// -------------------------
// Estructura esperada (que guardaremos desde el front):
// weightingModel = {
//   criteria: [{ id, name, description }],
//   roles: [
//     {
//       roleName: "Analista",
//       weights: { "criterioId1": 3, "criterioId2": 5, ... } // 0..5
//     },
//     ...
//   ],
//   notes: "opcional"
// }
//
// Esto NO es el análisis salarial todavía; es el “modelo de factores objetivos” que luego usaremos
// para explicar el salario al importar Excel.
function summarizeWeightingModel(weightingModel) {
  if (!weightingModel) return null;

  const criteria = weightingModel.criteria || [];
  const roles = weightingModel.roles || [];

  // Resumen: por cada puesto, top criterios por peso
  const roleSummaries = roles.map((r) => {
    const weights = r.weights || {};
    const scored = criteria
      .map((c) => ({ name: c.name, w: Number(weights[c.id] ?? 0) }))
      .sort((a, b) => b.w - a.w)
      .slice(0, 5);

    return {
      roleName: r.roleName,
      top: scored.filter((x) => x.w > 0),
    };
  });

  return { criteriaCount: criteria.length, rolesCount: roles.length, roleSummaries };
}

// -------------------------
// API: Agente IA (OpenAI)
// -------------------------
app.post("/api/agent", async (req, res) => {
  const { prompt } = req.body || {};
  if (!prompt) return res.status(400).json({ error: "Falta prompt" });

  if (!OPENAI_API_KEY) {
    return res.status(500).json({
      error:
        "Falta OPENAI_API_KEY. En local: set OPENAI_API_KEY=... / en DigitalOcean: configúralo como variable de entorno.",
    });
  }

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [
          {
            role: "system",
            content:
              "Eres un auditor experto en auditoría retributiva, brecha salarial y Pay Transparency (UE). Responde claro, profesional y accionable.",
          },
          { role: "user", content: prompt },
        ],
      }),
    });

    const data = await response.json();

    const text =
      data?.choices?.[0]?.message?.content ||
      "Sin respuesta del modelo (revisa logs).";

    res.json({ text });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Error llamando a la IA" });
  }
});

// -------------------------
// API: Exportar PDF
// -------------------------
app.post("/api/report/pdf", async (req, res) => {
  const { sessionMeta, items, weightingModel } = req.body || {};
  const empresa = sessionMeta?.empresa || "—";
  const fecha = sessionMeta?.fecha || "—";
  const responsable = sessionMeta?.responsable || "—";

  const risks = getRisks(items || []);
  const timeline = buildTimelinePlan(items || []);
  const wm = summarizeWeightingModel(weightingModel);

  res.setHeader("Content-Type", "application/pdf");
  res.setHeader(
    "Content-Disposition",
    `attachment; filename="Informe_Auditoria_${sanitizeFileName(empresa)}.pdf"`
  );

  const doc = new PDFDocument({ margin: 50 });
  doc.pipe(res);

  // Título
  doc.fontSize(18).text("Informe de Auditoría Retributiva", { align: "center" });
  doc.moveDown(0.5);
  doc
    .fontSize(11)
    .fillColor("#334155")
    .text(
      "Redactado conforme a la Directiva (UE) 2023/970 (Pay Transparency Directive).",
      { align: "center" }
    );

  doc.moveDown(1.5);
  doc.fillColor("#0f172a").fontSize(12);
  doc.text(`Empresa: ${empresa}`);
  doc.text(`Fecha del informe: ${fecha}`);
  doc.text(`Responsable: ${responsable}`);

  doc.moveDown(1.2);
  doc.fontSize(13).text("1. Resumen ejecutivo", { underline: true });
  doc.fontSize(11).text(
    `Se han identificado ${risks.length} riesgos relevantes en la auditoría. ` +
      `Este informe sintetiza hallazgos y propone un plan temporal para su resolución.`,
    { lineGap: 3 }
  );

  // Modelo de ponderación (0–5)
  doc.moveDown(1.0);
  doc.fontSize(13).text("2. Modelo de ponderación por puestos (0–5)", { underline: true });
  doc.fontSize(11);

  if (!wm) {
    doc.text(
      "No se ha definido un modelo de ponderación por puesto. Se recomienda definir factores objetivos (0–5) que expliquen la estructura salarial.",
      { lineGap: 3 }
    );
  } else {
    doc.text(
      `Criterios definidos: ${wm.criteriaCount}. Puestos configurados: ${wm.rolesCount}.`,
      { lineGap: 3 }
    );
    wm.roleSummaries.forEach((r) => {
      doc.moveDown(0.4);
      doc.fillColor("#1e3a8a").text(`Puesto: ${r.roleName}`);
      doc.fillColor("#0f172a");
      if (!r.top || r.top.length === 0) {
        doc.text("• (sin ponderaciones asignadas)", { lineGap: 2 });
      } else {
        r.top.forEach((t) => doc.text(`• ${t.name}: ${t.w}/5`, { lineGap: 2 }));
      }
    });
    doc.moveDown(0.4);
    doc.fillColor("#64748b").fontSize(9).text(
      "Nota: Este modelo sirve como base para justificar diferencias salariales con factores objetivos. " +
        "En el paso de análisis salarial (Excel) se contrasta el ajuste del modelo frente a datos reales.",
      { lineGap: 2 }
    );
    doc.fillColor("#0f172a").fontSize(11);
  }

  // Riesgos
  doc.moveDown(1.0);
  doc.fontSize(13).text("3. Riesgos detectados", { underline: true });
  doc.fontSize(11);

  if (risks.length === 0) {
    doc.text("No se han marcado riesgos.", { lineGap: 3 });
  } else {
    risks.forEach((r, idx) => {
      doc.moveDown(0.4);
      doc.fontSize(11).fillColor("#991b1b").text(`Riesgo ${idx + 1}: ${r.req}`);
      doc.fillColor("#0f172a").fontSize(10).text(`Evidencia/Fuente: ${r.evidence || "No aportada"}`);
      doc.text(`Notas/Acción: ${r.notes || "—"}`);
    });
  }

  // Plan temporal
  doc.moveDown(1.0);
  doc.fontSize(13).text("4. Plan temporal de trabajo (propuesta)", { underline: true });
  doc.fontSize(11);

  timeline.forEach((t) => {
    doc.moveDown(0.6);
    doc.fillColor("#1e3a8a").text(t.fase);
    doc.fillColor("#0f172a");
    t.acciones.forEach((a) => doc.text(`• ${a}`, { lineGap: 2 }));
  });

  doc.moveDown(1.0);
  doc.fontSize(9).fillColor("#64748b").text(
    "Nota: Este informe es una herramienta de apoyo a la auditoría. Se recomienda revisión legal y validación documental.",
    { lineGap: 2 }
  );

  doc.end();
});

// -------------------------
// API: Exportar Word (DOCX)
// -------------------------
app.post("/api/report/docx", async (req, res) => {
  const { sessionMeta, items, weightingModel } = req.body || {};
  const empresa = sessionMeta?.empresa || "—";
  const fecha = sessionMeta?.fecha || "—";
  const responsable = sessionMeta?.responsable || "—";

  const risks = getRisks(items || []);
  const timeline = buildTimelinePlan(items || []);
  const wm = summarizeWeightingModel(weightingModel);

  const doc = new Document({
    sections: [
      {
        children: [
          new Paragraph({ text: "Informe de Auditoría Retributiva", heading: HeadingLevel.TITLE }),
          new Paragraph({
            children: [
              new TextRun({
                text: "Redactado conforme a la Directiva (UE) 2023/970 (Pay Transparency Directive).",
                italics: true,
              }),
            ],
          }),
          new Paragraph(`Empresa: ${empresa}`),
          new Paragraph(`Fecha del informe: ${fecha}`),
          new Paragraph(`Responsable: ${responsable}`),

          new Paragraph({ text: "1. Resumen ejecutivo", heading: HeadingLevel.HEADING_1 }),
          new Paragraph(
            `Se han identificado ${risks.length} riesgos relevantes en la auditoría. Se propone un plan temporal para su resolución.`
          ),

          new Paragraph({ text: "2. Modelo de ponderación por puestos (0–5)", heading: HeadingLevel.HEADING_1 }),
          ...(wm
            ? [
                new Paragraph(`Criterios definidos: ${wm.criteriaCount}. Puestos configurados: ${wm.rolesCount}.`),
                ...wm.roleSummaries.flatMap((r) => [
                  new Paragraph({ text: `Puesto: ${r.roleName}`, heading: HeadingLevel.HEADING_2 }),
                  ...(r.top?.length
                    ? r.top.map((t) => new Paragraph(`• ${t.name}: ${t.w}/5`))
                    : [new Paragraph("• (sin ponderaciones asignadas)")]),
                ]),
                new Paragraph({
                  children: [
                    new TextRun({
                      text:
                        "Nota: Modelo base para justificar diferencias salariales con factores objetivos. Se debe contrastar contra datos reales en el análisis Excel.",
                      italics: true,
                    }),
                  ],
                }),
              ]
            : [
                new Paragraph(
                  "No se ha definido un modelo de ponderación por puesto. Se recomienda definir factores objetivos (0–5) que expliquen la estructura salarial."
                ),
              ]),

          new Paragraph({ text: "3. Riesgos detectados", heading: HeadingLevel.HEADING_1 }),
          ...(risks.length === 0
            ? [new Paragraph("No se han marcado riesgos.")]
            : risks.flatMap((r, idx) => [
                new Paragraph({ text: `Riesgo ${idx + 1}: ${r.req}`, heading: HeadingLevel.HEADING_2 }),
                new Paragraph(`Evidencia/Fuente: ${r.evidence || "No aportada"}`),
                new Paragraph(`Notas/Acción: ${r.notes || "—"}`),
              ])),

          new Paragraph({ text: "4. Plan temporal de trabajo (propuesta)", heading: HeadingLevel.HEADING_1 }),
          ...timeline.flatMap((t) => [
            new Paragraph({ text: t.fase, heading: HeadingLevel.HEADING_2 }),
            ...t.acciones.map((a) => new Paragraph(`• ${a}`)),
          ]),

          new Paragraph(
            "Nota: Este informe es una herramienta de apoyo a la auditoría. Se recomienda revisión legal y validación documental."
          ),
        ],
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  res.setHeader(
    "Content-Type",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  );
  res.setHeader(
    "Content-Disposition",
    `attachment; filename="Informe_Auditoria_${sanitizeFileName(empresa)}.docx"`
  );
  res.send(buffer);
});

// -------------------------
// Utilidad: sanitizar nombres de archivo
// -------------------------
function sanitizeFileName(name) {
  return String(name || "Empresa").replace(/[\\/:*?"<>|]/g, "_").slice(0, 80);
}

// -------------------------
// Arranque
// -------------------------
app.listen(PORT, () => {
  console.log(`Servidor corriendo en http://localhost:${PORT}`);
});