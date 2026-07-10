"""Convierte el análisis más reciente en el reporte semanal (Markdown).

Salida: reports/YYYY-MM-DD.md (histórico) y reports/ultimo.md (enlace estable).
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ESTADOS = {
    "normal": "🟢 Normal",
    "nueva": "🔴 ALERTA NUEVA — inicio de episodio",
    "en_curso": "🟠 Episodio en curso",
    "cierre": "🔵 Episodio cerrado — normalización",
    "suspendido_festivo": "⚪ Semana festiva (sin alertas)",
}


def linea_puerto(nombre, d):
    desv = 100 * (d["import_semana"] - d["baseline"]) / d["baseline"]
    partes = [f"**{nombre}** — {ESTADOS[d['episodio']['estado']]}",
              f"Importaciones: {d['import_semana']:,} ton. "
              f"({desv:+.0f}% vs. patrón de {d['baseline']:,} ton.; z = {d['z']})"]
    ep = d["episodio"]
    if ep["estado"] == "en_curso":
        partes.append(f"Bajo su patrón desde {ep['inicio']} ({ep['semanas']} semanas)")
    if ep["estado"] == "cierre":
        partes.append(f"Normalizó esta semana")
    if d.get("choque_caida"):
        partes.append("⚠ Caída abrupta esta semana")
    if d.get("nota_subida"):
        partes.append("↑ Semana inusualmente alta (nota informativa)")
    return "  \n".join(partes)


def main():
    analisis = sorted(Path("data").glob("analisis_*.json"))[-1]
    with open(analisis) as f:
        r = json.load(f)

    validaciones = sorted(Path("data").glob("validacion_*.json"))
    advertencias = []
    if validaciones:
        with open(validaciones[-1]) as f:
            advertencias = json.load(f).get("advertencias", [])

    hoy = datetime.now(ZoneInfo("America/Bogota")).date()
    md = [f"# Monitor Portuario Colombia — semana del {r['semana_analizada']}",
          f"*Generado automáticamente el {hoy}. Datos: IMF PortWatch "
          f"(estimados satelitales, rezago ~10 días; ver limitaciones abajo).*", ""]

    if advertencias:
        md += ["> **Advertencias de calidad de datos esta semana:**"]
        md += [f"> - {a}" for a in advertencias] + [""]

    for puerto, d in sorted(r["puertos"].items()):
        md += [linea_puerto(puerto, d), ""]

    md += ["---",
           "**Cómo leer este reporte.**"
           "- El *patrón esperado* es la mediana de las 13 semanas previas de cada puerto.",
           "- *z* mide la desviación de la semana en unidades robustas (mediana/MAD por puerto).",
           "- Se alerta por **caídas abruptas** (z ≤ −3) y por **caídas sostenidas** (CUSUM).",
           "- Las semanas festivas (fin/inicio de año) se reportan sin alertar.",
           "",
           "**Limitaciones.** Datos estimados por el IMF a partir de señales AIS; "
           "sujetos a revisión. Detección con 10–14 días de rezago: este monitor "
           "es analítico, no operativo. Cobertura: importaciones de Buenaventura, "
           "Cartagena, Barranquilla y Santa Marta.",
           "",
           f"*[Metodología y código](https://github.com/carlos-osorio/monitor-portuario)*"]

    texto = "\n".join(md)
    Path("reports").mkdir(exist_ok=True)
    (Path("reports") / f"{hoy}.md").write_text(texto, encoding="utf-8")
    (Path("reports") / "ultimo.md").write_text(texto, encoding="utf-8")
    print(f"Reporte escrito: reports/{hoy}.md y reports/ultimo.md")


if __name__ == "__main__":
    main()
