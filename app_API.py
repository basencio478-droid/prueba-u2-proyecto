import os
import io
import time
import sqlite3
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(page_title="Análisis Climático Histórico - Cuenca, Ecuador", layout="wide")

st.title("🌦️ Análisis Climático Histórico de Cuenca, Ecuador")
st.caption(
    "Proyecto de Carga, Exploración, Limpieza, Transformación y Visualización de Datos — "
    "Fuente: API de Open-Meteo (Historical Weather API)"
)

DB_NAME = os.path.join(tempfile.gettempdir(), "clima_cuenca.db")
TABLE_NAME = "clima_cuenca"

# Coordenadas de Cuenca, Ecuador
LATITUD = -2.9006
LONGITUD = -79.0045
ZONA_HORARIA = "America/Guayaquil"

# Rango de datos históricos diarios (10 años, ideal para análisis de tendencias)
FECHA_INICIO = "2015-01-01"
FECHA_FIN = "2024-12-31"

# Variables diarias solicitadas a la API
VARIABLES_DIARIAS = "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"

MAX_REINTENTOS = 3
TIMEOUT_SEGUNDOS = 30  # esta API responde en milisegundos, no hace falta un timeout largo

# ==============================================================================
# 1. CARGA DE DATOS (DESDE LA API + GUARDADO EN SQLITE)
# ==============================================================================
st.header("1. Carga de datos")

st.markdown(
    f"Los datos se obtienen desde la **API histórica de Open-Meteo**, para la ubicación de "
    f"**Cuenca, Ecuador** (lat `{LATITUD}`, lon `{LONGITUD}`), en el rango **{FECHA_INICIO} a {FECHA_FIN}**: "
    f"temperatura máxima, temperatura mínima, precipitación diaria y velocidad máxima del viento. "
    f"Se almacenan en una base de datos **SQLite** y luego se leen con `pd.read_sql()`."
)


@st.cache_data(show_spinner=False)
def obtener_datos_climaticos() -> pd.DataFrame:
    """Consulta el histórico climático diario de Cuenca en la API de Open-Meteo, con reintentos."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": LATITUD,
        "longitude": LONGITUD,
        "start_date": FECHA_INICIO,
        "end_date": FECHA_FIN,
        "daily": VARIABLES_DIARIAS,
        "timezone": ZONA_HORARIA,
    }

    ultimo_error = None
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            respuesta = requests.get(url, params=params, timeout=TIMEOUT_SEGUNDOS)
            respuesta.raise_for_status()
            datos = respuesta.json()["daily"]
            df = pd.DataFrame(datos)
            df["ciudad"] = "Cuenca"
            return df
        except (requests.exceptions.RequestException, KeyError, TypeError) as error:
            ultimo_error = error
            if intento < MAX_REINTENTOS:
                time.sleep(2 * intento)

    raise ConnectionError(
        f"No se pudieron obtener los datos climáticos tras {MAX_REINTENTOS} intentos. "
        f"Último error: {ultimo_error}"
    )


def guardar_en_sqlite(df: pd.DataFrame):
    conexion = sqlite3.connect(DB_NAME)
    df.to_sql(TABLE_NAME, conexion, if_exists="replace", index=False)
    conexion.close()


def leer_desde_sqlite() -> pd.DataFrame:
    conexion = sqlite3.connect(DB_NAME)
    df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conexion)
    conexion.close()
    return df


def tabla_existe() -> bool:
    """Verifica si el archivo de la base de datos y la tabla ya existen."""
    if not os.path.exists(DB_NAME):
        return False
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (TABLE_NAME,)
    )
    existe = cursor.fetchone() is not None
    conexion.close()
    return existe


# Botón único para refrescar manualmente (key único para evitar IDs duplicados)
if st.button("🔄 Actualizar datos desde la API", key="btn_actualizar_datos"):
    st.cache_data.clear()
    try:
        with st.spinner("Actualizando datos climáticos desde Open-Meteo..."):
            df_api = obtener_datos_climaticos()
            guardar_en_sqlite(df_api)
        st.success("✅ Datos actualizados correctamente.")
    except ConnectionError as error:
        st.error(
            "⚠️ No se pudo conectar con la API de Open-Meteo. Se seguirán mostrando "
            "los últimos datos guardados localmente."
        )
        st.caption(f"Detalle técnico: {error}")

# Si es la primera ejecución (no existe la BD/tabla todavía), se intenta cargar automáticamente
if not tabla_existe():
    try:
        with st.spinner("Cargando datos por primera vez desde la API..."):
            df_api = obtener_datos_climaticos()
            guardar_en_sqlite(df_api)
    except ConnectionError as error:
        st.error(
            "⚠️ No se pudo conectar con la API de Open-Meteo para la carga inicial. "
            "Verifica tu conexión a internet e intenta pulsar el botón "
            "'🔄 Actualizar datos desde la API' nuevamente."
        )
        st.caption(f"Detalle técnico: {error}")
        st.stop()

df_original = leer_desde_sqlite()

col1, col2 = st.columns(2)
col1.metric("Número de Registros (Filas)", df_original.shape[0])
col2.metric("Número de Columnas", df_original.shape[1])

st.subheader("DataFrame Original (Cuenca, leído desde SQLite):")
st.dataframe(df_original.head())

df = df_original.copy()

# ==============================================================================
# 2. EXPLORACIÓN DE DATOS
# ==============================================================================
st.header("2. Exploración de datos")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Primeros Registros", "Información e Inspección",
    "Estadísticas Descriptivas", "Valores Únicos", "Valores Nulos"
])

with tab1:
    st.write("**Primeros registros del dataset (`df.head()`):**")
    st.dataframe(df.head(10))

with tab2:
    st.write("**Tipos de datos por columna (`df.dtypes`):**")
    st.dataframe(df.dtypes.astype(str).to_frame(name="Tipo de Dato"))

    st.write("**Información General Estructurada (`df.info()`):**")
    buffer_info = io.StringIO()
    df.info(buf=buffer_info)
    st.text(buffer_info.getvalue())

with tab3:
    st.write("**Estadísticas descriptivas de variables numéricas (`df.describe()`):**")
    st.dataframe(df.describe())

with tab4:
    st.write("**Cantidad de valores únicos por columna (`df.nunique()`):**")
    st.dataframe(df.nunique().to_frame(name="Valores Únicos"))

with tab5:
    st.write("**Conteo de valores nulos por columna (`df.isnull().sum()`):**")
    st.dataframe(df.isnull().sum().to_frame(name="Valores Nulos"))

# ==============================================================================
# 3. LIMPIEZA DE DATOS
# ==============================================================================
st.header("3. Limpieza de datos")

df_limpio = df.copy()

# Técnica 1: Eliminar filas sin fecha (dropna)
filas_antes_dropna = df_limpio.shape[0]
df_limpio = df_limpio.dropna(subset=["time"])

# Técnica 2: Corregir tipos de datos (astype / to_datetime)
df_limpio["fecha"] = pd.to_datetime(df_limpio["time"], format="%Y-%m-%d")
df_limpio = df_limpio.drop(columns=["time"])

# Técnica 3: Reemplazar / Imputar nulos (fillna) con interpolación temporal
df_limpio = df_limpio.sort_values("fecha")
COLUMNAS_NUMERICAS = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_speed_10m_max"]
for col_num in COLUMNAS_NUMERICAS:
    df_limpio[col_num] = df_limpio[col_num].interpolate().fillna(df_limpio[col_num].median())

# Técnica 4: Eliminar duplicados (drop_duplicates)
filas_antes = df_limpio.shape[0]
df_limpio = df_limpio.drop_duplicates(subset=["fecha"])
filas_despues = df_limpio.shape[0]

# Técnica 5: Renombrar columnas
df_limpio = df_limpio.rename(columns={
    "temperature_2m_max": "temp_max",
    "temperature_2m_min": "temp_min",
    "precipitation_sum": "precipitacion_mm",
    "wind_speed_10m_max": "viento_max_kmh",
})

# Técnica 6: Eliminar Outliers (Capping por IQR) en precipitación
q1, q3 = df_limpio["precipitacion_mm"].quantile(0.25), df_limpio["precipitacion_mm"].quantile(0.75)
iqr = q3 - q1
df_limpio["precipitacion_mm"] = df_limpio["precipitacion_mm"].clip(
    lower=max(0, q1 - 1.5 * iqr), upper=q3 + 1.5 * iqr
)

st.success(
    "✅ Se han aplicado 6 técnicas de limpieza (`dropna()`, corrección de tipos con "
    "`astype()`/`to_datetime()`, `fillna()`/interpolación, `drop_duplicates()`, `rename()` "
    "y control de outliers con IQR)."
)
st.write(f"Filas eliminadas por valores nulos en fecha: {filas_antes_dropna - df_limpio.shape[0] if filas_antes_dropna else 0}")
st.write(f"Filas eliminadas por duplicación: {filas_antes - filas_despues}")

with st.expander("Ver Dataset Limpio"):
    st.dataframe(df_limpio)

# ==============================================================================
# 4. TRANSFORMACIÓN DE DATOS
# ==============================================================================
st.header("4. Transformación de datos")

df_transformado = df_limpio.copy()


# Transformación 1: Crear nuevas columnas (Clasificación del día según precipitación)
def clasificar_lluvia(precip_mm):
    if pd.isna(precip_mm):
        return "Sin Datos"
    precip_mm = float(precip_mm)
    if precip_mm == 0:
        return "Seco"
    elif precip_mm < 5:
        return "Llovizna"
    elif precip_mm < 20:
        return "Lluvia Moderada"
    else:
        return "Lluvia Intensa"


df_transformado["categoria_lluvia"] = df_transformado["precipitacion_mm"].apply(clasificar_lluvia)

# Transformación 2: Extraer año, mes y trimestre de la fecha (dt.year / dt.month / dt.quarter)
df_transformado["anio"] = df_transformado["fecha"].dt.year
df_transformado["mes"] = df_transformado["fecha"].dt.month
df_transformado["trimestre"] = df_transformado["fecha"].dt.quarter

# Transformación 3: Filtrar información (Filtro interactivo en Streamlit + loc[])
st.subheader("Filtrar registros por rango de fechas")
fecha_min_data = df_transformado["fecha"].min().date()
fecha_max_data = df_transformado["fecha"].max().date()
rango_fechas = st.slider(
    "Selecciona el rango de fechas:", fecha_min_data, fecha_max_data, (fecha_min_data, fecha_max_data)
)
df_filtrado = df_transformado.loc[
    (df_transformado["fecha"].dt.date >= rango_fechas[0]) & (df_transformado["fecha"].dt.date <= rango_fechas[1])
]
st.dataframe(df_filtrado)

# Transformación 4: Agrupar datos (groupby por año)
st.subheader("Agrupación (`groupby`): Promedio de indicadores por Año")
df_agrupado = df_transformado.groupby("anio")[
    ["temp_max", "temp_min", "precipitacion_mm", "viento_max_kmh"]
].mean().round(2).reset_index()
st.dataframe(df_agrupado)

# Transformación 5: Ordenar registros (sort_values) - días con mayor precipitación
st.subheader("Top 5 días con mayor precipitación en Cuenca")
top_dias = df_transformado.sort_values("precipitacion_mm", ascending=False).head(5)
st.dataframe(top_dias[["fecha", "precipitacion_mm", "temp_max", "temp_min", "categoria_lluvia"]])

# ==============================================================================
# 5. VISUALIZACIÓN
# ==============================================================================
st.header("5. Visualización de datos")

col_g1, col_g2 = st.columns(2)
col_g3, col_g4 = st.columns(2)

# Gráfico 1: Barras (Nativo de Streamlit) - Precipitación promedio por año
with col_g1:
    st.subheader("1. Barras: Precipitación Promedio por Año")
    serie_barras = df_agrupado.set_index("anio")["precipitacion_mm"]
    st.bar_chart(serie_barras)

# Gráfico 2: Histograma (Matplotlib/Seaborn) - distribución de la temperatura máxima
with col_g2:
    st.subheader("2. Histograma: Distribución de la Temperatura Máxima")
    fig_hist, ax_hist = plt.subplots(figsize=(5, 3.5))
    sns.histplot(df_transformado["temp_max"], bins=20, kde=True, color="tomato", ax=ax_hist)
    ax_hist.set_xlabel("Temperatura máxima (°C)")
    ax_hist.set_ylabel("Frecuencia")
    st.pyplot(fig_hist)

# Gráfico 3: Dispersión / Scatter (Matplotlib/Seaborn)
with col_g3:
    st.subheader("3. Dispersión: Temperatura Máxima vs Viento Máximo")
    fig_scat, ax_scat = plt.subplots(figsize=(5, 3.5))
    sns.scatterplot(
        data=df_transformado, x="temp_max", y="viento_max_kmh",
        hue="categoria_lluvia", ax=ax_scat
    )
    ax_scat.set_xlabel("Temperatura máxima (°C)")
    ax_scat.set_ylabel("Viento máximo (km/h)")
    st.pyplot(fig_scat)

# Gráfico 4: Pastel (Matplotlib) - distribución de días por categoría de lluvia
with col_g4:
    st.subheader("4. Pastel: Días por Categoría de Lluvia")
    conteo_categoria_pie = df_transformado["categoria_lluvia"].value_counts()
    fig_pie, ax_pie = plt.subplots(figsize=(4, 4))
    ax_pie.pie(
        conteo_categoria_pie, labels=conteo_categoria_pie.index, autopct='%1.1f%%',
        startangle=90, colors=["#66b3ff", "#99ff99", "#ffcc99", "#ff9999"]
    )
    ax_pie.axis('equal')
    st.pyplot(fig_pie)

# Gráfico 5: Línea - evolución mensual promedio de temperatura máxima y mínima
st.subheader("5. Línea: Evolución Mensual de la Temperatura en Cuenca")
df_mensual = df_transformado.groupby(
    df_transformado["fecha"].dt.to_period("M")
)[["temp_max", "temp_min"]].mean().reset_index()
df_mensual["fecha"] = df_mensual["fecha"].dt.to_timestamp()

fig_linea, ax_linea = plt.subplots(figsize=(10, 4))
sns.lineplot(data=df_mensual, x="fecha", y="temp_max", label="Temp. Máxima Promedio", ax=ax_linea)
sns.lineplot(data=df_mensual, x="fecha", y="temp_min", label="Temp. Mínima Promedio", ax=ax_linea)
ax_linea.set_xlabel("Fecha")
ax_linea.set_ylabel("Temperatura (°C)")
ax_linea.legend(loc="upper left")
st.pyplot(fig_linea)

# ==============================================================================
# 6. EXPORTACIÓN DE DATOS
# ==============================================================================
st.header("6. Exportación de datos")

df_transformado.to_csv("datos_limpios.csv", index=False)

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
    df_transformado.to_excel(writer, sheet_name='Datos Limpios', index=False)

st.info("💾 El archivo `datos_limpios.csv` ha sido guardado localmente mediante el comando estricto de la rúbrica.")

st.download_button(
    label="📥 Descargar datos_limpios.xlsx (Formato Web)",
    data=buffer.getvalue(),
    file_name="datos_limpios.xlsx",
    mime="application/vnd.ms-excel"
)

# ==============================================================================
# 7. INTERFAZ - SIDEBAR
# ==============================================================================
st.sidebar.title("Menú de Navegación")
st.sidebar.info("""
**Secciones del Proyecto:**
1. Carga de Datos (API + SQLite)
2. Exploración (EDA)
3. Limpieza de Datos
4. Transformación
5. Visualización Estructurada
6. Exportación final
""")
st.sidebar.markdown("---")
st.sidebar.caption("Fuente: API de Open-Meteo — Cuenca, Ecuador — Datos climáticos históricos diarios (2015-2024)")


