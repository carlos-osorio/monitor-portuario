"""Detección de anomalías sobre el snapshot más reciente.

Diseño calibrado por backtest (ver DECISIONS.md y notebooks/02):
- Indicador principal: importaciones semanales por puerto.
- Detector de choques: z-modificado (mediana/MAD por puerto, ventana K=13,
  solo pasado). Alerta por caídas z <= -3.0; subidas z >= +3.0 como nota.
- Detector de regímenes: CUSUM unilateral inferior (k=0.5, h=5.0) con
  semántica de episodios: nueva / en curso / cierre.
- Excepción festiva: semanas ISO 51, 52, 1 y 2 se reportan pero no alertan.
- Pronóstico en modo sombra: se calcula y evalúa, no se publica.
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# ── PARÁMETROS (calibrados en notebooks/02, jul 2026) ────────────
K_VENTANA = 13
Z_CHOQUE = 3.0
CUSUM_K = 0.5
CUSUM_H = 5.0
SEMANAS_FESTIVAS = {51, 52, 1, 2}
INDICADOR = "import"
HORIZONTE_SOMBRA = 4          # semanas del pronóstico no publicado


def serie_semanal(df):
    """Series semanales del indicador por puerto, sin la semana parcial."""
    sem = (df.set_index("date").groupby("portname")[INDICADOR]
             .resample("W").sum().unstack(level=0))
    return sem.iloc[:-1]


def z_modificado(serie):
    mediana = serie.rolling(K_VENTANA).median().shift(1)
    mad = (serie.rolling(K_VENTANA)
                .apply(lambda v: np.median(np.abs(v - np.median(v))), raw=True)
                .shift(1))
    return 0.6745 * (serie - mediana) / mad


def cusum_negativo(z):
    s, out = 0.0, []
    for val in z.fillna(0):
        s = min(0.0, s + val + CUSUM_K)
        out.append(s)
    return pd.Series(out, index=z.index)


def estado_episodio(cus):
    """Estado del episodio CUSUM al cierre de la serie de un puerto."""
    en_alerta = cus <= -CUSUM_H
    if en_alerta.iloc[-1]:
        inicio = en_alerta[::-1].idxmin() if not en_alerta.all() else cus.index[0]
        # idxmin invertido da la última semana NO-alerta; el episodio empieza después
        inicio = cus.index[cus.index.get_loc(inicio) + 1] if not en_alerta.all() else inicio
        semanas = int((cus.index >= inicio).sum())
        estado = "nueva" if semanas == 1 else "en_curso"
        return {"estado": estado, "inicio": str(inicio.date()), "semanas": semanas}
    if len(cus) > 1 and en_alerta.iloc[-2]:
        return {"estado": "cierre", "cerrado_en": str(cus.index[-1].date())}
    return {"estado": "normal"}


def main():
    archivos = sorted(Path("data").glob("portwatch_*.csv"))
    df = pd.read_csv(archivos[-1], parse_dates=["date"])
    sem = serie_semanal(df)

    ultima = sem.index[-1]
    es_festiva = ultima.isocalendar().week in SEMANAS_FESTIVAS

    resultado = {"semana_analizada": str(ultima.date()),
                 "excepcion_festiva": bool(es_festiva),
                 "puertos": {}}

    for puerto in sem.columns:
        s = sem[puerto]
        z = z_modificado(s)
        cus = cusum_negativo(z)
        z_hoy = float(z.iloc[-1])

        info = {
            "import_semana": int(s.iloc[-1]),
            "baseline": int(s.rolling(K_VENTANA).median().shift(1).iloc[-1]),
            "z": round(z_hoy, 2),
            "choque_caida": bool(z_hoy <= -Z_CHOQUE) and not es_festiva,
            "nota_subida": bool(z_hoy >= Z_CHOQUE) and not es_festiva,
            "cusum": round(float(cus.iloc[-1]), 2),
            "episodio": estado_episodio(cus),
        }


        s_exp = (df[df["portname"] == puerto].set_index("date")["export"]
                 .resample("W").sum().iloc[:-1])
        info["export_semana"] = int(s_exp.iloc[-1])
        info["export_baseline"] = int(s_exp.rolling(K_VENTANA).median().shift(1).iloc[-1])
        z_exp = z_modificado(s_exp)
        cus_exp = cusum_negativo(z_exp)
        z_exp_hoy = float(z_exp.iloc[-1])
        info["export_z"] = round(z_exp_hoy, 2)
        info["export_choque_caida"] = bool(z_exp_hoy <= -Z_CHOQUE) and not es_festiva
        info["export_nota_subida"] = bool(z_exp_hoy >= Z_CHOQUE) and not es_festiva
        info["export_episodio"] = (estado_episodio(cus_exp) if not es_festiva
                                   else {"estado": "suspendido_festivo"})
      
        if es_festiva:
            info["episodio"] = {"estado": "suspendido_festivo"}
        resultado["puertos"][puerto] = info

    # ── Pronóstico sombra: persiste el baseline, y evalúa el de la corrida pasada
    resultado["sombra"] = {}
    for puerto in sem.columns:
        base = float(sem[puerto].rolling(K_VENTANA).median().iloc[-1])
        resultado["sombra"][puerto] = {"pronostico": [int(base)] * HORIZONTE_SOMBRA}

    previos = sorted(Path("data").glob("analisis_*.json"))
    if previos:
        with open(previos[-1]) as f:
            pasado = json.load(f)
        errores = {}
        for puerto, s in pasado.get("sombra", {}).items():
            sem_pasada = pd.Timestamp(pasado["semana_analizada"])
            nuevas = sem.loc[sem.index > sem_pasada, puerto]
            pron = s["pronostico"][:len(nuevas)]
            if len(pron):
                reales = nuevas.iloc[:len(pron)].values
                errores[puerto] = round(float(np.mean(
                    np.abs(reales - np.array(pron)) / np.maximum(reales, 1))) * 100, 1)
        resultado["sombra_error_mape_pct"] = errores

    fecha = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
    salida = Path("data") / f"analisis_{fecha}.json"
    with open(salida, "w") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print(f"Análisis escrito en {salida}")
    for p, info in resultado["puertos"].items():
        print(f"  {p:<14} z={info['z']:>6}  cusum={info['cusum']:>6}  "
              f"episodio={info['episodio']['estado']}")


if __name__ == "__main__":
    main()
