"""PDF report generation for research outputs."""

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)


class PDFReportGenerator:
    """Generates professional PDF reports from research data."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self.styles["Heading1"],
            fontSize=24,
            spaceAfter=20,
            textColor=colors.HexColor("#1a1a2e"),
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading2"],
            fontSize=16,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor("#16213e"),
        ))
        self.styles.add(ParagraphStyle(
            name="SubHeader",
            parent=self.styles["Heading3"],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=5,
        ))
        self.styles.add(ParagraphStyle(
            name="BodyText2",
            parent=self.styles["BodyText"],
            fontSize=10,
            spaceAfter=6,
            leading=14,
        ))

    def generate_research_report(self, research_data: dict) -> bytes:
        """Generate a research report PDF and return bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=72, leftMargin=72,
            topMargin=72, bottomMargin=72,
        )

        story = []

        # Title
        company = research_data.get("company", {})
        ticker = company.get("ticker", "N/A")
        name = company.get("name", "Unknown Company")
        story.append(Paragraph(f"Research Report: {name} ({ticker})", self.styles["ReportTitle"]))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%B %d, %Y')} | "
            f"Sector: {company.get('sector', 'N/A')}",
            self.styles["BodyText2"],
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e")))
        story.append(Spacer(1, 20))

        # Executive Summary
        summary = company.get("research_summary", "No research summary available.")
        story.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))
        story.append(Paragraph(summary, self.styles["BodyText2"]))
        story.append(Spacer(1, 15))

        # Key Metrics Table
        fundamentals = company.get("fundamentals", {})
        if fundamentals:
            story.append(Paragraph("Key Financial Metrics", self.styles["SectionHeader"]))
            table_data = [["Metric", "Value"]]
            important_keys = [
                ("pe_ratio", "P/E Ratio"), ("forward_pe", "Forward P/E"),
                ("price_to_book", "Price/Book"), ("ev_to_ebitda", "EV/EBITDA"),
                ("profit_margin", "Profit Margin"), ("roe", "ROE"),
                ("debt_to_equity", "Debt/Equity"), ("revenue_growth", "Revenue Growth"),
            ]
            for key, label in important_keys:
                value = fundamentals.get(key)
                if value is not None:
                    if isinstance(value, float) and abs(value) < 1:
                        formatted = f"{value:.2%}"
                    elif isinstance(value, float):
                        formatted = f"{value:.2f}"
                    else:
                        formatted = str(value)
                    table_data.append([label, formatted])

            if len(table_data) > 1:
                table = Table(table_data, colWidths=[200, 200])
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                    ("TOPPADDING", (0, 0), (-1, 0), 10),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ]))
                story.append(table)
                story.append(Spacer(1, 15))

        # Filings
        filings = research_data.get("filings", [])
        if filings:
            story.append(Paragraph("SEC Filings Analyzed", self.styles["SectionHeader"]))
            for filing in filings[:5]:
                story.append(Paragraph(
                    f"<b>{filing.get('type', 'N/A')}</b> — Filed: {filing.get('date', 'N/A')}",
                    self.styles["SubHeader"],
                ))
                if filing.get("summary"):
                    story.append(Paragraph(filing["summary"][:500], self.styles["BodyText2"]))
            story.append(Spacer(1, 15))

        # Strategies
        strategies = research_data.get("strategies", [])
        if strategies:
            story.append(Paragraph("Strategy Recommendations", self.styles["SectionHeader"]))
            for strat in strategies[:3]:
                story.append(Paragraph(
                    f"<b>{strat.get('name', 'N/A')}</b> — {strat.get('recommendation', 'N/A')} "
                    f"(Confidence: {strat.get('confidence', 'N/A')}%)",
                    self.styles["SubHeader"],
                ))
                if strat.get("rationale"):
                    story.append(Paragraph(strat["rationale"][:800], self.styles["BodyText2"]))

        # Disclaimer
        story.append(Spacer(1, 30))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        story.append(Paragraph(
            "<i>Disclaimer: This report is generated by an AI system for research purposes only. "
            "It does not constitute financial advice. Always consult a qualified financial advisor "
            "before making investment decisions.</i>",
            self.styles["BodyText2"],
        ))

        doc.build(story)
        return buffer.getvalue()
