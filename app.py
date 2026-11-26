"""Aplicación Streamlit de transparencia retributiva.

Ejecutar con:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
from io import BytesIO

import altair as alt
import pandas as pd
import streamlit as st

from pay_transparency.analisis import (
    AMBAR,
    AMBITOS,
    CAMPOS_OBLIGATORIOS,
    COLORES,
    CONCEPTOS,
    GRIS,
    ICONOS,
    PATRONES_CAMPOS,
    ROJO,
    VERDE,
    Umbrales,
    detectar_mapeo,
    ejecutar_analisis,
    preparar_datos,
)
from pay_transparency.generador import EMPRESA, exportar_excel, generar_plantilla
from pay_transparency.informe import exportar_informe
from pay_transparency.pseudonimizacion import detectar_columnas_personales, pseudonimizar

st.set_page_config(page_title="Transparencia retributiva", page_icon="⚖️", layout="wide")

ETIQUETAS_CAMPOS = {
    "sexo": "Sexo (obligatorio)",
    "puesto": "Puesto (obligatorio)",
    "base": "Salario base anual (obligatorio)",
    "complementos": "Complementos anuales",
    "total": "Retribución total anual",
    "jornada": "Jornada (%)",
    "grupo": "Grupo profesional / nivel",
    "departamento": "Departamento",
    "antiguedad": "Antigüedad (años)",
    "fecha_alta": "Fecha de alta",
}

st.markdown(
    """
    <style>
    .semaforo {display:inline-block; padding:0.35rem 0.9rem; border-radius:999px; color:white; font-weight:700; letter-spacing:0.03em;}
    .pie {color:#777; font-size:0.85rem; margin-top:3rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def badge(nivel: str, texto: str | None = None) -> str:
    return f'<span class="semaforo" style="background:{COLORES[nivel]}">{ICONOS[nivel]} {texto or nivel}</span>'


def estilo_semaforo(df: pd.DataFrame, columna: str = "Semáforo"):
    def color(valor):
        c = COLORES.get(str(valor))
        return f"background-color:{c}; color:white; font-weight:700; text-align:center" if c else ""

    formato = {c: "{:,.1f}" for c in df.columns if "(%)" in c} | {c: "{:,.2f} €" for c in df.columns if "(€)" in c}
    return df.style.map(color, subset=[columna]).format(formato, na_rep="—")


def grafico_brechas(tabla: pd.DataFrame, columna_categoria: str, titulo: str, umbrales: Umbrales):
    datos = tabla.dropna(subset=["Brecha media (%)"]).copy()
    if datos.empty:
        st.info("No hay grupos comparables para representar.")
        return
    datos["Etiqueta"] = datos[columna_categoria].astype(str) + "  (" + datos["Mujeres (n)"].astype(str) + "M / " + datos["Hombres (n)"].astype(str) + "H)"
    barras = (
        alt.Chart(datos)
        .mark_bar()
        .encode(
            x=alt.X("Brecha media (%):Q", title="Brecha media (%) · positiva = las mujeres cobran menos"),
            y=alt.Y("Etiqueta:N", sort="-x", title=None, axis=alt.Axis(labelLimit=320, labelOverlap=False)),
            color=alt.Color("Semáforo:N", scale=alt.Scale(domain=list(COLORES), range=list(COLORES.values())), legend=alt.Legend(title="Semáforo")),
            tooltip=[columna_categoria, "Mujeres (n)", "Hombres (n)", "Media mujeres (€)", "Media hombres (€)", "Brecha media (%)", "Brecha mediana (%)", "Motivo"],
        )
    )
    reglas = alt.Chart(pd.DataFrame({"x": [umbrales.verde, -umbrales.verde, umbrales.rojo, -umbrales.rojo], "tipo": ["5 %", "5 %", "25 %", "25 %"]})).mark_rule(strokeDash=[4, 4], color="#555").encode(x="x:Q")
    st.altair_chart((barras + reglas).properties(title=titulo, height=max(220, 28 * len(datos))), use_container_width=True)


# ---------------------------------------------------------------------------
# Barra lateral: parámetros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Parámetros")
    nombre_empresa = st.text_input("Nombre de la empresa (para el informe)", value="")
    st.subheader("Umbrales del semáforo")
    verde = st.slider("Verde: brecha inferior a (%)", 1.0, 15.0, 5.0, 0.5, help="Referencia: 5 % de la Directiva (UE) 2023/970.")
    rojo = st.slider("Rojo: brecha igual o superior a (%)", 10.0, 50.0, 25.0, 1.0, help="Referencia: 25 % del art. 28.3 del Estatuto de los Trabajadores.")
    n_minimo = st.number_input("Mínimo de personas de cada sexo para comparar", 1, 20, 3)
    repres_min = st.slider("Aviso de segregación si un sexo está por debajo de (%)", 5.0, 45.0, 25.0, 5.0)
    materialidad = st.slider("Materialidad de un concepto (% de la retribución total)", 0.0, 5.0, 1.0, 0.5, help="Una diferencia en un concepto (p. ej. complementos) menor que este porcentaje de la retribución total se considera inmaterial.")
    umbrales = Umbrales(verde=verde, rojo=max(rojo, verde + 1), n_minimo=int(n_minimo), representacion_min=repres_min, materialidad=materialidad)
    st.caption("Convención: brecha = (hombres − mujeres) / hombres. Retribuciones equiparadas a jornada completa.")

st.title("⚖️ Transparencia retributiva")
st.write("Genera una plantilla de prueba, pseudonimiza los datos personales y analiza las brechas salariales entre sexos con alertas tipo semáforo.")

# ---------------------------------------------------------------------------
# Paso 1: generar Excel de prueba
# ---------------------------------------------------------------------------
st.header("1 · Generar un Excel de prueba")
with st.expander("Crear una plantilla ficticia de 100 empleados", expanded="df_origen" not in st.session_state):
    col_a, col_b = st.columns([1, 3])
    semilla = col_a.number_input("Semilla aleatoria", 0, 9999, 42)
    col_b.caption(f"Empresa ficticia: **{EMPRESA}**. Incluye nombre, DNI, contacto, sexo, departamento, puesto, grupo profesional, antigüedad, jornada y retribución. Lleva sesgos deliberados para que el análisis tenga algo que encontrar.")
    if st.button("Generar Excel de prueba", type="primary"):
        plantilla = generar_plantilla(int(semilla))
        st.session_state["excel_demo"] = exportar_excel(plantilla)
        st.session_state["df_origen"] = plantilla
        st.session_state["nombre_fichero"] = f"empleados_demo_{semilla}.xlsx"
        for clave in ("pseudo", "tabla", "resultado"):
            st.session_state.pop(clave, None)
    if "excel_demo" in st.session_state:
        st.download_button("Descargar Excel de prueba", st.session_state["excel_demo"], st.session_state["nombre_fichero"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.dataframe(st.session_state["df_origen"].head(8), use_container_width=True)
        st.success("Plantilla generada y cargada en el paso 2. Puedes descargarla o seguir directamente.")

# ---------------------------------------------------------------------------
# Paso 2: adjuntar Excel
# ---------------------------------------------------------------------------
st.header("2 · Adjuntar el Excel con la plantilla")
fichero = st.file_uploader("Excel (.xlsx) o CSV con una fila por persona", type=["xlsx", "xls", "csv"])
if fichero is not None:
    try:
        if fichero.name.lower().endswith(".csv"):
            df_subido = pd.read_csv(fichero, sep=None, engine="python")
        else:
            hojas = pd.ExcelFile(fichero).sheet_names
            hoja = st.selectbox("Hoja", hojas, index=0) if len(hojas) > 1 else hojas[0]
            df_subido = pd.read_excel(fichero, sheet_name=hoja)
        if st.session_state.get("nombre_fichero") != fichero.name or "df_origen" not in st.session_state:
            for clave in ("pseudo", "tabla", "resultado"):
                st.session_state.pop(clave, None)
        st.session_state["df_origen"] = df_subido
        st.session_state["nombre_fichero"] = fichero.name
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se ha podido leer el fichero: {exc}")

if "df_origen" not in st.session_state:
    st.info("Genera el Excel de prueba o adjunta el tuyo para continuar.")
    st.stop()

df_origen: pd.DataFrame = st.session_state["df_origen"]
st.caption(f"Fichero cargado: **{st.session_state['nombre_fichero']}** · {len(df_origen)} filas · {len(df_origen.columns)} columnas")
with st.expander("Ver datos originales (contienen datos personales)"):
    st.dataframe(df_origen, use_container_width=True)

# ---------------------------------------------------------------------------
# Paso 3: pseudonimizar
# ---------------------------------------------------------------------------
st.header("3 · Pseudonimizar los datos personales")
deteccion = detectar_columnas_personales(list(df_origen.columns))
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Columnas detectadas como identificadores directos** (se eliminan):")
    st.write(", ".join(deteccion["directas"]) or "ninguna")
    st.markdown("**Fecha de nacimiento** (se convierte en tramo de edad):")
    st.write(", ".join(deteccion["nacimiento"]) or "ninguna")
with col2:
    restantes = [c for c in df_origen.columns if c not in deteccion["directas"] and c not in deteccion["nacimiento"]]
    extra = st.multiselect("Otras columnas a eliminar", restantes, help="Añade aquí cualquier columna que también identifique a la persona.")
    opciones_id = ["(ninguna: usar posición de fila)"] + list(df_origen.columns)
    sugerida = deteccion["ids"][0] if deteccion["ids"] else None
    columna_id = st.selectbox("Columna identificadora para derivar el pseudónimo", opciones_id, index=opciones_id.index(sugerida) if sugerida else 0)
    clave_usuario = st.text_input("Clave secreta (opcional; si se deja vacía se genera una)", type="password", help="Con la misma clave y el mismo identificador, el pseudónimo se repite entre ficheros. Guárdala aparte de los datos.")

if st.button("Pseudonimizar", type="primary"):
    pseudo, tabla, clave, detalle = pseudonimizar(
        df_origen,
        clave=clave_usuario or None,
        columnas_extra=extra,
        columna_id=None if columna_id.startswith("(") else columna_id,
    )
    st.session_state.update({"pseudo": pseudo, "tabla": tabla, "clave": clave, "detalle": detalle})
    st.session_state.pop("resultado", None)

if "pseudo" not in st.session_state:
    st.info("Pulsa «Pseudonimizar» para continuar. El análisis solo se hace sobre datos pseudonimizados.")
    st.stop()

pseudo: pd.DataFrame = st.session_state["pseudo"]
detalle = st.session_state["detalle"]
st.success(f"Eliminadas {len(detalle['eliminadas'])} columnas identificativas ({', '.join(detalle['eliminadas']) or 'ninguna'}); generalizadas: {', '.join(detalle['generalizadas']) or 'ninguna'}.")
st.dataframe(pseudo.head(10), use_container_width=True)


def _a_excel(df: pd.DataFrame, hoja: str) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=hoja, index=False)
    return buffer.getvalue()


c1, c2, c3 = st.columns(3)
c1.download_button("Descargar datos pseudonimizados", _a_excel(pseudo, "Pseudonimizado"), "empleados_pseudonimizados.xlsx")
c2.download_button("Descargar tabla de correspondencia (acceso restringido)", _a_excel(st.session_state["tabla"], "Correspondencia"), "tabla_correspondencia_CONFIDENCIAL.xlsx", help="Permite volver a identificar a las personas. Debe guardarse separada de los datos y con acceso restringido (art. 4.5 RGPD).")
with c3:
    st.text_input("Clave usada (guárdala aparte)", st.session_state["clave"], disabled=True)

# ---------------------------------------------------------------------------
# Paso 4: análisis
# ---------------------------------------------------------------------------
st.header("4 · Analizar salarios, puestos y sexo")
mapeo_sugerido = detectar_mapeo(list(pseudo.columns))
with st.expander("Correspondencia de columnas", expanded=any(not mapeo_sugerido.get(c) for c in CAMPOS_OBLIGATORIOS)):
    st.caption("La herramienta propone una correspondencia automática. Corrígela si hace falta.")
    opciones = ["(no disponible)"] + list(pseudo.columns)
    mapeo: dict[str, str | None] = {}
    columnas_ui = st.columns(2)
    for i, campo in enumerate(PATRONES_CAMPOS):
        sugerido = mapeo_sugerido.get(campo)
        elegido = columnas_ui[i % 2].selectbox(ETIQUETAS_CAMPOS[campo], opciones, index=opciones.index(sugerido) if sugerido in opciones else 0, key=f"map_{campo}")
        mapeo[campo] = None if elegido.startswith("(") else elegido

if st.button("Analizar", type="primary"):
    try:
        datos, avisos = preparar_datos(pseudo, mapeo)
        st.session_state["resultado"] = ejecutar_analisis(datos, umbrales, avisos)
        st.session_state["datos_std"] = datos
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

if "resultado" not in st.session_state:
    st.info("Pulsa «Analizar» para calcular las brechas.")
    st.stop()

# Recalcular si han cambiado los umbrales en la barra lateral
resultado = ejecutar_analisis(st.session_state["datos_std"], umbrales, st.session_state["resultado"].avisos)
resumen = resultado.resumen

for aviso in resultado.avisos:
    st.warning(aviso)

st.markdown(f"### Estado global: {badge(resultado.estado_global)}", unsafe_allow_html=True)
total = resumen["conceptos"]["total"]
alertas = resultado.alertas
n_rojas = int((alertas["Nivel"] == ROJO).sum()) if not alertas.empty else 0
n_ambar = int((alertas["Nivel"] == AMBAR).sum()) if not alertas.empty else 0
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Personas", resumen["personas"])
k1.caption(f"{resumen['mujeres']} mujeres · {resumen['hombres']} hombres")
k2.metric("Brecha media total", f"{total['Brecha media (%)']:.1f} %" if total["Brecha media (%)"] is not None else "—")
k2.markdown(badge(total["Semáforo"]), unsafe_allow_html=True)
k3.metric("Brecha mediana total", f"{total['Brecha mediana (%)']:.1f} %" if total["Brecha mediana (%)"] is not None else "—")
k3.caption("Equiparada a jornada completa")
if resultado.ajustada.get("disponible"):
    ic = resultado.ajustada["ic95"]
    k4.metric("Brecha ajustada", f"{resultado.ajustada['brecha_ajustada_pct']:.1f} %", help="A igual puesto y antigüedad. Regresión sobre el logaritmo de la retribución total.")
    k4.caption(f"IC 95 %: {ic[0]} a {ic[1]} · {'significativa' if resultado.ajustada['significativa'] else 'no significativa'}" if ic[0] is not None else "")
else:
    k4.metric("Brecha ajustada", "n/d")
k5.metric("Alertas", f"{n_rojas} / {n_ambar}")
k5.caption(f"{ICONOS[ROJO]} rojas / {ICONOS[AMBAR]} ámbar")

st.caption(
    "Media mujeres: {m:,.0f} € · Media hombres: {h:,.0f} € (equiparado a jornada completa). "
    "Sin equiparar a jornada completa la brecha media total sería del {s:.1f} %.".format(
        m=total["Media mujeres (€)"] or 0, h=total["Media hombres (€)"] or 0, s=resumen["brecha_total_sin_equiparar"] or 0
    )
)

# ---------------------------------------------------------------------------
# Paso 5: alertas y tablas
# ---------------------------------------------------------------------------
st.header("5 · Alertas tipo semáforo")
pestanas = st.tabs(["🚨 Alertas", "Por puesto", "Por grupo profesional", "Por departamento", "Representación y jornada", "Marco normativo"])

with pestanas[0]:
    if alertas.empty:
        st.success("Sin alertas: todas las comparaciones están en verde.")
    else:
        filtro = st.multiselect("Mostrar niveles", [ROJO, AMBAR, VERDE], default=[ROJO, AMBAR])
        visibles = alertas[alertas["Nivel"].isin(filtro)]
        for _, fila in visibles.iterrows():
            with st.container(border=True):
                st.markdown(f"{badge(fila['Nivel'])} &nbsp; **{fila['Ámbito']} · {fila['Elemento']}** &nbsp;·&nbsp; {fila['Indicador']}: **{fila['Valor']:+.1f}**", unsafe_allow_html=True)
                st.write(fila["Mensaje"])
                st.caption(f"Recomendación: {fila['Recomendación']}")
        st.dataframe(estilo_semaforo(visibles, "Nivel"), use_container_width=True, hide_index=True)

for indice, ambito in ((1, "puesto"), (2, "grupo"), (3, "departamento")):
    with pestanas[indice]:
        if f"{ambito}|total" not in resultado.tablas:
            st.info(f"No hay columna de {ambito} en el fichero.")
            continue
        concepto = st.radio("Concepto", [c for c in CONCEPTOS if f"{ambito}|{c}" in resultado.tablas], format_func=CONCEPTOS.get, horizontal=True, key=f"concepto_{ambito}")
        tabla = resultado.tablas[f"{ambito}|{concepto}"]
        grafico_brechas(tabla, tabla.columns[0], f"{AMBITOS[ambito]} · {CONCEPTOS[concepto]}", umbrales)
        st.dataframe(estilo_semaforo(tabla), use_container_width=True, hide_index=True)
        if ambito == "departamento":
            st.caption("El departamento agrupa puestos distintos, así que no es un comparador legal de 'igual trabajo'. Se muestra a título informativo y no genera alertas.")

with pestanas[4]:
    st.subheader("Representación por sexo")
    st.dataframe(estilo_semaforo(resultado.representacion), use_container_width=True, hide_index=True)
    st.subheader("Jornada")
    st.dataframe(resultado.parcialidad, use_container_width=True, hide_index=True)

with pestanas[5]:
    st.markdown(
        f"""
**Principio aplicado.** Igual retribución por trabajo de igual valor (art. 28 del Estatuto de los Trabajadores y Ley Orgánica 3/2007). Se compara por **puesto** (igual trabajo) y por **grupo profesional** (trabajo de igual valor), por concepto retributivo y equiparando a jornada completa, como exige el **Real Decreto 902/2020** para el registro retributivo.

**Semáforo.**
- {ICONOS[VERDE]} **Verde**: brecha media inferior al {umbrales.verde:g} %. La Directiva (UE) 2023/970 fija el 5 % como umbral a partir del cual, sin justificación objetiva, procede una evaluación retributiva conjunta.
- {ICONOS[AMBAR]} **Ámbar**: brecha entre el {umbrales.verde:g} % y el {umbrales.rojo:g} %, brecha alta con muestra pequeña, o segregación por sexo en un ámbito.
- {ICONOS[ROJO]} **Rojo**: brecha media igual o superior al {umbrales.rojo:g} %. El art. 28.3 ET obliga a justificar en el registro retributivo que la diferencia no obedece a motivos relacionados con el sexo.
- {ICONOS[GRIS]} **Gris**: no concluyente, porque hay menos de {umbrales.n_minimo} personas de alguno de los sexos o solo un sexo en el grupo.

**Brecha ajustada.** Regresión del logaritmo de la retribución total sobre el sexo, el puesto y la antigüedad. Indica cuánto menos cobran las mujeres a igual puesto y antigüedad; es la cifra más cercana al principio de igual trabajo, igual salario.

**Limitaciones.** Herramienta de apoyo. No sustituye al registro retributivo (art. 5 RD 902/2020) ni a la auditoría retributiva (art. 7) ni valora los puestos conforme al art. 4 RD 902/2020. Los grupos pequeños se marcan en gris porque el resultado no es fiable y porque publicar sus cifras podría permitir identificar a personas concretas.
        """
    )

st.header("6 · Descargar el informe")
informe = exportar_informe(resultado, pseudo, umbrales, nombre_empresa)
st.download_button("Descargar informe completo (Excel)", informe, f"informe_brecha_retributiva_{dt.date.today():%Y%m%d}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
st.markdown('<p class="pie">Elaborado por otraforma · Herramienta de apoyo; no constituye asesoramiento jurídico.</p>', unsafe_allow_html=True)
