import datetime as dt
from io import BytesIO

import pandas as pd
import pytest

from pay_transparency.analisis import (
    AMBAR,
    GRIS,
    ROJO,
    VERDE,
    Umbrales,
    brecha_pct,
    detectar_mapeo,
    ejecutar_analisis,
    preparar_datos,
    tabla_brechas,
)
from pay_transparency.generador import exportar_excel, generar_plantilla
from pay_transparency.informe import exportar_informe
from pay_transparency.pseudonimizacion import detectar_columnas_personales, pseudonimizar, tramo_edad


@pytest.fixture(scope="module")
def plantilla():
    return generar_plantilla(semilla=42, fecha_referencia=dt.date(2026, 11, 26))


def test_generador_100_empleados(plantilla):
    assert len(plantilla) == 100
    assert plantilla["ID Empleado"].is_unique
    assert plantilla["DNI"].is_unique
    assert set(plantilla["Sexo"]) == {"Mujer", "Hombre"}
    assert (plantilla["Retribución total anual (€)"] == (plantilla["Salario base anual (€)"] + plantilla["Complementos anuales (€)"]).round(2)).all()


def test_generador_reproducible():
    a = generar_plantilla(7, dt.date(2026, 1, 1))
    b = generar_plantilla(7, dt.date(2026, 1, 1))
    pd.testing.assert_frame_equal(a, b)


def test_exportar_excel_legible(tmp_path, plantilla):
    ruta = tmp_path / "demo.xlsx"
    exportar_excel(plantilla, ruta)
    leido = pd.read_excel(ruta, sheet_name="Empleados")
    assert len(leido) == 100
    assert "Leyenda" in pd.ExcelFile(ruta).sheet_names


def test_deteccion_columnas_personales(plantilla):
    d = detectar_columnas_personales(list(plantilla.columns))
    for col in ("Nombre", "Apellidos", "DNI", "Email", "Teléfono", "Dirección", "Municipio"):
        assert col in d["directas"]
    assert d["nacimiento"] == ["Fecha de nacimiento"]
    assert d["ids"] == ["ID Empleado"]
    assert "Sexo" not in d["directas"] and "Puesto" not in d["directas"]


def test_pseudonimizacion_elimina_identificadores(plantilla):
    pseudo, tabla, clave, detalle = pseudonimizar(plantilla, clave="clave-de-prueba")
    for col in ("Nombre", "Apellidos", "DNI", "Email", "Teléfono", "Dirección", "ID Empleado", "Fecha de nacimiento"):
        assert col not in pseudo.columns
    assert "Pseudónimo" in pseudo.columns and pseudo["Pseudónimo"].is_unique
    assert "Tramo de edad" in pseudo.columns
    assert len(tabla) == 100 and "DNI" in tabla.columns
    # Determinista con la misma clave, distinto con otra
    pseudo2, *_ = pseudonimizar(plantilla, clave="clave-de-prueba")
    pseudo3, *_ = pseudonimizar(plantilla, clave="otra-clave")
    assert pseudo["Pseudónimo"].tolist() == pseudo2["Pseudónimo"].tolist()
    assert pseudo["Pseudónimo"].tolist() != pseudo3["Pseudónimo"].tolist()


def test_tramo_edad():
    ref = dt.date(2026, 6, 1)
    assert tramo_edad(dt.date(2000, 6, 2), ref) == "Menos de 30"
    assert tramo_edad(dt.date(1996, 6, 1), ref) == "30-39"
    assert tramo_edad(dt.date(1960, 1, 1), ref) == "60 o más"


def test_brecha_pct_signo():
    m = pd.Series([80.0, 80.0])
    h = pd.Series([100.0, 100.0])
    assert brecha_pct(m, h) == pytest.approx(20.0)
    assert brecha_pct(h, m) == pytest.approx(-25.0)
    assert brecha_pct(pd.Series([], dtype=float), h) is None


def _datos(filas):
    df = pd.DataFrame(filas, columns=["Sexo", "Puesto", "Salario base", "Jornada"])
    mapeo = detectar_mapeo(list(df.columns))
    datos, _ = preparar_datos(df, mapeo)
    return datos


def test_semaforo_por_umbral():
    u = Umbrales(verde=5, rojo=25, n_minimo=3)
    filas = []
    filas += [("Mujer", "Verde", 100, 100)] * 3 + [("Hombre", "Verde", 102, 100)] * 3
    filas += [("Mujer", "Ambar", 90, 100)] * 3 + [("Hombre", "Ambar", 100, 100)] * 3
    filas += [("Mujer", "Rojo", 70, 100)] * 3 + [("Hombre", "Rojo", 100, 100)] * 3
    filas += [("Mujer", "Pequeno", 95, 100)] * 2 + [("Hombre", "Pequeno", 100, 100)] * 3
    filas += [("Mujer", "Solo", 100, 100)] * 4
    tabla = tabla_brechas(_datos(filas), "puesto", "base", u).set_index("Puesto")
    assert tabla.loc["Verde", "Semáforo"] == VERDE
    assert tabla.loc["Ambar", "Semáforo"] == AMBAR
    assert tabla.loc["Rojo", "Semáforo"] == ROJO
    assert tabla.loc["Pequeno", "Semáforo"] == GRIS
    assert tabla.loc["Solo", "Semáforo"] == GRIS
    assert tabla.loc["Rojo", "Brecha media (%)"] == pytest.approx(30.0)


def test_equiparacion_a_jornada_completa():
    # Mismo salario por hora: a media jornada se cobra la mitad, pero la brecha equiparada es cero.
    filas = [("Mujer", "P", 50, 50)] * 3 + [("Hombre", "P", 100, 100)] * 3
    tabla = tabla_brechas(_datos(filas), "puesto", "base")
    assert tabla.loc[0, "Brecha media (%)"] == pytest.approx(0.0)
    assert tabla.loc[0, "Semáforo"] == VERDE


def test_sexo_normalizado_y_filas_excluidas():
    df = pd.DataFrame({"Sexo": ["F", "M", "H", "V", "X"], "Puesto": ["a"] * 5, "Salario base": [1, 2, 3, 4, 5]})
    datos, avisos = preparar_datos(df, detectar_mapeo(list(df.columns)))
    assert datos["sexo"].tolist() == ["Mujer", "Mujer", "Hombre", "Hombre"]
    assert any("sin sexo" in a for a in avisos)


def test_faltan_columnas_obligatorias():
    df = pd.DataFrame({"Puesto": ["a"], "Salario base": [1]})
    with pytest.raises(ValueError, match="sexo"):
        preparar_datos(df, detectar_mapeo(list(df.columns)))


def test_analisis_completo_detecta_sesgos(plantilla):
    pseudo, *_ = pseudonimizar(plantilla, clave="k")
    datos, avisos = preparar_datos(pseudo, detectar_mapeo(list(pseudo.columns)), referencia=dt.date(2026, 11, 26))
    resultado = ejecutar_analisis(datos, Umbrales(), avisos)
    puestos = resultado.tablas["puesto|total"].set_index("Puesto")
    assert puestos.loc["Operario/a", "Semáforo"] == ROJO
    assert puestos.loc["Comercial", "Semáforo"] == AMBAR
    assert resultado.estado_global == ROJO
    assert resultado.ajustada["disponible"] and resultado.ajustada["brecha_ajustada_pct"] > 0
    assert not resultado.alertas.empty
    assert resultado.alertas["Nivel"].iloc[0] == ROJO
    # El departamento no genera alertas
    assert not resultado.alertas["Ámbito"].eq("Departamento").any()
    informe = exportar_informe(resultado, pseudo, Umbrales(), "Demo")
    hojas = pd.ExcelFile(BytesIO(informe)).sheet_names
    assert {"Resumen", "Alertas", "Representación", "Datos pseudonimizados"} <= set(hojas)
