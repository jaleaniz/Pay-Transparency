# Pay-Transparency

Herramienta de transparencia retributiva. Hace cuatro cosas, en este orden:

1. **Genera un Excel de prueba** con una empresa ficticia de 100 empleados: nombre, DNI, contacto, fecha de nacimiento, sexo, departamento, puesto, grupo profesional, antigüedad, jornada, salario base y complementos. Los datos son inventados e incluyen sesgos deliberados para que el análisis tenga algo que detectar.
2. **Pseudonimiza** el Excel que se adjunte: elimina los identificadores directos (nombre, DNI, email, teléfono, domicilio…), convierte la fecha de nacimiento en tramo de edad y sustituye la identidad por un pseudónimo derivado con HMAC-SHA256 y una clave secreta. La tabla de correspondencia se descarga aparte, como exige el art. 4.5 RGPD.
3. **Analiza** salarios, puestos y sexo: brecha media y mediana global, por puesto (igual trabajo), por grupo profesional (trabajo de igual valor) y por departamento, desglosada por salario base, complementos y total, equiparada a jornada completa. Calcula además una brecha ajustada a igual puesto y antigüedad, la representación por sexo y la parcialidad.
4. **Emite alertas tipo semáforo** y un informe Excel descargable.

## Semáforo

| Nivel | Criterio por defecto | Referencia |
|---|---|---|
| 🟢 Verde | Brecha media inferior al 5 % | Directiva (UE) 2023/970, umbral de evaluación conjunta |
| 🟡 Ámbar | Brecha entre el 5 % y el 25 %; brecha alta con muestra pequeña; segregación por sexo | — |
| 🔴 Rojo | Brecha media igual o superior al 25 % | Art. 28.3 ET: obligación de justificación |
| ⚪ Gris | Menos de 3 personas de algún sexo, o un solo sexo en el grupo | No concluyente |

Convención: brecha = (hombres − mujeres) / hombres. Positiva: las mujeres cobran menos. Los umbrales se ajustan en la barra lateral.

## Uso

```bash
pip install -r requirements.txt
streamlit run app.py
```

Generar solo el Excel de prueba desde la terminal:

```bash
python -m pay_transparency.generador --salida data/empleados_demo.xlsx --semilla 42
```

Ejecutar las pruebas:

```bash
pytest
```

## Estructura

- `app.py`: interfaz Streamlit en seis pasos.
- `pay_transparency/generador.py`: plantilla ficticia y exportación a Excel.
- `pay_transparency/pseudonimizacion.py`: detección de columnas personales y pseudonimización.
- `pay_transparency/analisis.py`: brechas, semáforo, brecha ajustada, representación y alertas.
- `pay_transparency/informe.py`: informe Excel con formato.
- `data/empleados_demo.xlsx`: Excel de prueba ya generado.

## Qué columnas necesita un Excel propio

Obligatorias: sexo, puesto y salario base anual. Opcionales, pero recomendables: complementos, retribución total, jornada (%), grupo profesional, departamento y antigüedad o fecha de alta. La app propone la correspondencia de columnas y permite corregirla.

## Aviso

Herramienta de apoyo. No sustituye al registro retributivo ni a la auditoría retributiva del Real Decreto 902/2020, ni constituye asesoramiento jurídico. Los ficheros con datos reales y las tablas de correspondencia no deben subirse al repositorio.

Elaborado por otraforma.
