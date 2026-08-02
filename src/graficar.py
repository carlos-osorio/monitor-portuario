"""Genera los gráficos del dashboard histórico a partir del último snapshot.

Salida: SVGs en docs/graficos/, que dashboard.html incrusta.
Corre en el pipeline, después de descargar.py (necesita el CSV del snapshot).
"""

import glob
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")                      # backend sin pantalla, para Actions
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

SALIDA = Path("docs/graficos")
SALIDA.mkdir(parents=True, exist_ok=True)

# Estilo sobrio y consistente con la identidad del observatorio
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "figure.autolayout": True,
})
AZUL = "#1a5490"
ROJO = "#c0392b"


def cargar_snapshot():
    csv = sorted(glob.glob("data/portwatch_*.csv"))[-1]
    df = pd.read_csv(csv, parse_dates=["date"])
    return df


def serie_semanal(df, puerto, columna):
    s = (df[df["portname"] == puerto]
         .set_index("date")[columna].resample("W").sum().iloc[:-1])
    return s


def grafico_barranquilla(df):
    """Gráfico narrativo 1: el episodio del calado, importaciones de Barranquilla."""
    s = serie_semanal(df, "Barranquilla", "import").loc["2024-01":]

    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(s.index, s.values / 1000, color=AZUL, linewidth=1.6)

    # Sombrea el episodio del calado (oct 2025 – mar 2026)
    ax.axvspan(pd.Timestamp("2025-10-01"), pd.Timestamp("2026-03-25"),
               color=ROJO, alpha=0.10)
    ax.annotate("Crisis del calado\ndel canal de acceso",
                xy=(pd.Timestamp("2025-12-15"), s.loc["2025-10":"2026-03"].min()/1000),
                xytext=(pd.Timestamp("2025-11-01"), s.max()/1000 * 0.55),
                fontsize=9, color=ROJO, ha="center")

    ax.set_title("Barranquilla — importaciones semanales estimadas",
                 fontsize=12, fontweight="bold", loc="left")
    ax.set_ylabel("miles de toneladas / semana")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.margins(x=0.01)

    fig.savefig(SALIDA / "barranquilla_calado.svg", format="svg")
    plt.close(fig)
    print("✓ barranquilla_calado.svg")


def main():
    df = cargar_snapshot()
    grafico_barranquilla(df)
    print("Gráficos generados en", SALIDA)


if __name__ == "__main__":
    main()
