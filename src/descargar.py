"""Descarga las series de PortWatch para los puertos v1 y guarda un snapshot fechado."""

from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests

URL = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
       "Daily_Ports_Data/FeatureServer/0/query")

PUERTOS_V1 = {
    "port183": "Buenaventura",
    "port218": "Cartagena",
    "port120": "Barranquilla",
    "port1154": "Santa Marta",
}

CAMPOS = "date,portid,portname,portcalls,portcalls_container,import,export"
INICIO_SERIE = "2019-01-07"   # antes de esta fecha la serie está muerta (verificado en exploración)

import time

def descargar_puerto(pid: str, reintentos: int = 3) -> pd.DataFrame:
    """Descarga todas las filas de un puerto, paginando de a 1000.

    Resiliente a hipos transitorios del API: reintenta con espera creciente
    y solo falla ruidosamente si tras varios intentos no obtiene datos válidos.
    """
    todas, offset = [], 0
    while True:
        params = {
            "where": f"portid = '{pid}'",
            "outFields": CAMPOS,
            "orderByFields": "date",
            "resultOffset": offset,
            "resultRecordCount": 1000,
            "f": "json",
        }

        # Petición con reintentos ante fallo transitorio
        datos = None
        for intento in range(reintentos):
            try:
                r = requests.get(URL, params=params, timeout=60)
                r.raise_for_status()
                cuerpo = r.json()
            except (requests.RequestException, ValueError) as e:
                espera = 2 ** (intento + 1)   # 2s, 4s, 8s
                print(f"  {pid} offset {offset}: intento {intento+1} falló "
                      f"({e}); reintento en {espera}s")
                time.sleep(espera)
                continue

            # El API respondió, pero ¿trae datos o un error empaquetado?
            if "features" in cuerpo:
                datos = cuerpo["features"]
                break
            if "error" in cuerpo:
                espera = 2 ** (intento + 1)
                print(f"  {pid} offset {offset}: el API devolvió error "
                      f"{cuerpo['error'].get('code','?')}; reintento en {espera}s")
                time.sleep(espera)
                continue
            # Respuesta 200 sin 'features' ni 'error' (p.ej. esquema): reintentar
            espera = 2 ** (intento + 1)
            print(f"  {pid} offset {offset}: respuesta sin 'features'; "
                  f"reintento en {espera}s")
            time.sleep(espera)

        # Agotados los reintentos sin datos válidos → fallo ruidoso, claro
        if datos is None:
            raise RuntimeError(
                f"No se pudo descargar {pid} (offset {offset}) tras "
                f"{reintentos} intentos. El API de PortWatch no devolvió "
                f"datos válidos; probablemente un problema transitorio del "
                f"servicio. Revisar y reintentar la corrida."
            )

        tanda = [f["attributes"] for f in datos]
        todas.extend(tanda)
        if len(tanda) < 1000:
            break
        offset += 1000

    return pd.DataFrame(todas)


def main() -> None:
    frames = []
    for pid, nombre in PUERTOS_V1.items():
        print(f"Descargando {nombre}...")
        df = descargar_puerto(pid)
        if df.empty:
            raise RuntimeError(f"El puerto {nombre} ({pid}) devolvió 0 filas: revisar la fuente.")
        frames.append(df)

    datos = pd.concat(frames, ignore_index=True)
    datos["date"] = pd.to_datetime(datos["date"])
    datos = datos[datos["date"] >= INICIO_SERIE]

    carpeta = Path("data")
    carpeta.mkdir(exist_ok=True)
    hoy_bogota = datetime.now(ZoneInfo("America/Bogota")).date()
    archivo = carpeta / f"portwatch_{hoy_bogota.isoformat()}.csv"
    datos.to_csv(archivo, index=False)
    print(f"Guardadas {len(datos)} filas en {archivo}")


if __name__ == "__main__":
    main()
