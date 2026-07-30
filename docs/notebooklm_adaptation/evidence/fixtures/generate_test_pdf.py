from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


OUTPUT = Path(__file__).with_name("notebooklm_benchmark_source.pdf")


def main() -> None:
    page_width, page_height = A4
    pdf = canvas.Canvas(str(OUTPUT), pagesize=A4)
    pdf.setTitle("Notebook Workspace Benchmark")

    pdf.setFillColor(HexColor("#16324F"))
    pdf.rect(0, page_height - 126, page_width, 126, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(48, page_height - 72, "Notebook Workspace Benchmark")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, page_height - 94, "Non-sensitive interaction test fixture")

    pdf.setFillColor(HexColor("#1F2937"))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(48, page_height - 174, "Operational brief")
    pdf.setFont("Helvetica", 11)
    lines = [
        "A calm notebook workspace should keep evidence, questions, and outputs",
        "visible without losing the user's current context.",
        "",
        "Key principles:",
        "1. Source selection must be explicit and reversible.",
        "2. Generated answers must link back to supporting evidence.",
        "3. Background processing must expose clear progress and safe failure states.",
        "4. Responsive layouts should preserve the primary question-and-answer flow.",
    ]
    y = page_height - 202
    for line in lines:
        pdf.drawString(48, y, line)
        y -= 20

    pdf.setStrokeColor(HexColor("#CBD5E1"))
    pdf.line(48, 88, page_width - 48, 88)
    pdf.setFillColor(HexColor("#64748B"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(48, 64, "Created solely for authorized NotebookLM UX research.")
    pdf.drawRightString(page_width - 48, 64, "Page 1")
    pdf.save()


if __name__ == "__main__":
    main()
