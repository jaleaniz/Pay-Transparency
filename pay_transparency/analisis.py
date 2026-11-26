"""Análisis de brechas retributivas entre sexos y alertas tipo semáforo.

Marco de referencia (España):

- Art. 28 del Estatuto de los Trabajadores: igual retribución por trabajo de
  igual valor. Cuando el promedio de las retribuciones de un sexo sea superior
  al del otro en un 25 % o más, la empresa debe justificar que no obedece a
  motivos relacionados con el sexo (art. 28.3 ET).
- Real Decreto 902/2020, de igualdad retributiva: registro retributivo con
  medias y medianas por sexo, desagregadas por grupo profesional, categoría,
  puesto y por concepto (salario base, complementos, percepciones
  extrasalariales), equiparando a jornada completa.
- Directiva (UE) 2023/970 de transparencia retributiva: fija en el 5 % la
  brecha que, sin justificación objetiva, obliga a una evaluación retributiva
  conjunta.

Convención de signo: la brecha se calcula como (hombres - mujeres) / hombres.
Un valor positivo indica que las mujeres cobran menos; negativo, que cobran
más. Ambos sentidos generan alerta, porque la norma protege a los dos sexos.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .pseudonimizacion import normalizar

VERDE, AMBAR, ROJO, GRIS = "VERDE", "ÁMBAR", "ROJO", "GRIS"
COLORES = {VERDE: "#2e7d32", AMBAR: "#f9a825", ROJO: "#c62828", GRIS: "#9e9e9e"}
ICONOS = {VERDE: "🟢", AMBAR: "🟡", ROJO: "🔴", GRIS: "⚪"}
ORDEN_NIVEL = {ROJO: 0, AMBAR: 1, GRIS: 2, VERDE: 3}

CONCEPTOS = {"total": "Retribución total", "base": "Salario base", "complementos": "Complementos"}
AMBITOS = {"puesto": "Puesto (igual trabajo)", "grupo": "Grupo profesional (igual valor)", "departamento": "Departamento"}

# Patrones para reconocer las columnas de un Excel cualquiera.
PATRONES_CAMPOS = {
    "sexo": [r"\bsexo\b", r"g[eé]nero"],
    "puesto": [r"\bpuesto\b", r"cargo", r"posici[oó]n", r"categor[ií]a"],
    "departamento": [r"departamento", r"\b[aá]rea\b", r"unidad"],
    "grupo": [r"grupo\s*prof", r"\bgrupo\b", r"\bnivel\b", r"banda"],
    "antiguedad": [r"antig"],
    "fecha_alta": [r"fecha\s*(de\s*)?(alta|ingreso|incorporaci)"],
    "jornada": [r"jornada", r"\bfte\b", r"parcialidad"],
    "base": [r"salario\s*base", r"sueldo\s*base", r"\bbase\b"],
    "complementos": [r"complemento", r"plus", r"variable", r"bonus"],
    "total": [r"retribuci[oó]n\s*total", r"salario\s*total", r"\btotal\b", r"bruto\s*anual"],
}
CAMPOS_OBLIGATORIOS = ("sexo", "puesto", "base")


@dataclass
class Umbrales:
    """Umbrales del semáforo, en puntos porcentuales de brecha."""

    verde: float = 5.0  # por debajo: verde (referencia: Directiva 2023/970)
    rojo: float = 25.0  # a partir de aquí: rojo (referencia: art. 28.3 ET)
    n_minimo: int = 3  # personas de cada sexo necesarias para comparar con fiabilidad
    representacion_min: float = 25.0  # % mínimo de un sexo en un ámbito antes de avisar de segregación
    materialidad: float = 1.0  # % de la retribución total por debajo del cual una diferencia en un concepto se considera inmaterial

    def nivel(self, brecha: float | None) -> str:
        if brecha is None or pd.isna(brecha):
            return GRIS
        valor = abs(brecha)
        if valor >= self.rojo:
            return ROJO
        if valor >= self.verde:
            return AMBAR
        return VERDE


@dataclass
class Resultado:
    resumen: dict
    ajustada: dict
    tablas: dict[str, pd.DataFrame]
    representacion: pd.DataFrame
    parcialidad: pd.DataFrame
    alertas: pd.DataFrame
    estado_global: str
    avisos: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Preparación de datos
# ---------------------------------------------------------------------------


def detectar_mapeo(columnas: list[str]) -> dict[str, str | None]:
    """Propone qué columna del fichero corresponde a cada campo del análisis."""
    mapeo: dict[str, str | None] = {campo: None for campo in PATRONES_CAMPOS}
    usadas: set[str] = set()
    for campo, patrones in PATRONES_CAMPOS.items():
        for patron in patrones:
            candidatas = [c for c in columnas if c not in usadas and re.search(patron, normalizar(c))]
            if candidatas:
                mapeo[campo] = candidatas[0]
                usadas.add(candidatas[0])
                break
    return mapeo


def normalizar_sexo(valor) -> str | None:
    if pd.isna(valor):
        return None
    v = normalizar(valor)
    if v in {"mujer", "m", "f", "femenino", "female", "woman", "mujeres"}:
        return "Mujer"
    if v in {"hombre", "h", "v", "masculino", "male", "man", "varon", "hombres"}:
        return "Hombre"
    return None


def preparar_datos(df: pd.DataFrame, mapeo: dict[str, str | None], referencia: dt.date | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Convierte el fichero a un esquema estándar y equipara las retribuciones a jornada completa."""
    avisos: list[str] = []
    faltan = [c for c in CAMPOS_OBLIGATORIOS if not mapeo.get(c)]
    if faltan:
        raise ValueError(f"Faltan columnas obligatorias: {', '.join(faltan)}")

    datos = pd.DataFrame(index=df.index)
    if "Pseudónimo" in df.columns:
        datos["pseudonimo"] = df["Pseudónimo"].astype(str)
    datos["sexo"] = df[mapeo["sexo"]].map(normalizar_sexo)
    datos["puesto"] = df[mapeo["puesto"]].astype(str).str.strip()

    for campo in ("departamento", "grupo"):
        col = mapeo.get(campo)
        datos[campo] = df[col].astype(str).str.strip() if col else "Sin informar"
        if not col:
            avisos.append(f"No se ha encontrado la columna de {campo}; se omite ese nivel de análisis.")

    datos["base"] = pd.to_numeric(df[mapeo["base"]], errors="coerce")
    col_comp = mapeo.get("complementos")
    datos["complementos"] = pd.to_numeric(df[col_comp], errors="coerce").fillna(0.0) if col_comp else 0.0
    if not col_comp:
        avisos.append("No hay columna de complementos; el análisis por concepto se limita al salario base.")
    col_total = mapeo.get("total")
    datos["total"] = pd.to_numeric(df[col_total], errors="coerce") if col_total else datos["base"] + datos["complementos"]
    datos["total"] = datos["total"].fillna(datos["base"] + datos["complementos"])

    col_jornada = mapeo.get("jornada")
    if col_jornada:
        jornada = pd.to_numeric(df[col_jornada], errors="coerce")
        if jornada.dropna().le(1).all():  # viene como fracción (0.5) en lugar de porcentaje (50)
            jornada = jornada * 100
        datos["jornada"] = jornada.fillna(100.0).clip(lower=1)
    else:
        datos["jornada"] = 100.0
        avisos.append("No hay columna de jornada; se asume jornada completa para todas las personas.")

    col_ant, col_alta = mapeo.get("antiguedad"), mapeo.get("fecha_alta")
    if col_ant:
        datos["antiguedad"] = pd.to_numeric(df[col_ant], errors="coerce")
    elif col_alta:
        ref = pd.Timestamp(referencia or dt.date.today())
        datos["antiguedad"] = ((ref - pd.to_datetime(df[col_alta], errors="coerce")).dt.days / 365.25).round(1)
    else:
        datos["antiguedad"] = np.nan
        avisos.append("No hay antigüedad ni fecha de alta; la brecha ajustada no podrá descontar la antigüedad.")

    factor = 100.0 / datos["jornada"]
    for concepto in CONCEPTOS:
        datos[f"{concepto}_jc"] = datos[concepto] * factor

    sin_sexo = datos["sexo"].isna().sum()
    if sin_sexo:
        avisos.append(f"{sin_sexo} fila(s) sin sexo reconocible se han excluido del análisis.")
    sin_salario = datos["base"].isna().sum()
    if sin_salario:
        avisos.append(f"{sin_salario} fila(s) sin salario base numérico se han excluido del análisis.")
    datos = datos.dropna(subset=["sexo", "base"]).reset_index(drop=True)
    return datos, avisos


# ---------------------------------------------------------------------------
# Cálculo de brechas
# ---------------------------------------------------------------------------


def brecha_pct(mujeres: pd.Series, hombres: pd.Series, estadistico: str = "mean") -> float | None:
    """Brecha porcentual (hombres - mujeres) / hombres. None si falta alguno de los dos grupos."""
    if len(mujeres) == 0 or len(hombres) == 0:
        return None
    m = getattr(mujeres, estadistico)()
    h = getattr(hombres, estadistico)()
    if not h:
        return None
    return float((h - m) / h * 100)


def _fila_brecha(grupo: pd.DataFrame, columna: str, umbrales: Umbrales, concepto: str = "total") -> dict:
    mujeres = grupo.loc[grupo["sexo"] == "Mujer", columna]
    hombres = grupo.loc[grupo["sexo"] == "Hombre", columna]
    n_m, n_h = len(mujeres), len(hombres)
    media = brecha_pct(mujeres, hombres, "mean")
    mediana = brecha_pct(mujeres, hombres, "median")

    # Un complemento puede tener una brecha enorme en % y ser irrelevante en euros.
    # Se mide la diferencia de medias frente a la retribución total media del grupo.
    inmaterial = False
    if concepto != "total" and n_m and n_h and "total_jc" in grupo.columns:
        diferencia = abs(hombres.mean() - mujeres.mean())
        inmaterial = diferencia < umbrales.materialidad / 100 * grupo["total_jc"].mean()

    if n_m == 0 or n_h == 0:
        nivel, motivo = GRIS, "Solo hay personas de un sexo: no es posible comparar"
    elif inmaterial:
        nivel, motivo = VERDE, f"Diferencia inferior al {umbrales.materialidad:g} % de la retribución total: inmaterial"
    elif n_m < umbrales.n_minimo or n_h < umbrales.n_minimo:
        if media is not None and abs(media) >= umbrales.rojo:
            nivel, motivo = AMBAR, f"Brecha ≥ {umbrales.rojo:g} % con muestra pequeña: revisar caso a caso"
        else:
            nivel, motivo = GRIS, f"Menos de {umbrales.n_minimo} personas de algún sexo: resultado no concluyente"
    else:
        nivel = umbrales.nivel(media)
        referencia_legal = " (umbral del art. 28.3 ET)" if concepto == "total" else ""
        motivo = {
            ROJO: f"Brecha media ≥ {umbrales.rojo:g} %{referencia_legal}: requiere justificación objetiva",
            AMBAR: f"Brecha media entre {umbrales.verde:g} % y {umbrales.rojo:g} %: requiere revisión",
            VERDE: f"Brecha media < {umbrales.verde:g} %",
        }[nivel]

    def _r(valor, decimales=2):
        return None if valor is None or pd.isna(valor) else float(round(float(valor), decimales))

    return {
        "Mujeres (n)": n_m,
        "Hombres (n)": n_h,
        "Media mujeres (€)": _r(mujeres.mean()) if n_m else None,
        "Media hombres (€)": _r(hombres.mean()) if n_h else None,
        "Brecha media (%)": _r(media, 1),
        "Mediana mujeres (€)": _r(mujeres.median()) if n_m else None,
        "Mediana hombres (€)": _r(hombres.median()) if n_h else None,
        "Brecha mediana (%)": _r(mediana, 1),
        "Semáforo": nivel,
        "Motivo": motivo,
    }


def tabla_brechas(datos: pd.DataFrame, por: str, concepto: str = "total", umbrales: Umbrales | None = None) -> pd.DataFrame:
    """Brecha por cada valor de ``por`` (puesto, grupo o departamento) para un concepto retributivo."""
    umbrales = umbrales or Umbrales()
    columna = f"{concepto}_jc"
    filas = []
    for valor, grupo in datos.groupby(por, sort=True):
        fila = {AMBITOS.get(por, por).split(" (")[0]: valor, "Concepto": CONCEPTOS[concepto]}
        fila.update(_fila_brecha(grupo, columna, umbrales, concepto))
        filas.append(fila)
    tabla = pd.DataFrame(filas)
    if tabla.empty:
        return tabla
    tabla["_orden"] = tabla["Semáforo"].map(ORDEN_NIVEL)
    tabla["_abs"] = tabla["Brecha media (%)"].abs().fillna(-1)
    return tabla.sort_values(["_orden", "_abs"], ascending=[True, False]).drop(columns=["_orden", "_abs"]).reset_index(drop=True)


def brecha_global(datos: pd.DataFrame, concepto: str, umbrales: Umbrales) -> dict:
    fila = _fila_brecha(datos, f"{concepto}_jc", umbrales, concepto)
    fila["Concepto"] = CONCEPTOS[concepto]
    return fila


def brecha_ajustada(datos: pd.DataFrame) -> dict:
    """Brecha ajustada por puesto y antigüedad mediante regresión lineal sobre el logaritmo de la retribución.

    Responde a la pregunta: a igual puesto y antigüedad, ¿cuánto menos cobran las mujeres?
    """
    d = datos[(datos["total_jc"] > 0)].copy()
    tiene_ant = d["antiguedad"].notna().all() and d["antiguedad"].nunique() > 1
    if not tiene_ant:
        d["antiguedad"] = 0.0
    y = np.log(d["total_jc"].to_numpy(dtype=float))
    mujer = (d["sexo"] == "Mujer").astype(float).to_numpy()
    dummies = pd.get_dummies(d["puesto"], drop_first=True, dtype=float)
    X = np.column_stack([np.ones(len(d)), mujer, d["antiguedad"].to_numpy(dtype=float), dummies.to_numpy()])
    if len(d) <= X.shape[1] + 2 or mujer.sum() == 0 or mujer.sum() == len(d):
        return {"disponible": False, "motivo": "Muestra insuficiente para estimar la brecha ajustada."}
    coef, _, rango, _ = np.linalg.lstsq(X, y, rcond=None)
    residuos = y - X @ coef
    gl = len(d) - rango
    sigma2 = float(residuos @ residuos) / gl if gl > 0 else float("nan")
    try:
        var = sigma2 * np.linalg.pinv(X.T @ X)[1, 1]
        error = float(np.sqrt(var))
    except (np.linalg.LinAlgError, ValueError):
        error = float("nan")
    gap = (1 - np.exp(coef[1])) * 100
    ic = ((1 - np.exp(coef[1] + 1.96 * error)) * 100, (1 - np.exp(coef[1] - 1.96 * error)) * 100) if error == error else (None, None)
    return {
        "disponible": True,
        "brecha_ajustada_pct": round(float(gap), 1),
        "ic95": tuple(round(v, 1) if v is not None else None for v in ic),
        "controles": ["puesto"] + (["antigüedad"] if tiene_ant else []),
        "n": int(len(d)),
        "significativa": bool(error == error and abs(coef[1]) > 1.96 * error),
    }


# ---------------------------------------------------------------------------
# Representación y parcialidad
# ---------------------------------------------------------------------------


def representacion(datos: pd.DataFrame, por: str, umbrales: Umbrales) -> pd.DataFrame:
    total_mujeres = (datos["sexo"] == "Mujer").mean() * 100
    filas = []
    for valor, grupo in datos.groupby(por, sort=True):
        n = len(grupo)
        pct_m = (grupo["sexo"] == "Mujer").mean() * 100
        if n < umbrales.n_minimo:
            nivel, motivo = GRIS, "Grupo demasiado pequeño"
        elif pct_m < umbrales.representacion_min or pct_m > 100 - umbrales.representacion_min:
            sexo_minoritario = "mujeres" if pct_m < 50 else "hombres"
            nivel, motivo = AMBAR, f"Segregación: menos del {umbrales.representacion_min:g} % de {sexo_minoritario}"
        else:
            nivel, motivo = VERDE, "Composición equilibrada"
        filas.append(
            {
                AMBITOS.get(por, por).split(" (")[0]: valor,
                "Personas": n,
                "Mujeres (n)": int((grupo["sexo"] == "Mujer").sum()),
                "Hombres (n)": int((grupo["sexo"] == "Hombre").sum()),
                "% mujeres": round(pct_m, 1),
                "% mujeres en la empresa": round(total_mujeres, 1),
                "Semáforo": nivel,
                "Motivo": motivo,
            }
        )
    return pd.DataFrame(filas)


def parcialidad(datos: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for sexo, grupo in datos.groupby("sexo"):
        filas.append(
            {
                "Sexo": sexo,
                "Personas": len(grupo),
                "A tiempo parcial (n)": int((grupo["jornada"] < 100).sum()),
                "% a tiempo parcial": round((grupo["jornada"] < 100).mean() * 100, 1),
                "Jornada media (%)": round(grupo["jornada"].mean(), 1),
            }
        )
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------


def _alerta(nivel, ambito, elemento, indicador, valor, mensaje, recomendacion) -> dict:
    return {
        "Nivel": nivel,
        "Ámbito": ambito,
        "Elemento": elemento,
        "Indicador": indicador,
        "Valor": valor,
        "Mensaje": mensaje,
        "Recomendación": recomendacion,
    }


def _texto_direccion(brecha: float) -> str:
    return "las mujeres cobran menos" if brecha > 0 else "los hombres cobran menos"


def generar_alertas(resumen: dict, ajustada: dict, tablas: dict[str, pd.DataFrame], repres: pd.DataFrame, parc: pd.DataFrame, umbrales: Umbrales) -> pd.DataFrame:
    alertas: list[dict] = []

    # 1. Brecha global por concepto
    for concepto, fila in resumen["conceptos"].items():
        brecha = fila["Brecha media (%)"]
        nivel = fila["Semáforo"]
        if brecha is None:
            continue
        if nivel == ROJO:
            mensaje = f"La brecha media global en {CONCEPTOS[concepto].lower()} es del {abs(brecha):.1f} % ({_texto_direccion(brecha)}). Supera el 25 % del art. 28.3 ET."
            reco = "Incluir en el registro retributivo una justificación objetiva y ajena al sexo; si no existe, abrir plan de corrección."
        elif nivel == AMBAR:
            mensaje = f"La brecha media global en {CONCEPTOS[concepto].lower()} es del {abs(brecha):.1f} % ({_texto_direccion(brecha)})."
            reco = "Analizar por puesto y grupo profesional para localizar el origen; la Directiva 2023/970 fija el 5 % como umbral de evaluación conjunta."
        else:
            mensaje = f"La brecha media global en {CONCEPTOS[concepto].lower()} es del {abs(brecha):.1f} %, dentro del margen aceptable."
            reco = "Mantener seguimiento anual en el registro retributivo."
        alertas.append(_alerta(nivel, "Global", "Toda la plantilla", f"Brecha media · {CONCEPTOS[concepto]}", round(brecha, 1), mensaje, reco))

    # 2. Brecha ajustada
    if ajustada.get("disponible"):
        gap = ajustada["brecha_ajustada_pct"]
        nivel = umbrales.nivel(gap) if ajustada["significativa"] or abs(gap) >= umbrales.rojo else (VERDE if abs(gap) < umbrales.verde else AMBAR)
        controles = " y ".join(ajustada["controles"])
        mensaje = f"A igual {controles}, la brecha estimada es del {abs(gap):.1f} % ({_texto_direccion(gap)})."
        mensaje += " Estadísticamente significativa." if ajustada["significativa"] else " No es estadísticamente significativa con esta muestra."
        reco = "Es la cifra más cercana al principio 'igual trabajo, igual salario'. Si es relevante, revisar criterios de fijación salarial y complementos." if nivel != VERDE else "Sin acción específica."
        alertas.append(_alerta(nivel, "Global", "Toda la plantilla", "Brecha ajustada (igual puesto y antigüedad)", gap, mensaje, reco))

    # 3. Brechas por ámbito y concepto. El departamento no es un comparador legal
    #    (mezcla puestos distintos), así que se muestra en tablas pero no genera alertas.
    for clave, tabla in tablas.items():
        ambito, concepto = clave.split("|")
        if tabla.empty or ambito == "departamento":
            continue
        nombre_col = tabla.columns[0]
        for _, fila in tabla.iterrows():
            nivel, brecha = fila["Semáforo"], fila["Brecha media (%)"]
            if nivel == VERDE or brecha is None or pd.isna(brecha):
                continue
            if nivel == GRIS:
                continue  # los no concluyentes se listan en las tablas, no como alertas
            elemento = f"{fila[nombre_col]}"
            detalle = f"{fila['Mujeres (n)']} mujeres y {fila['Hombres (n)']} hombres"
            if nivel == ROJO:
                mensaje = f"En '{elemento}' ({detalle}) la brecha media en {CONCEPTOS[concepto].lower()} es del {abs(brecha):.1f} %: {_texto_direccion(brecha)}."
                reco = "Posible incumplimiento del principio de igual retribución (art. 28 ET). Revisar persona a persona y documentar la justificación o corregir."
            else:
                mensaje = f"En '{elemento}' ({detalle}) la brecha media en {CONCEPTOS[concepto].lower()} es del {abs(brecha):.1f} %: {_texto_direccion(brecha)}."
                reco = "Comprobar si la diferencia se explica por antigüedad, jornada u objetivos. Si no, corregir en la próxima revisión salarial." if "muestra pequeña" not in fila["Motivo"] else fila["Motivo"] + "."
            alertas.append(_alerta(nivel, AMBITOS[ambito], elemento, f"Brecha media · {CONCEPTOS[concepto]}", round(brecha, 1), mensaje, reco))

    # 4. Representación (segregación horizontal/vertical)
    if not repres.empty:
        nombre_col = repres.columns[0]
        for _, fila in repres.iterrows():
            if fila["Semáforo"] != AMBAR:
                continue
            alertas.append(
                _alerta(
                    AMBAR,
                    "Representación",
                    fila[nombre_col],
                    "% mujeres",
                    fila["% mujeres"],
                    f"En '{fila[nombre_col]}' hay un {fila['% mujeres']:.0f} % de mujeres frente al {fila['% mujeres en la empresa']:.0f} % de la empresa ({fila['Personas']} personas).",
                    "Revisar procesos de selección y promoción; la segregación ocupacional es una de las causas principales de la brecha global.",
                )
            )

    # 5. Parcialidad
    if len(parc) == 2:
        p = parc.set_index("Sexo")["% a tiempo parcial"]
        if p.get("Mujer", 0) > 0 and p.get("Mujer", 0) >= 2 * max(p.get("Hombre", 0), 1) and p.get("Mujer", 0) >= 10:
            alertas.append(
                _alerta(
                    AMBAR,
                    "Jornada",
                    "Tiempo parcial",
                    "% a tiempo parcial",
                    p["Mujer"],
                    f"El {p['Mujer']:.0f} % de las mujeres trabaja a tiempo parcial frente al {p.get('Hombre', 0):.0f} % de los hombres.",
                    "Las cifras de este informe están equiparadas a jornada completa, pero la parcialidad feminizada reduce la retribución real percibida. Revisar la asignación de jornadas.",
                )
            )

    df = pd.DataFrame(alertas)
    if df.empty:
        return df
    orden_ambito = {"Global": 0, AMBITOS["puesto"]: 1, AMBITOS["grupo"]: 2, "Representación": 3, "Jornada": 4}
    orden_concepto = {"Retribución total": 0, "Salario base": 1, "Complementos": 2}
    df["_nivel"] = df["Nivel"].map(ORDEN_NIVEL)
    df["_ambito"] = df["Ámbito"].map(orden_ambito).fillna(9)
    df["_concepto"] = df["Indicador"].str.split("· ").str[-1].map(orden_concepto).fillna(0)
    df["_abs"] = -pd.to_numeric(df["Valor"], errors="coerce").abs().fillna(0)
    return df.sort_values(["_nivel", "_ambito", "_concepto", "_abs"]).drop(columns=["_nivel", "_ambito", "_concepto", "_abs"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------


def ejecutar_analisis(datos: pd.DataFrame, umbrales: Umbrales | None = None, avisos: list[str] | None = None) -> Resultado:
    umbrales = umbrales or Umbrales()
    conceptos_disponibles = ["total", "base"] + (["complementos"] if (datos["complementos"] != 0).any() else [])

    resumen = {
        "personas": int(len(datos)),
        "mujeres": int((datos["sexo"] == "Mujer").sum()),
        "hombres": int((datos["sexo"] == "Hombre").sum()),
        "conceptos": {c: brecha_global(datos, c, umbrales) for c in conceptos_disponibles},
        "brecha_total_sin_equiparar": brecha_pct(datos.loc[datos["sexo"] == "Mujer", "total"], datos.loc[datos["sexo"] == "Hombre", "total"]),
    }
    ajustada = brecha_ajustada(datos)

    tablas: dict[str, pd.DataFrame] = {}
    ambitos = ["puesto"] + [a for a in ("grupo", "departamento") if (datos[a] != "Sin informar").any()]
    for ambito in ambitos:
        for concepto in conceptos_disponibles:
            tablas[f"{ambito}|{concepto}"] = tabla_brechas(datos, ambito, concepto, umbrales)

    ambito_repres = "grupo" if "grupo" in ambitos else "puesto"
    repres = representacion(datos, ambito_repres, umbrales)
    if "departamento" in ambitos:
        repres = pd.concat([repres, representacion(datos, "departamento", umbrales).rename(columns={"Departamento": repres.columns[0]})], ignore_index=True)
    parc = parcialidad(datos)

    alertas = generar_alertas(resumen, ajustada, tablas, repres, parc, umbrales)
    estado = VERDE
    if not alertas.empty:
        estado = alertas["Nivel"].map(ORDEN_NIVEL).min()
        estado = {v: k for k, v in ORDEN_NIVEL.items()}[estado]
        if estado == GRIS:
            estado = VERDE

    return Resultado(resumen=resumen, ajustada=ajustada, tablas=tablas, representacion=repres, parcialidad=parc, alertas=alertas, estado_global=estado, avisos=list(avisos or []))
