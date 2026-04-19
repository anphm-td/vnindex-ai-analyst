"""
VNINDEX AI Analyst - PDF Report Generator
Xuất báo cáo phân tích hàng ngày dạng PDF.
"""

import logging
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

import config

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Tạo báo cáo PDF hàng ngày."""

    def __init__(self):
        self.reports_dir = config.REPORTS_DIR

    def generate(self, macro_data: dict, tech_data: dict,
                 news_data: dict, risk_data: dict,
                 cio_decisions: dict) -> str:
        """Tạo PDF report và trả về đường dẫn file."""
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"VNINDEX_Report_{today}.pdf"
        filepath = self.reports_dir / filename

        logger.info(f"📄 Generating PDF report: {filepath}")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Trang 1: Tổng quan
        pdf.add_page()
        self._header(pdf, f"VNINDEX AI ANALYST - BÁO CÁO NGÀY {today}")

        # Market Assessment
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "1. DANH GIA THI TRUONG", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        assessment = cio_decisions.get("market_assessment", "Chua co du lieu")
        pdf.multi_cell(0, 6, self._safe_text(assessment))
        pdf.ln(5)

        risk_level = cio_decisions.get("risk_level", "N/A")
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"Muc rui ro: {self._safe_text(risk_level)}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        # Vĩ mô
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "2. DU LIEU VI MO", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        macro_lines = [
            f"DXY: {macro_data.get('dxy', 'N/A')}",
            f"US10Y: {macro_data.get('us10y', 'N/A')}%",
            f"USD/VND: {macro_data.get('usd_vnd', 'N/A')}",
            f"Bien dong ty gia: {macro_data.get('exchange_rate_change_pct', 'N/A')}%",
            f"Trang thai: {macro_data.get('status', 'N/A')}",
        ]
        for line in macro_lines:
            pdf.cell(0, 6, self._safe_text(line), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        # Market Breadth
        breadth = tech_data.get("market_breadth", {})
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "3. DO RONG THI TRUONG", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Tang: {breadth.get('advance', 0)} | Giam: {breadth.get('decline', 0)} | Khong doi: {breadth.get('unchanged', 0)}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Breadth Ratio: {breadth.get('ratio', 0):.4f}", new_x="LMARGIN", new_y="NEXT")
        if risk_data.get("keo_tru_warning"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 8, "CANH BAO: XANH VO DO LONG (KEO TRU)", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        # Trang 2: Khuyến nghị
        pdf.add_page()
        self._header(pdf, "KHUYEN NGHI DAU TU")

        decisions = cio_decisions.get("decisions", [])
        if decisions:
            # Table header
            pdf.set_font("Helvetica", "B", 9)
            col_widths = [20, 20, 60, 35, 30]
            headers = ["Ma", "K.Nghi", "Ly do", "Stop Loss", "Tin cay"]
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 8, h, border=1)
            pdf.ln()

            # Table rows
            pdf.set_font("Helvetica", "", 8)
            for dec in decisions:
                sym = dec.get("symbol", "N/A")
                rec = self._safe_text(dec.get("recommendation", "N/A"))
                reason = self._safe_text(dec.get("reasoning", ""))[:70]
                stop = dec.get("trailing_stop")
                stop_str = f"{stop:,.0f}" if stop else "N/A"
                conf = dec.get("confidence", 0)
                conf_str = f"{conf*100:.0f}%"

                pdf.cell(col_widths[0], 7, sym, border=1)
                pdf.cell(col_widths[1], 7, rec, border=1)
                pdf.cell(col_widths[2], 7, reason, border=1)
                pdf.cell(col_widths[3], 7, stop_str, border=1)
                pdf.cell(col_widths[4], 7, conf_str, border=1)
                pdf.ln()
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 10, "Khong co khuyen nghi hom nay.", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(10)

        # Tin tức Sentiment
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "TIN TUC & SENTIMENT", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Sentiment thi truong: {news_data.get('market_sentiment', 0):+.4f}", new_x="LMARGIN", new_y="NEXT")

        sentiments = news_data.get("symbol_sentiments", {})
        for sym, score in list(sentiments.items())[:15]:
            emoji = "+" if score > 0 else "-" if score < 0 else "="
            pdf.cell(0, 5, f"  {sym}: {score:+.4f} ({emoji})", new_x="LMARGIN", new_y="NEXT")

        # Trailing Stops
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "TRAILING STOP", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        stops = risk_data.get("trailing_stops", {})
        for sym, s in list(stops.items())[:15]:
            pdf.cell(0, 5,
                     f"  {sym}: Gia={s.get('current_price',0):,.0f} | "
                     f"Stop={s.get('stop_loss',0):,.0f} | "
                     f"Cach={s.get('distance_pct',0):.1f}%",
                     new_x="LMARGIN", new_y="NEXT")

        # Footer
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 5, f"Generated by VNINDEX AI Analyst v1.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, "Luu y: Day la phan tich tu dong, khong phai khuyen nghi dau tu chinh thuc.", new_x="LMARGIN", new_y="NEXT")

        # Save
        pdf.output(str(filepath))
        logger.info(f"📄 PDF saved: {filepath}")
        return str(filepath)

    def _header(self, pdf: FPDF, title: str):
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 15, self._safe_text(title), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_draw_color(0, 102, 204)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)

    @staticmethod
    def _safe_text(text: str) -> str:
        """Remove Vietnamese diacritics for PDF compatibility with built-in fonts."""
        if not text:
            return ""
        replacements = {
            'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
            'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
            'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
            'đ': 'd', 'Đ': 'D',
            'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
            'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
            'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
            'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
            'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
            'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
            'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
            'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
            'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        }
        for vn, ascii_char in replacements.items():
            text = text.replace(vn, ascii_char)
            text = text.replace(vn.upper(), ascii_char.upper())
        return text
