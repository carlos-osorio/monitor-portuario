"""Descarga las series de PortWatch para los puertos v1 y guarda un snapshot fechado."""

from datetime import date
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


def descargar_puerto(pid: str) -> pd.DataFrame:
    """Descarga todas las filas de un puerto, paginando de a 1000."""
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
        r = requests.get(URL, params=params, timeout=60)
        r.raise_for_status()
        tanda = [f["attributes"] for f in r.json()["features"]]
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
    archivo = carpeta / f"portwatch_{date.today().isoformat()}.csv"
    datos.to_csv(archivo, index=False)
    print(f"Guardadas {len(datos)} filas en {archivo}")


if __name__ == "__main__":
    main()
