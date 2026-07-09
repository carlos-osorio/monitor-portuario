"""Valida el snapshot más reciente según la política de validación (ver DECISIONS.md).

Niveles: GRITA detiene el pipeline (exit 1 → workflow rojo); ADVIERTE deja
constancia en un archivo que el reporte mostrará; ANOTA acumula métricas.
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

# ── POLÍTICA (editar aquí, no abajo) ─────────────────────────────
COLUMNAS_ESPERADAS = {"date", "portid", "portname", "portcalls",
                      "portcalls_container", "import", "export"}
PUERTOS_ESPERADOS = {"Buenaventura", "Cartagena", "Barranquilla", "Santa Marta"}
INICIO_SERIE = "2019-01-07"
REZAGO_ADVIERTE_DIAS = 16          # un ciclo de publicación perdido
REZAGO_GRITA_DIAS = 30             # fuente presuntamente muerta
TOPES_DIARIOS = {                  # umbral superior de plausibilidad (criterio de dominio)
    "portcalls": 25,               # TODO Carlos: fijar con tu criterio
    "import": 400_000,             # TODO Carlos: toneladas/día máximas creíbles
    "export": 400_000,             # TODO Carlos
}
NUMERICAS = ["portcalls", "portcalls_container", "import", "export"]

gritos, advertencias, notas = [], [], {}


def cargar_snapshots():
    archivos = sorted(Path("data").glob("portwatch_*.csv"))
    if not archivos:
        gritos.append("No existe ningún snapshot en data/")
        return None, None
    actual = pd.read_csv(archivos[-1], parse_dates=["date"])
    anterior = pd.read_csv(archivos[-2], parse_dates=["date"]) if len(archivos) > 1 else None
    notas["snapshot_validado"] = archivos[-1].name
    return actual, anterior


def chequeo_esquema(df):                                   # 1 → GRITA
    faltantes = COLUMNAS_ESPERADAS - set(df.columns)
    if faltantes:
        gritos.append(f"Esquema roto: faltan columnas {faltantes}")
        return
    for col in NUMERICAS:
        if not pd.api.types.is_numeric_dtype(df[col]):
            gritos.append(f"Esquema roto: '{col}' no es numérica")


def chequeo_presencia(df):                                 # 2 → GRITA
    faltan = PUERTOS_ESPERADOS - set(df["portname"].unique())
    if faltan:
        gritos.append(f"Puertos ausentes del snapshot: {faltan}")


def chequeo_completitud(df):                               # 3 → GRITA
    for puerto, g in df.groupby("portname"):
        if g["date"].duplicated().any():
            gritos.append(f"{puerto}: fechas duplicadas")
        esperadas = pd.date_range(INICIO_SERIE, g["date"].max())
        huecos = len(esperadas) - g["date"].nunique()
        if huecos > 0:
            gritos.append(f"{puerto}: {huecos} días faltantes en la serie")


def chequeo_frescura(df):                                  # 4 → ADVIERTE/GRITA
    hoy = datetime.now(ZoneInfo("America/Bogota")).date()
    rezago = (hoy - df["date"].max().date()).days
    notas["rezago_dias"] = rezago
    if rezago >= REZAGO_GRITA_DIAS:
        gritos.append(f"Rezago de {rezago} días: fuente presuntamente muerta")
    elif rezago >= REZAGO_ADVIERTE_DIAS:
        advertencias.append(f"Rezago de {rezago} días (normal ~10): ciclo perdido")


def chequeo_rangos(df):                                    # 5 → partido
    for col in NUMERICAS:
        negativos = (df[col] < 0).sum()
        if negativos:
            gritos.append(f"{negativos} valores negativos en '{col}' (imposible físico)")
    for col, tope in TOPES_DIARIOS.items():
        raros = df[df[col] > tope]
        for _, fila in raros.iterrows():
            advertencias.append(
                f"{fila['portname']} {fila['date'].date()}: {col}={fila[col]} supera tope {tope}")


def chequeo_ceros(df):                                     # 6 → ADVIERTE máxima
    ultima_completa = df["date"].max() - pd.Timedelta(days=6)
    reciente = df[df["date"] >= ultima_completa]
    for puerto, g in reciente.groupby("portname"):
        if (g["portcalls"] == 0).all() and (g["import"] == 0).all():
            advertencias.append(
                f"⚠⚠ {puerto}: SEMANA COMPLETA EN CERO — feed caído o disrupción mayor. REVISAR HOY.")


def chequeo_revisiones(actual, anterior):                  # 7 → ANOTA
    if anterior is None:
        notas["revisiones"] = "sin snapshot anterior para comparar"
        return
    corte = anterior["date"].max()
    llaves = ["portid", "date"]
    a = actual[actual["date"] <= corte].set_index(llaves).sort_index()
    b = anterior.set_index(llaves).sort_index()
    comunes = a.index.intersection(b.index)
    cambiadas = (a.loc[comunes, NUMERICAS] != b.loc[comunes, NUMERICAS]).any(axis=1)
    notas["revisiones_pct_filas"] = round(100 * cambiadas.mean(), 2)
    notas["revisiones_delta_import_ton"] = int(
        (a.loc[comunes, "import"] - b.loc[comunes, "import"]).abs().sum())


def main():
    actual, anterior = cargar_snapshots()
    if actual is not None:
        chequeo_esquema(actual)
        if not gritos:                       # sin esquema sano, lo demás no es confiable
            chequeo_presencia(actual)
            chequeo_completitud(actual)
            chequeo_frescura(actual)
            chequeo_rangos(actual)
            chequeo_ceros(actual)
            chequeo_revisiones(actual, anterior)

    fecha = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
    Path("data").mkdir(exist_ok=True)
    with open(f"data/validacion_{fecha}.json", "w") as f:
        json.dump({"gritos": gritos, "advertencias": advertencias, "notas": notas},
                  f, indent=2, ensure_ascii=False, default=str)

    print(f"Gritos: {len(gritos)} | Advertencias: {len(advertencias)} | Notas: {notas}")
    for a in advertencias:
        print("  ADVIERTE:", a)
    if gritos:
        for g in gritos:
            print("  GRITA:", g)
        sys.exit(1)      # ← exit code 1: el mismo que viste en rojo toda la semana


if __name__ == "__main__":
    main()
