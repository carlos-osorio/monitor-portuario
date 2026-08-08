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
    partes = [f"**{nombre}** — {ESTADOS[d['episodio']['estado']]}"]

    # Importaciones en lenguaje llano
    tendencia = describir_desviacion(desv)
    partes.append(f"Importaciones: {d['import_semana']:,.0f} ton — {tendencia}")

    if "export_semana" in d:
        desv_e = 100 * (d["export_semana"] - d["export_baseline"]) / d["export_baseline"]
        partes.append(f"Exportaciones: {d['export_semana']:,.0f} ton — "
                      f"{describir_desviacion(desv_e)}")

    # Señales, ya en lenguaje humano
    ep = d["episodio"]
    if ep["estado"] == "en_curso":
        partes.append(f"Por debajo de lo habitual desde {ep['inicio']} "
                      f"({ep['semanas']} semanas seguidas)")
    if ep["estado"] == "cierre":
        partes.append("Volvió a niveles normales esta semana")
    if d.get("choque_caida"):
        partes.append("Caída fuerte y repentina esta semana")
    if d.get("nota_subida"):
        partes.append("Semana inusualmente alta")
    if d.get("alerta_piso"):
        partes.append("Importaciones en su nivel más bajo de los últimos años")
    if d.get("export_alerta_piso"):
        partes.append("Exportaciones en su nivel más bajo de los últimos años")

    return "  \n".join(partes)


def describir_desviacion(pct):
    """Traduce la desviación vs. patrón a lenguaje llano."""
    a = abs(pct)
    if a < 5:
        return "en línea con lo habitual"
    direccion = "por encima" if pct > 0 else "por debajo"
    if a < 20:
        return f"{a:.0f}% {direccion} de lo habitual"
    return f"{a:.0f}% {direccion} de lo habitual para el puerto"


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
           "**Nota metodológica.** \"Lo habitual\" es el nivel típico "
           "de cada puerto en las últimas 13 semanas. Una semana se marca como "
           "inusual cuando se aparta de ese nivel más de lo que el propio puerto "
           "suele variar (medida robusta de dispersión por puerto; detalle técnico "
           "y código en el repositorio). Se distinguen caídas abruptas de una "
           "semana y descensos sostenidos de varias. Las semanas de fin y comienzo "
           "de año se reportan sin marcar por su estacionalidad.",
           ""
           ]

    texto = "\n".join(md)
    Path("reports").mkdir(exist_ok=True)
    (Path("reports") / f"{hoy}.md").write_text(texto, encoding="utf-8")
    (Path("reports") / "ultimo.md").write_text(texto, encoding="utf-8")
    print(f"Reporte escrito: reports/{hoy}.md y reports/ultimo.md")

    # Versión web: index.html en la raíz, para GitHub Pages
    try:
        import markdown
        cuerpo = markdown.markdown(texto, extensions=["tables"])
    except ImportError:
        cuerpo = f"<pre>{texto}</pre>"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitor portuario — Colombia</title>
<style>
  body {{ max-width: 820px; margin: 2rem auto; padding: 0 1rem;
          font-family: system-ui, -apple-system, sans-serif; line-height: 1.55; color: #222; }}
  h1 {{ font-size: 1.5rem; }}
  strong {{ font-weight: 600; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 1.5rem 0; }}
  blockquote {{ border-left: 3px solid #e67e22; margin: 1rem 0; padding: 0.3rem 0 0.3rem 1rem;
                color: #663; background: #fdf6ec; }}
  em {{ color: #666; }}
</style>
</head>
<body>
{cuerpo}
</body>
</html>"""
    Path("index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
