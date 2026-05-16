"""Barebones PDF export from an existing analysis final_report dict (requires fpdf2)."""

from datetime import datetime
import os

from fpdf import FPDF


def _safe(text) -> str:
    """Keep PDF text compatible with built-in Helvetica (latin-1)."""
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def _section(pdf: FPDF, title: str, body: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, _safe(body))
    pdf.ln(3)


def build_report_pdf(report: dict, input_url: str, image_path: str | None = None) -> bytes:
    """
    Build a PDF from the same fields shown in the Streamlit UI.
    No extra API calls — only aggregates existing final_report data.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "GeoInference Enhancement Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 6, _safe(f"URL: {input_url}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _safe(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if image_path and os.path.isfile(image_path):
        try:
            pdf.image(image_path, w=90)
            pdf.ln(6)
        except Exception:
            pass

    key_info = report.get("key_information", {})
    _section(
        pdf,
        "Best Guess",
        f"{key_info.get('best_guess', '')}\n\n{key_info.get('confidence_summary', '')}",
    )

    lines = []
    for guess in report.get("location_guesses", []):
        lat, lon = guess["coordinates"][0], guess["coordinates"][1]
        conf = guess.get("confidence", "")
        lines.append(
            f"#{guess.get('rank', '')} {guess.get('location_name', '')} "
            f"({lat}, {lon}) — confidence: {conf}"
        )
    _section(pdf, "Location Guesses", "\n".join(lines) if lines else "None")

    _section(pdf, "Conflict Analysis", report.get("conflict_analysis", ""))
    _section(pdf, "Full Report", report.get("full_report", ""))

    return bytes(pdf.output())
