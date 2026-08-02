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
    """Gráfico narrativo: episodio del calado en Barranquilla."""
    col = "export"                              # ← cambia a "export" si ahí se ve mejor
    s = serie_semanal(df, "Barranquilla", col).loc["2024-01":]
    movil = s.rolling(13).median()             # "lo habitual" del detector

    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(s.index, s.values / 1000, color=AZUL, linewidth=1.5, label="Semanal")
    ax.plot(movil.index, movil.values / 1000, color=AZUL, linewidth=1.3,
            linestyle=":", alpha=0.8, label="Mediana móvil (13 sem.)")

    ax.axvspan(pd.Timestamp("2025-10-01"), pd.Timestamp("2026-03-25"),
               color=ROJO, alpha=0.10)
    # Anotación debajo de la línea, fuente menor
    ymin = s.loc["2025-10":"2026-03"].min() / 1000
    ax.annotate("Crisis del calado del canal",
                xy=(pd.Timestamp("2025-12-15"), ymin),
                xytext=(pd.Timestamp("2025-12-15"), ymin * 0.6),
                fontsize=8, color=ROJO, ha="center",
                arrowprops=dict(arrowstyle="-", color=ROJO, alpha=0.5))

    ax.set_title(f"Barranquilla — {'importaciones' if col=='import' else 'exportaciones'} semanales",
                 fontsize=12, fontweight="bold", loc="left")
    ax.set_ylabel("miles de toneladas / semana")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(fontsize=8, loc="upper right", frameon=False)
    ax.margins(x=0.01)

    fig.savefig(SALIDA / "barranquilla_calado.svg", format="svg")
    plt.close(fig)
    print("✓ barranquilla_calado.svg")

def grafico_pandemia(df):
    """Gráfico narrativo: impacto de la pandemia, un panel por puerto (escalas propias)."""
    puertos = ["Buenaventura", "Cartagena", "Barranquilla", "Santa Marta"]
    colores = {"Buenaventura": "#1a5490", "Cartagena": "#c0392b",
               "Barranquilla": "#27ae60", "Santa Marta": "#e67e22"}

    fig, axes = plt.subplots(2, 2, figsize=(10, 6), sharex=True)
    for ax, p in zip(axes.flat, puertos):
        s = serie_semanal(df, p, "import").rolling(4).mean()
        ax.plot(s.index, s.values / 1000, color=colores[p], linewidth=1.3)
        ax.axvspan(pd.Timestamp("2020-03-15"), pd.Timestamp("2020-06-30"),
                   color="grey", alpha=0.15)
        ax.set_title(p, fontsize=10, fontweight="bold", loc="left")
        ax.set_ylabel("mil ton/sem", fontsize=8)
        ax.tick_params(labelsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.suptitle("Actividad portuaria de Colombia — importaciones semanales por puerto",
                 fontsize=12, fontweight="bold", x=0.02, ha="left")
    fig.text(0.5, 0.005, "Zona gris: confinamiento inicial por COVID-19 (mar–jun 2020)",
             ha="center", fontsize=8, color="#444")
    fig.savefig(SALIDA / "pandemia_puertos.svg", format="svg")
    plt.close(fig)
    print("✓ pandemia_puertos.svg")

def graficos_por_puerto(df, flujo="import"):
    """Un gráfico ancho por puerto, para el flujo indicado (import o export)."""
    puertos = {"Buenaventura": "#1a5490", "Cartagena": "#c0392b",
               "Barranquilla": "#27ae60", "Santa Marta": "#e67e22"}
    etiqueta_flujo = "importaciones" if flujo == "import" else "exportaciones"

    hitos = [
        (pd.Timestamp("2020-03-15"), pd.Timestamp("2020-06-30"), "Confinamiento COVID-19"),
        (pd.Timestamp("2021-04-28"), pd.Timestamp("2021-06-15"), "Paro nacional"),
    ]

    for puerto, color in puertos.items():
        s = serie_semanal(df, puerto, flujo).rolling(4).mean()
        fig, ax = plt.subplots(figsize=(11, 3.6))
        ax.plot(s.index, s.values / 1000, color=color, linewidth=1.4)

        for ini, fin, etq in hitos:
            ax.axvspan(ini, fin, color="grey", alpha=0.15)
            ax.annotate(etq, xy=(ini, ax.get_ylim()[1] * 0.92),
                        fontsize=7.5, color="#555", ha="left")

        ax.set_title(f"{puerto} — {etiqueta_flujo} semanales (suavizado 4 sem.)",
                     fontsize=11, fontweight="bold", loc="left")
        ax.set_ylabel("mil ton/sem", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.margins(x=0.01)

        slug = puerto.lower().replace(" ", "")
        fig.savefig(SALIDA / f"puerto_{slug}_{flujo}.svg", format="svg")
        plt.close(fig)
        print(f"✓ puerto_{slug}_{flujo}.svg")
       


def main():
    df = cargar_snapshot()
    graficos_por_puerto(df, "import")
    graficos_por_puerto(df, "export")
    print("Gráficos generados en", SALIDA)

if __name__ == "__main__":
    main()
