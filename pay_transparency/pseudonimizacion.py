"""Pseudonimización de datos personales (art. 4.5 RGPD).

Se sustituye la identidad de cada persona por un pseudónimo derivado con
HMAC-SHA256 a partir de una clave secreta. Sin la clave (o sin la tabla de
correspondencia) no es posible volver a identificar a nadie. Los
identificadores directos se eliminan y la fecha de nacimiento se generaliza
a un tramo de edad.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
import secrets
import unicodedata

import pandas as pd

# Columnas que identifican directamente a la persona y se eliminan.
PATRONES_DIRECTOS = [
    r"\bnombre\b", r"apellido", r"\bdni\b", r"\bnif\b", r"\bnie\b", r"pasaporte",
    r"e-?mail", r"correo", r"tel[eé]fono", r"m[oó]vil", r"direcci[oó]n", r"domicilio",
    r"\bcalle\b", r"c[oó]digo\s*postal", r"\bcp\b", r"municipio", r"localidad", r"ciudad",
    r"\biban\b", r"cuenta\s*bancaria", r"\bnss\b", r"seguridad\s*social", r"n[uú]mero\s*de\s*afiliaci[oó]n",
]
PATRON_NACIMIENTO = r"nacimiento"
PATRON_ID = r"\bid\b|identificador|c[oó]digo\s*empleado|n[uú]m(ero)?\s*empleado"

TRAMOS_EDAD = [(0, 29, "Menos de 30"), (30, 39, "30-39"), (40, 49, "40-49"), (50, 59, "50-59"), (60, 200, "60 o más")]


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y sin espacios sobrantes, para comparar nombres de columna."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()


def detectar_columnas_personales(columnas: list[str]) -> dict[str, list[str]]:
    """Clasifica las columnas en identificadores directos, fecha de nacimiento e identificador interno."""
    directas, nacimiento, ids = [], [], []
    for col in columnas:
        n = normalizar(col)
        if re.search(PATRON_NACIMIENTO, n):
            nacimiento.append(col)
        elif any(re.search(p, n) for p in PATRONES_DIRECTOS):
            directas.append(col)
        elif re.search(PATRON_ID, n):
            ids.append(col)
    return {"directas": directas, "nacimiento": nacimiento, "ids": ids}


def generar_clave() -> str:
    return secrets.token_hex(16)


def pseudonimo(valor: str, clave: str, longitud: int = 10) -> str:
    digesto = hmac.new(clave.encode("utf-8"), str(valor).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"P-{digesto[:longitud].upper()}"


def tramo_edad(fecha_nacimiento, referencia: dt.date | None = None) -> str | None:
    if pd.isna(fecha_nacimiento):
        return None
    referencia = referencia or dt.date.today()
    fecha = pd.Timestamp(fecha_nacimiento).date()
    edad = referencia.year - fecha.year - ((referencia.month, referencia.day) < (fecha.month, fecha.day))
    for minimo, maximo, etiqueta in TRAMOS_EDAD:
        if minimo <= edad <= maximo:
            return etiqueta
    return None


def pseudonimizar(
    df: pd.DataFrame,
    clave: str | None = None,
    columnas_extra: list[str] | None = None,
    columna_id: str | None = None,
    referencia: dt.date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, str, dict]:
    """Devuelve (datos pseudonimizados, tabla de correspondencia, clave usada, detalle de columnas).

    La tabla de correspondencia debe guardarse aparte y con acceso restringido:
    es la "información adicional" que el RGPD exige mantener separada.
    """
    clave = clave or generar_clave()
    deteccion = detectar_columnas_personales(list(df.columns))
    directas = list(dict.fromkeys(deteccion["directas"] + (columnas_extra or [])))

    if columna_id is None:
        columna_id = deteccion["ids"][0] if deteccion["ids"] else None

    if columna_id is not None and df[columna_id].notna().all() and df[columna_id].is_unique:
        origen = df[columna_id].astype(str)
    else:
        # Sin identificador fiable se usa la posición de la fila; sigue siendo reproducible con la misma clave y el mismo fichero.
        origen = pd.Series([f"fila-{i}" for i in range(len(df))], index=df.index)

    pseudonimos = origen.map(lambda v: pseudonimo(v, clave))

    tabla = pd.DataFrame({"Pseudónimo": pseudonimos})
    for col in ([columna_id] if columna_id else []) + directas:
        if col in df.columns:
            tabla[col] = df[col].values

    salida = df.drop(columns=[c for c in directas + ([columna_id] if columna_id else []) if c in df.columns]).copy()
    for col in deteccion["nacimiento"]:
        salida[col] = pd.to_datetime(salida[col], errors="coerce").map(lambda f: tramo_edad(f, referencia))
        salida = salida.rename(columns={col: "Tramo de edad"})
    salida.insert(0, "Pseudónimo", pseudonimos.values)

    detalle = {
        "eliminadas": [c for c in directas if c in df.columns],
        "generalizadas": deteccion["nacimiento"],
        "columna_id": columna_id,
    }
    return salida, tabla, clave, detalle
