"""
exporter.py
Export session data to CSV or PDF report.
"""

import csv
import os
from datetime import datetime
from typing import List

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports")


def ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def export_csv(rows: List[dict], filename: str = None) -> str:
    ensure_reports_dir()
    if filename is None:
        filename = datetime.now().strftime("report_%Y%m%d_%H%M%S.csv")
    path = os.path.join(REPORTS_DIR, filename)
    if not rows:
        return path
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def export_pdf(rows: List[dict], session_name: str = "Session",
               filename: str = None, tags: list = None) -> str:
    """Generate a summary PDF report using reportlab."""
    ensure_reports_dir()
    if filename is None:
        filename = datetime.now().strftime("report_%Y%m%d_%H%M%S.pdf")
    path = os.path.join(REPORTS_DIR, filename)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )

        doc = SimpleDocTemplate(path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            "Title", parent=styles["Title"],
            textColor=colors.HexColor("#1a1a2e"),
            fontSize=22,
        )
        story.append(Paragraph("LightRoom Classic — Performance Report", title_style))
        story.append(Paragraph(f"Session: {session_name}", styles["Normal"]))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            styles["Normal"]
        ))
        story.append(Spacer(1, 0.3 * inch))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        story.append(Spacer(1, 0.2 * inch))

        if not rows:
            story.append(Paragraph("No data recorded.", styles["Normal"]))
        else:
            # Summary statistics
            lr_rows = [r for r in rows if r.get("lr_running")]
            total_samples = len(rows)
            lr_samples = len(lr_rows)
            duration_min = (rows[-1]["timestamp"] - rows[0]["timestamp"]) / 60

            def avg(key):
                vals = [r[key] for r in rows if r.get(key) is not None]
                return sum(vals) / len(vals) if vals else 0

            def peak(key):
                vals = [r[key] for r in rows if r.get(key) is not None]
                return max(vals) if vals else 0

            story.append(Paragraph("Summary", styles["Heading2"]))
            summary_data = [
                ["Metric", "Value"],
                ["Session Duration", f"{duration_min:.1f} minutes"],
                ["Total Samples", str(total_samples)],
                ["LR Running Samples", str(lr_samples)],
                ["Avg System CPU", f"{avg('sys_cpu_pct'):.1f}%"],
                ["Peak System CPU", f"{peak('sys_cpu_pct'):.1f}%"],
                ["Avg LR CPU", f"{avg('lr_cpu_pct'):.1f}%"],
                ["Peak LR CPU", f"{peak('lr_cpu_pct'):.1f}%"],
                ["Avg LR RAM", f"{avg('lr_ram_rss_mb'):.0f} MB"],
                ["Peak LR RAM", f"{peak('lr_ram_rss_mb'):.0f} MB"],
                ["Avg System RAM Used", f"{avg('sys_ram_used_mb'):.0f} MB"],
                ["Peak Disk Read", f"{peak('disk_read_bps') / 1e6:.1f} MB/s"],
                ["Peak Disk Write", f"{peak('disk_write_bps') / 1e6:.1f} MB/s"],
                ["Thermal Throttling Events", str(sum(1 for r in rows if r.get("throttling")))],
            ]

            t = Table(summary_data, colWidths=[3 * inch, 3 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d2d44")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(t)

            # Event tags section
            if tags:
                story.append(Spacer(1, 0.3 * inch))
                story.append(Paragraph("Tagged Events", styles["Heading2"]))
                tag_data = [["Time", "Operation", "Note"]]
                for tag in tags:
                    tag_data.append([tag.time_str, tag.operation.value, tag.note or "—"])
                tag_table = Table(tag_data, colWidths=[1.2 * inch, 2.2 * inch, 3 * inch])
                tag_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d2d44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]))
                story.append(tag_table)

        doc.build(story)

    except ImportError:
        # Fallback: write plain text if reportlab missing
        with open(path.replace(".pdf", ".txt"), "w") as f:
            f.write(f"LightRoom Classic Performance Report\n")
            f.write(f"Session: {session_name}\n")
            f.write(f"Samples: {len(rows)}\n")

    return path
