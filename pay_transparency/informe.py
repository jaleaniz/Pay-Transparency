"""Exportación del informe de brechas a Excel."""

from __future__ import annotations

import datetime as dt
from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .analisis import AMBITOS, COLORES, CONCEPTOS, Resultado, Umbrales

FUENTE = "Helvetica"


def _formatear(ws, df: pd.DataFrame, fila_inicio: int = 1) -> None:
    for celda in ws[fila_inicio]:
        celda.font = Font(bold=True, color="FFFFFF", name=FUENTE, size=10)
        celda.fill = PatternFill("solid", fgColor="2F2F2F")
        celda.alignment = Alignment(vertical="center", wrap_text=True)
    for idx, columna in enumerate(df.columns, start=1):
        valores = [len(str(v)) for v in df[columna].head(200)] if len(df) else [0]
        ws.column_dimensions[get_column_letter(idx)].width = min(max(len(str(columna)), *valores) + 2, 60)
    if "Semáforo" in df.columns or "Nivel" in df.columns:
        col = list(df.columns).index("Semáforo" if "Semáforo" in df.columns else "Nivel") + 1
        for fila in range(fila_inicio + 1, fila_inicio + 1 + len(df)):
            celda = ws.cell(row=fila, column=col)
            color = COLORES.get(str(celda.value))
            if color:
                celda.fill = PatternFill("solid", fgColor=color.lstrip("#"))
                celda.font = Font(bold=True, color="FFFFFF", name=FUENTE, size=10)
                celda.alignment = Alignment(horizontal="center")
    for fila in ws.iter_rows(min_row=fila_inicio + 1, max_row=fila_inicio + len(df)):
        for celda in fila:
            if celda.font.name != FUENTE or celda.font.bold is not True:
                celda.font = Font(name=FUENTE, size=10, bold=celda.font.bold, color=celda.font.color)
            celda.alignment = Alignment(vertical="top", wrap_text=True)


def exportar_informe(resultado: Resultado, datos_pseudonimizados: pd.DataFrame | None, umbrales: Umbrales, nombre_empresa: str = "") -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # Resumen
        filas = [
            ("Informe de transparencia retributiva", ""),
            ("Empresa", nombre_empresa or "No indicada"),
            ("Fecha", dt.date.today().strftime("%d/%m/%Y")),
            ("Estado global (semáforo)", resultado.estado_global),
            ("Personas analizadas", resultado.resumen["personas"]),
            ("Mujeres", resultado.resumen["mujeres"]),
            ("Hombres", resultado.resumen["hombres"]),
            ("", ""),
        ]
        for concepto, fila in resultado.resumen["conceptos"].items():
            filas.append((f"Brecha media global · {CONCEPTOS[concepto]} (%)", fila["Brecha media (%)"]))
            filas.append((f"Brecha mediana global · {CONCEPTOS[concepto]} (%)", fila["Brecha mediana (%)"]))
        if resultado.resumen.get("brecha_total_sin_equiparar") is not None:
            filas.append(("Brecha media total sin equiparar a jornada completa (%)", round(resultado.resumen["brecha_total_sin_equiparar"], 1)))
        if resultado.ajustada.get("disponible"):
            filas.append(("Brecha ajustada a igual puesto y antigüedad (%)", resultado.ajustada["brecha_ajustada_pct"]))
            ic = resultado.ajustada["ic95"]
            filas.append(("Intervalo de confianza 95 % (%)", f"{ic[0]} a {ic[1]}" if ic[0] is not None else "n/d"))
            filas.append(("Estadísticamente significativa", "Sí" if resultado.ajustada["significativa"] else "No"))
        filas += [
            ("", ""),
            ("Leyenda del semáforo", ""),
            ("VERDE", f"Brecha media inferior al {umbrales.verde:g} %"),
            ("ÁMBAR", f"Brecha media entre el {umbrales.verde:g} % y el {umbrales.rojo:g} %, o segregación por sexo"),
            ("ROJO", f"Brecha media igual o superior al {umbrales.rojo:g} % (art. 28.3 ET: obligación de justificación)"),
            ("GRIS", f"No concluyente: menos de {umbrales.n_minimo} personas de algún sexo o un solo sexo en el grupo"),
            ("", ""),
            ("Convención", "Brecha = (hombres - mujeres) / hombres. Positiva: las mujeres cobran menos. Retribuciones equiparadas a jornada completa."),
            ("Marco normativo", "Art. 28 ET; RD 902/2020 de igualdad retributiva; Directiva (UE) 2023/970 de transparencia retributiva."),
            ("Aviso", "Herramienta de apoyo. No sustituye al registro retributivo ni a la auditoría retributiva legalmente exigibles."),
            ("", ""),
            ("Elaborado por otraforma", ""),
        ]
        resumen = pd.DataFrame(filas, columns=["Indicador", "Valor"])
        resumen.to_excel(writer, sheet_name="Resumen", index=False)
        ws = writer.sheets["Resumen"]
        _formatear(ws, resumen)
        ws.column_dimensions["A"].width = 58
        ws.column_dimensions["B"].width = 70
        for fila in range(2, len(resumen) + 2):
            etiqueta = ws.cell(row=fila, column=1).value
            celda_valor = ws.cell(row=fila, column=2)
            color = COLORES.get(str(celda_valor.value)) or COLORES.get(str(etiqueta))
            if color and (etiqueta in COLORES or etiqueta == "Estado global (semáforo)"):
                objetivo = ws.cell(row=fila, column=1) if etiqueta in COLORES else celda_valor
                objetivo.fill = PatternFill("solid", fgColor=color.lstrip("#"))
                objetivo.font = Font(bold=True, color="FFFFFF", name=FUENTE, size=10)

        # Alertas
        alertas = resultado.alertas if not resultado.alertas.empty else pd.DataFrame([{"Nivel": "VERDE", "Mensaje": "Sin alertas"}])
        alertas.to_excel(writer, sheet_name="Alertas", index=False)
        _formatear(writer.sheets["Alertas"], alertas)

        # Tablas por ámbito
        for clave, tabla in resultado.tablas.items():
            ambito, concepto = clave.split("|")
            nombre = f"{AMBITOS[ambito].split(' (')[0]} · {CONCEPTOS[concepto]}"[:31]
            tabla.to_excel(writer, sheet_name=nombre, index=False)
            _formatear(writer.sheets[nombre], tabla)

        resultado.representacion.to_excel(writer, sheet_name="Representación", index=False)
        _formatear(writer.sheets["Representación"], resultado.representacion)
        resultado.parcialidad.to_excel(writer, sheet_name="Jornada", index=False)
        _formatear(writer.sheets["Jornada"], resultado.parcialidad)

        if datos_pseudonimizados is not None:
            datos_pseudonimizados.to_excel(writer, sheet_name="Datos pseudonimizados", index=False)
            _formatear(writer.sheets["Datos pseudonimizados"], datos_pseudonimizados)

    return buffer.getvalue()
