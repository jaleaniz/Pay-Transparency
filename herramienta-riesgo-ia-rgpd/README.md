# Radar IA y Datos

Herramienta de análisis de riesgo del uso de inteligencia artificial y del tratamiento de datos personales en empresas, para aplicarla en clientes. Un solo archivo HTML, sin servidor: los datos del cliente no salen del navegador.

Elaborado por otraforma.

## Uso

1. Abre `index.html` en cualquier navegador moderno (doble clic sobre el archivo).
2. Fase 1, Cliente: alcance del análisis, datos de la evaluación, DPD, RLT.
   - Alcance "Completo": 8 dimensiones, 47 controles e inventario de IA.
   - Alcance "Solo protección de datos": 6 dimensiones y 28 controles del RGPD y la LOPDGDD. Se ocultan el inventario de IA, las dos dimensiones de IA y los controles específicos de herramientas de IA. El informe se titula "tratamiento de datos personales".
   - Alcance "Solo uso de IA": inventario de IA, las dos dimensiones del Reglamento de IA y los 15 controles del RGPD vinculados al uso de IA (31 controles en total).
   - Cambiar de alcance no borra respuestas: los controles ocultos se conservan.
3. Fase 2, Inventario IA: registra cada sistema de IA en uso. La herramienta propone la clasificación según el Reglamento de IA y señala los efectos en el RGPD (RAT, EIPD, art. 22, art. 28, transferencias).
4. Fase 3, Cuestionario: 47 controles en 8 dimensiones. Responde con evidencia: Sí, Parcial, No o No aplica. Cada control admite una nota.
5. Fase 4, Resultados: riesgo global y por dimensión, alertas críticas, mapa probabilidad × impacto, clasificación de sistemas y plan de acción priorizado con referencia normativa y plazo.
6. Fase 5, Informe: documento con marca otraforma. "Copiar informe" lo lleva al portapapeles en texto; "Imprimir o guardar PDF" usa el diálogo del navegador (solo al abrir el archivo localmente).

Guardado: la evaluación se autoguarda en el navegador. Para archivarla por cliente o cambiar de equipo, usa "Exportar JSON" e "Importar JSON". "Nueva evaluación" borra la actual tras confirmar.

## Metodología

- Riesgo de cada control = probabilidad (Sí 1, Parcial 2, No 3) × impacto fijo del control (1 a 3). Escala 1 a 9, conforme al enfoque de la guía de la AEPD *Gestión del riesgo y evaluación de impacto en tratamientos de datos personales* (2021).
- Puntuación por dimensión: media de los riesgos de los controles aplicables, llevada a 0 a 100. Global: media de las dimensiones con datos.
- Niveles: bajo (menos de 25), medio (25 a 49), alto (50 a 74), muy alto (75 o más).
- Alertas críticas: reglas independientes de la puntuación (práctica prohibida art. 5 RIA, art. 22 RGPD sin intervención humana, EIPD exigible no realizada, transferencias sin garantías, categorías especiales sin excepción, proveedor sin contrato art. 28, posible DPD obligatorio, art. 4 RIA, art. 64.4.d ET).
- Clasificación de sistemas: prohibido (art. 5), alto riesgo (art. 6.2 y Anexo III), transparencia (art. 50), mínimo.

## Dimensiones y marco

| Dimensión | Marco |
|---|---|
| Gobernanza y responsabilidad proactiva | Arts. 5.2, 24, 30, 37 a 39 RGPD; art. 34 LOPDGDD |
| Licitud, información y finalidad | Arts. 5, 6, 7, 9, 13 y 14 RGPD; art. 11 LOPDGDD |
| Encargados, proveedores de IA y transferencias | Art. 28 y capítulo V RGPD |
| Seguridad y brechas | Arts. 32 a 34 RGPD |
| Derechos y decisiones automatizadas | Arts. 12 a 22 RGPD |
| Evaluación de impacto y diseño | Arts. 25, 35 y 36 RGPD |
| Gobernanza de la IA | Arts. 4, 5, 6, 25, 26, 27 y 50 Reglamento (UE) 2024/1689 |
| IA en el ámbito laboral y uso cotidiano | Anexo III.4 RIA; arts. 20 bis y 64.4.d ET; arts. 87 a 91 LOPDGDD |

## Fechas normativas incorporadas (revisar periódicamente)

- Reglamento (UE) 2024/1689: prohibiciones y alfabetización en IA desde el 2 de febrero de 2025; modelos de uso general desde el 2 de agosto de 2025; transparencia (art. 50) desde el 2 de agosto de 2026.
- Reglamento (UE) 2026/1744 (Ómnibus digital sobre IA): adoptado el 8 de julio de 2026, publicado en el DOUE el 24 de julio y en vigor desde el 27 de julio de 2026. Aplaza el alto riesgo del Anexo III al 2 de diciembre de 2027 y el del Anexo I al 2 de agosto de 2028.
- Proyecto de Ley Orgánica para el buen uso y la gobernanza de la inteligencia artificial (expediente 121/000096): en tramitación en el Congreso en noviembre de 2026. No es norma vigente.

## Mantenimiento

Todo el contenido (controles, ámbitos del Anexo III, prácticas prohibidas, textos del informe) está en el bloque `<script>` de `index.html`, en las constantes `DIMENSIONES`, `AMBITOS` y `PROHIB`. Para añadir un control basta con añadir un objeto con `id`, `t` (texto), `ref` (referencia), `imp` (impacto 1 a 3) y `acc` (acción recomendada).

## Límites

Evaluación preliminar. No sustituye una EIPD formal, el dictamen de un abogado ni el criterio del DPD.
