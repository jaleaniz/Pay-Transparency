"""Generación de una plantilla ficticia de 100 empleados en Excel.

Los datos son inventados. Se introducen a propósito algunas diferencias
retributivas entre sexos para que el análisis tenga algo que detectar:

- ``Operario/a``: las mujeres cobran alrededor de un 27 % menos (alerta roja).
- ``Comercial``: las mujeres cobran alrededor de un 10 % menos (alerta ámbar).
- ``Desarrollador/a``: mismo salario base, pero complementos menores para
  las mujeres (alerta ámbar en complementos).
- ``Key Account Manager``: los hombres cobran alrededor de un 6 % menos
  (alerta ámbar en sentido inverso).
- ``Director/a de Área``: una sola mujer de cuatro personas (alerta de
  representación).
- Resto de puestos: diferencias dentro del ruido estadístico (verde).
"""

from __future__ import annotations

import datetime as dt
import random
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

EMPRESA = "Industrias Ficticias Norte, S.L."
DOMINIO = "ifnorte-demo.es"

# (departamento, puesto, grupo profesional, nº mujeres, nº hombres)
PLANTILLA = [
    ("Dirección", "Director/a General", 1, 0, 1),
    ("Dirección", "Director/a de Área", 1, 1, 3),
    ("Finanzas", "Responsable de Finanzas", 2, 1, 0),
    ("Finanzas", "Contable", 3, 2, 2),
    ("Finanzas", "Técnico/a de Administración", 4, 4, 1),
    ("Recursos Humanos", "Responsable de RRHH", 2, 1, 0),
    ("Recursos Humanos", "Técnico/a de RRHH", 3, 2, 1),
    ("Recursos Humanos", "Administrativo/a de Personal", 4, 3, 0),
    ("Comercial", "Responsable Comercial", 2, 0, 1),
    ("Comercial", "Key Account Manager", 3, 2, 3),
    ("Comercial", "Comercial", 4, 5, 7),
    ("Operaciones", "Responsable de Operaciones", 2, 0, 1),
    ("Operaciones", "Jefe/a de Equipo", 3, 1, 3),
    ("Operaciones", "Operario/a", 5, 7, 13),
    ("Tecnología", "Responsable de IT", 2, 0, 1),
    ("Tecnología", "Desarrollador/a Senior", 3, 1, 4),
    ("Tecnología", "Desarrollador/a", 4, 3, 5),
    ("Tecnología", "Técnico/a de Soporte", 5, 2, 2),
    ("Marketing", "Responsable de Marketing", 2, 1, 0),
    ("Marketing", "Especialista en Marketing", 3, 3, 1),
    ("Marketing", "Diseñador/a", 4, 1, 1),
    ("Atención al Cliente", "Responsable de Atención al Cliente", 2, 1, 0),
    ("Atención al Cliente", "Agente de Atención al Cliente", 5, 7, 2),
]

# Banda salarial base anual (jornada completa) por grupo profesional.
BANDAS = {1: (78_000, 105_000), 2: (48_000, 62_000), 3: (34_000, 44_000), 4: (26_000, 32_000), 5: (19_000, 24_000)}
# Porcentaje de complementos sobre el salario base por grupo (mín, máx).
COMPLEMENTOS = {1: (0.15, 0.25), 2: (0.10, 0.16), 3: (0.05, 0.12), 4: (0.02, 0.08), 5: (0.0, 0.06)}

# Sesgos deliberados: factor aplicado a mujeres (o a hombres si es negativo el ajuste)
SESGO_BASE = {"Operario/a": {"Mujer": 0.78}, "Comercial": {"Mujer": 0.91}, "Key Account Manager": {"Hombre": 0.94}, "Director/a de Área": {"Mujer": 0.95}}
SESGO_COMPLEMENTOS = {"Desarrollador/a": {"Mujer": 0.35}, "Operario/a": {"Mujer": 0.5}}

NOMBRES_M = ["Lucía", "María", "Carmen", "Ana", "Laura", "Marta", "Elena", "Sara", "Paula", "Isabel", "Cristina", "Raquel", "Nuria", "Beatriz", "Patricia", "Silvia", "Rocío", "Alba", "Irene", "Eva", "Sonia", "Clara", "Andrea", "Noelia", "Teresa", "Pilar", "Mónica", "Inés", "Julia", "Lorena", "Natalia", "Verónica", "Ángela", "Celia", "Miriam", "Olga", "Esther", "Yolanda", "Gloria", "Aitana", "Nerea", "Ainhoa", "Leire", "Maite", "Amaya", "Blanca", "Rosa", "Dolores", "Susana", "Vanesa"]
NOMBRES_H = ["Javier", "Carlos", "David", "Daniel", "Alejandro", "Pablo", "Sergio", "Manuel", "Jorge", "Antonio", "Francisco", "Luis", "Miguel", "Rubén", "Álvaro", "Adrián", "Raúl", "Iván", "Óscar", "Marcos", "Diego", "Fernando", "Jesús", "Andrés", "Víctor", "Roberto", "Alberto", "Ignacio", "Gonzalo", "Jaime", "Hugo", "Mario", "Enrique", "Rafael", "Ramón", "Tomás", "Guillermo", "Eduardo", "Joaquín", "Emilio", "Iker", "Unai", "Mikel", "Asier", "Xavier", "Pedro", "Juan", "José", "Ángel", "Santiago"]
APELLIDOS = ["García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Gómez", "Martín", "Jiménez", "Ruiz", "Hernández", "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero", "Alonso", "Gutiérrez", "Navarro", "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Ramírez", "Serrano", "Blanco", "Molina", "Morales", "Suárez", "Ortega", "Delgado", "Castro", "Ortiz", "Rubio", "Marín", "Sanz", "Iglesias", "Medina", "Garrido", "Cortés", "Castillo", "Santos", "Lozano", "Guerrero", "Cano", "Prieto", "Méndez", "Etxeberria", "Agirre", "Zubizarreta", "Ferrer", "Puig", "Vidal", "Soler", "Roig"]
CALLES = ["Calle Mayor", "Avenida de la Constitución", "Calle Real", "Paseo de los Olmos", "Calle del Sol", "Avenida del Puerto", "Calle Nueva", "Plaza de España", "Calle de la Iglesia", "Camino Viejo", "Calle Luna", "Ronda Norte"]
MUNICIPIOS = [("Bilbao", "480"), ("Barakaldo", "489"), ("Getxo", "489"), ("Santander", "390"), ("Burgos", "090"), ("Vitoria-Gasteiz", "010"), ("Logroño", "260"), ("Donostia", "200")]

LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"


def _dni(rng: random.Random) -> str:
    numero = rng.randint(10_000_000, 99_999_999)
    return f"{numero}{LETRAS_DNI[numero % 23]}"


def _quitar_acentos(texto: str) -> str:
    tabla = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return texto.translate(tabla)


def generar_plantilla(semilla: int = 42, fecha_referencia: dt.date | None = None) -> pd.DataFrame:
    """Devuelve un DataFrame con 100 empleados ficticios."""
    rng = random.Random(semilla)
    hoy = fecha_referencia or dt.date.today()
    filas: list[dict] = []
    emails_usados: set[str] = set()
    dnis_usados: set[str] = set()

    for departamento, puesto, grupo, n_mujeres, n_hombres in PLANTILLA:
        for sexo, cantidad in (("Mujer", n_mujeres), ("Hombre", n_hombres)):
            for _ in range(cantidad):
                nombre = rng.choice(NOMBRES_M if sexo == "Mujer" else NOMBRES_H)
                apellidos = f"{rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"

                edad_min = {1: 38, 2: 32, 3: 27, 4: 23, 5: 20}[grupo]
                edad = rng.randint(edad_min, 63)
                fecha_nacimiento = hoy - dt.timedelta(days=int(edad * 365.25) + rng.randint(0, 364))
                antiguedad_max = min(edad - 19, 32)
                antiguedad = round(rng.uniform(0.3, antiguedad_max), 1)
                fecha_alta = hoy - dt.timedelta(days=int(antiguedad * 365.25))

                # Jornada: parcialidad algo más frecuente en mujeres (reflejo habitual de los registros reales)
                if grupo >= 3 and rng.random() < (0.18 if sexo == "Mujer" else 0.05):
                    jornada = rng.choice([50, 60, 80])
                else:
                    jornada = 100
                tipo_contrato = "Temporal" if (antiguedad < 2 and rng.random() < 0.5) else "Indefinido"

                # El salario recorre la banda del grupo sobre todo por antigüedad (como en un convenio),
                # con un pequeño margen individual. Así la brecha ajustada tiene algo que descontar.
                base_min, base_max = BANDAS[grupo]
                progresion = min(antiguedad / 25, 1.0) * rng.uniform(0.75, 1.0)
                base_jc = base_min + (base_max - base_min) * progresion
                base_jc *= SESGO_BASE.get(puesto, {}).get(sexo, 1.0)
                base_jc *= rng.uniform(0.98, 1.02)

                comp_min, comp_max = COMPLEMENTOS[grupo]
                complementos_jc = base_jc * rng.uniform(comp_min, comp_max)
                complementos_jc *= SESGO_COMPLEMENTOS.get(puesto, {}).get(sexo, 1.0)

                factor_jornada = jornada / 100
                salario_base = round(base_jc * factor_jornada, 2)
                complementos = round(complementos_jc * factor_jornada, 2)

                while True:
                    dni = _dni(rng)
                    if dni not in dnis_usados:
                        dnis_usados.add(dni)
                        break
                base_email = _quitar_acentos(f"{nombre}.{apellidos.split()[0]}").lower().replace(" ", "")
                email = f"{base_email}@{DOMINIO}"
                sufijo = 2
                while email in emails_usados:
                    email = f"{base_email}{sufijo}@{DOMINIO}"
                    sufijo += 1
                emails_usados.add(email)

                municipio, prefijo_cp = rng.choice(MUNICIPIOS)
                filas.append(
                    {
                        "Nombre": nombre,
                        "Apellidos": apellidos,
                        "DNI": dni,
                        "Sexo": sexo,
                        "Fecha de nacimiento": fecha_nacimiento,
                        "Email": email,
                        "Teléfono": f"6{rng.randint(10_000_000, 99_999_999)}",
                        "Dirección": f"{rng.choice(CALLES)}, {rng.randint(1, 120)}",
                        "Código postal": f"{prefijo_cp}{rng.randint(0, 99):02d}",
                        "Municipio": municipio,
                        "Departamento": departamento,
                        "Puesto": puesto,
                        "Grupo profesional": grupo,
                        "Fecha de alta": fecha_alta,
                        "Antigüedad (años)": antiguedad,
                        "Tipo de contrato": tipo_contrato,
                        "Jornada (%)": jornada,
                        "Salario base anual (€)": salario_base,
                        "Complementos anuales (€)": complementos,
                    }
                )

    rng.shuffle(filas)
    df = pd.DataFrame(filas)
    df.insert(0, "ID Empleado", [f"E{i:03d}" for i in range(1, len(df) + 1)])
    df["Retribución total anual (€)"] = (df["Salario base anual (€)"] + df["Complementos anuales (€)"]).round(2)
    return df


def _ajustar_hoja(ws, df: pd.DataFrame) -> None:
    cabecera_fill = PatternFill("solid", fgColor="2F2F2F")
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF", name="Helvetica", size=10)
        celda.fill = cabecera_fill
        celda.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    for idx, columna in enumerate(df.columns, start=1):
        ancho = max(len(str(columna)), *(len(str(v)) for v in df[columna].head(100))) + 2
        ws.column_dimensions[get_column_letter(idx)].width = min(ancho, 40)
        if "(€)" in str(columna):
            for celda in ws[get_column_letter(idx)][1:]:
                celda.number_format = "#,##0.00 €"
        if "Fecha" in str(columna):
            for celda in ws[get_column_letter(idx)][1:]:
                celda.number_format = "DD/MM/YYYY"


def exportar_excel(df: pd.DataFrame, ruta: str | Path | None = None) -> bytes:
    """Escribe la plantilla en un Excel con formato. Devuelve los bytes y, si se indica ruta, lo guarda."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Empleados", index=False)
        _ajustar_hoja(writer.sheets["Empleados"], df)

        leyenda = pd.DataFrame(
            {
                "Campo": list(df.columns),
                "Descripción": [
                    "Identificador interno del empleado",
                    "Nombre (dato personal, ficticio)",
                    "Apellidos (dato personal, ficticio)",
                    "DNI (dato personal, ficticio con letra válida)",
                    "Sexo registrado a efectos del registro retributivo",
                    "Fecha de nacimiento (dato personal)",
                    "Correo corporativo (dato personal)",
                    "Teléfono (dato personal)",
                    "Domicilio (dato personal)",
                    "Código postal (dato personal)",
                    "Municipio de residencia (dato personal)",
                    "Departamento",
                    "Puesto de trabajo (criterio de 'igual trabajo')",
                    "Grupo profesional según convenio (criterio de 'trabajo de igual valor')",
                    "Fecha de incorporación",
                    "Antigüedad en años a fecha de generación",
                    "Indefinido o temporal",
                    "Porcentaje de jornada sobre la jornada completa",
                    "Salario base anual bruto efectivamente percibido (según jornada)",
                    "Complementos salariales anuales percibidos (según jornada)",
                    "Suma de salario base y complementos",
                ],
            }
        )
        leyenda.to_excel(writer, sheet_name="Leyenda", index=False)
        _ajustar_hoja(writer.sheets["Leyenda"], leyenda)
        ws = writer.sheets["Leyenda"]
        ws.cell(row=len(leyenda) + 3, column=1, value=f"Empresa ficticia: {EMPRESA}. Todos los datos son inventados.")
        ws.cell(row=len(leyenda) + 4, column=1, value="Elaborado por otraforma")

    datos = buffer.getvalue()
    if ruta is not None:
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        Path(ruta).write_bytes(datos)
    return datos


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Genera el Excel de empleados ficticios.")
    parser.add_argument("--salida", default="data/empleados_demo.xlsx")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()
    plantilla = generar_plantilla(args.semilla)
    exportar_excel(plantilla, args.salida)
    print(f"Generado {args.salida} con {len(plantilla)} empleados.")
