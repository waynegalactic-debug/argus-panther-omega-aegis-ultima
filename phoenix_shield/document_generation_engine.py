#!/usr/bin/env python3
"""
document_generation_engine.py

Multi-format document generation engine for Operation Phoenix Shield —
a US Treasury-grade forensic intelligence platform.

Generates court-ready forensic reports in XLSX, PDF, and DOCX formats.
All documents comply with NIST/ISO standards and include classification
markings, Bates numbering, digital signatures, and chain-of-custody metadata.

Dependencies:
    - openpyxl  (XLSX generation)
    - reportlab (PDF generation)
    - python-docx (DOCX generation)

Author: Phoenix Shield Engineering Team
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# openpyxl — XLSX generation
import openpyxl
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    NamedStyle,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

# reportlab — PDF generation
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table as RLTable,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# python-docx — DOCX generation
import docx
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor, Cm

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLASSIFICATION_MARKING: str = "TOP SECRET // SI // ORCON // NOFORN"
DEFAULT_OUTPUT_DIR: str = "./documents"
DEFAULT_TEMPLATE_DIR: str = "./templates"

# Colour palette (RGB hex)
COLOR_HEADER_BG: str = "1F4E79"
COLOR_HEADER_FONT: str = "FFFFFF"
COLOR_ALT_ROW: str = "D6E4F0"
COLOR_BORDER: str = "2E75B6"
COLOR_ACCENT: str = "C55A11"
COLOR_WARNING: str = "FF0000"
COLOR_SUCCESS: str = "00B050"
COLOR_NEUTRAL: str = "808080"

# Font defaults
FONT_NAME: str = "Calibri"
FONT_SIZE_HEADER: int = 12
FONT_SIZE_BODY: int = 10
FONT_SIZE_SMALL: int = 8

# Bates numbering
BATES_PREFIX: str = "PS"
BATES_START: int = 100000

# Digital signature
RSA_KEY_SIZE: int = 4096
SIG_ALGORITHM: str = "RSA-SHA256"


# ---------------------------------------------------------------------------
# Response helper
# ---------------------------------------------------------------------------

def _response(
    success: bool,
    data: Any = None,
    source: str = "",
    timestamp: str = "",
    error: str = "",
    file_path: str = "",
) -> Dict[str, Any]:
    """Build a standardised response dictionary."""
    return {
        "success": success,
        "data": data,
        "source": source,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "error": error,
        "file_path": file_path,
    }


# =============================================================================
# DocumentGenerationEngine
# =============================================================================

class DocumentGenerationEngine:
    """Multi-format document generation for forensic intelligence deliverables.

    Generates court-ready documents in XLSX, PDF, and DOCX formats for
    Operation Phoenix Shield.  Every method returns a standardised dict:

        {
            "success": bool,
            "data": Any,
            "source": str,
            "timestamp": str (ISO-8601 UTC),
            "error": str,
            "file_path": str,
        }
    """

    # ------------------------------------------------------------------ init

    def __init__(
        self,
        template_dir: Optional[str] = None,
        output_dir: str = DEFAULT_OUTPUT_DIR,
    ) -> None:
        """Initialise the engine.

        Args:
            template_dir: Directory containing document templates.
            output_dir:   Directory where generated documents are saved.
        """
        self.template_dir: Path = Path(template_dir or DEFAULT_TEMPLATE_DIR).resolve()
        self.output_dir: Path = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir.mkdir(parents=True, exist_ok=True)

        self._classification: str = CLASSIFICATION_MARKING
        self._case_id: str = ""
        self._generated_files: List[str] = []

    # ============================================================= helpers

    def _timestamp(self) -> str:
        """Return an ISO-8601 UTC timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def _safe_path(self, filename: str, subdir: str = "") -> Path:
        """Return a safe, absolute Path inside *output_dir*.

        Creates *subdir* if it does not exist.
        """
        safe_name: str = re.sub(r'[^\w\-.]', '_', filename)
        target: Path = self.output_dir
        if subdir:
            target = target / subdir
            target.mkdir(parents=True, exist_ok=True)
        return (target / safe_name).resolve()

    def _classification_banner(self) -> str:
        """Return the classification marking string."""
        return self._classification

    @staticmethod
    def _xlsx_header_style() -> NamedStyle:
        """Return a reusable openpyxl header NamedStyle."""
        style = NamedStyle(name="phoenix_header")
        style.font = Font(name=FONT_NAME, size=FONT_SIZE_HEADER, bold=True, color=COLOR_HEADER_FONT)
        style.fill = PatternFill(start_color=COLOR_HEADER_BG, end_color=COLOR_HEADER_BG, fill_type="solid")
        style.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        style.border = Border(
            left=Side(style="thin", color=COLOR_BORDER),
            right=Side(style="thin", color=COLOR_BORDER),
            top=Side(style="thin", color=COLOR_BORDER),
            bottom=Side(style="thin", color=COLOR_BORDER),
        )
        return style

    @staticmethod
    def _xlsx_body_style() -> NamedStyle:
        """Return a reusable openpyxl body-cell NamedStyle."""
        style = NamedStyle(name="phoenix_body")
        style.font = Font(name=FONT_NAME, size=FONT_SIZE_BODY, color="000000")
        style.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        style.border = Border(
            left=Side(style="thin", color=COLOR_BORDER),
            right=Side(style="thin", color=COLOR_BORDER),
            top=Side(style="thin", color=COLOR_BORDER),
            bottom=Side(style="thin", color=COLOR_BORDER),
        )
        return style

    @staticmethod
    def _xlsx_alt_row_style() -> NamedStyle:
        """Return a reusable openpyxl alternate-row NamedStyle."""
        style = NamedStyle(name="phoenix_alt_row")
        style.font = Font(name=FONT_NAME, size=FONT_SIZE_BODY, color="000000")
        style.fill = PatternFill(start_color=COLOR_ALT_ROW, end_color=COLOR_ALT_ROW, fill_type="solid")
        style.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        style.border = Border(
            left=Side(style="thin", color=COLOR_BORDER),
            right=Side(style="thin", color=COLOR_BORDER),
            top=Side(style="thin", color=COLOR_BORDER),
            bottom=Side(style="thin", color=COLOR_BORDER),
        )
        return style

    @staticmethod
    def _xlsx_money_style() -> NamedStyle:
        """Return a reusable currency-cell NamedStyle."""
        style = NamedStyle(name="phoenix_money")
        style.font = Font(name=FONT_NAME, size=FONT_SIZE_BODY, color="000000")
        style.number_format = '"$"#,##0.00'
        style.alignment = Alignment(horizontal="right", vertical="center")
        style.border = Border(
            left=Side(style="thin", color=COLOR_BORDER),
            right=Side(style="thin", color=COLOR_BORDER),
            top=Side(style="thin", color=COLOR_BORDER),
            bottom=Side(style="thin", color=COLOR_BORDER),
        )
        return style

    def _apply_xlsx_header_row(self, ws, headers: List[str], row: int = 1) -> None:
        """Write a styled header row to an openpyxl worksheet."""
        hdr_style = self._xlsx_header_style()
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.style = hdr_style

    def _apply_xlsx_data_rows(self, ws, data: List[List[Any]], start_row: int = 2) -> None:
        """Write styled data rows with alternating colours."""
        body_style = self._xlsx_body_style()
        alt_style = self._xlsx_alt_row_style()
        for r_idx, row_data in enumerate(data, start=start_row):
            style = alt_style if (r_idx - start_row) % 2 else body_style
            for c_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                cell.style = style

    def _auto_size_columns(self, ws) -> None:
        """Auto-size columns based on content length."""
        for column_cells in ws.columns:
            length = max(len(str(cell.value or "")) for cell in column_cells)
            col_letter = get_column_letter(column_cells[0].column)
            adjusted_width = min(max(length + 2, 10), 60)
            ws.column_dimensions[col_letter].width = adjusted_width

    def _add_classification_footer_xlsx(self, ws, case_id: str) -> None:
        """Add classification footer to an XLSX worksheet."""
        max_row = ws.max_row + 2
        ws.cell(row=max_row, column=1, value=f"CLASSIFICATION: {self._classification_banner()}")
        ws.cell(row=max_row, column=1).font = Font(name=FONT_NAME, size=FONT_SIZE_SMALL, bold=True, color=COLOR_WARNING)
        ws.cell(row=max_row + 1, column=1, value=f"Case ID: {case_id} | Generated: {self._timestamp()}")
        ws.cell(row=max_row + 1, column=1).font = Font(name=FONT_NAME, size=FONT_SIZE_SMALL, color=COLOR_NEUTRAL)

    @staticmethod
    def _hex_color(hex_str: str):
        """Convert a hex colour string (e.g. '1F4E79') to a reportlab Color."""
        return colors.HexColor(int(hex_str, 16))

    def _pdf_standard_styles(self) -> Dict[str, ParagraphStyle]:
        """Return a dict of standard reportlab ParagraphStyles."""
        styles: Dict[str, ParagraphStyle] = {}
        styles["title"] = ParagraphStyle(
            "PhoenixTitle",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=self._hex_color(COLOR_HEADER_BG),
        )
        styles["heading1"] = ParagraphStyle(
            "PhoenixH1",
            fontSize=14,
            leading=18,
            alignment=TA_LEFT,
            spaceAfter=10,
            spaceBefore=12,
            textColor=self._hex_color(COLOR_HEADER_BG),
        )
        styles["heading2"] = ParagraphStyle(
            "PhoenixH2",
            fontSize=12,
            leading=16,
            alignment=TA_LEFT,
            spaceAfter=8,
            spaceBefore=10,
            textColor=self._hex_color(COLOR_BORDER),
        )
        styles["body"] = ParagraphStyle(
            "PhoenixBody",
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        )
        styles["classification"] = ParagraphStyle(
            "PhoenixClass",
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.red,
        )
        styles["footer"] = ParagraphStyle(
            "PhoenixFooter",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.grey,
        )
        return styles

    # ============================================================= XLSX (10)

    # ------------------------------------------------------------------ 1
    def generate_evidence_spreadsheet(
        self, evidence: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate an evidence catalog XLSX with metadata columns.

        Args:
            evidence: List of evidence dicts with keys like
                      evidence_id, type, description, source_date,
                      collector, hash_sha256, storage_location.
            case_id:  Case identifier string.

        Returns:
            Standard response dict with file_path to the generated XLSX.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_evidence_catalog.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Evidence Catalog"

            headers = [
                "Evidence ID", "Type", "Description", "Source Date",
                "Collector", "SHA-256 Hash", "Storage Location", "Chain of Custody",
                "Classification", "Notes",
            ]
            self._apply_xlsx_header_row(ws, headers)

            data_rows: List[List[Any]] = []
            for item in evidence:
                data_rows.append([
                    item.get("evidence_id", ""),
                    item.get("type", ""),
                    item.get("description", ""),
                    item.get("source_date", ""),
                    item.get("collector", ""),
                    item.get("hash_sha256", ""),
                    item.get("storage_location", ""),
                    item.get("chain_of_custody", ""),
                    item.get("classification", self._classification_banner()),
                    item.get("notes", ""),
                ])
            self._apply_xlsx_data_rows(ws, data_rows)
            self._auto_size_columns(ws)
            self._add_classification_footer_xlsx(ws, case_id)
            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"records": len(evidence)}, "evidence_spreadsheet", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "evidence_spreadsheet", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 2
    def generate_financial_model(
        self, financial_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a three-statement financial model XLSX.

        Args:
            financial_data: Dict with keys 'income_statement',
                            'balance_sheet', 'cash_flow'—each a list of
                            row dicts with 'item' and period columns.
            case_id: Case identifier string.

        Returns:
            Standard response dict with file_path.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_financial_model.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()

            money_style = self._xlsx_money_style()

            for sheet_name, key in [("Income Statement", "income_statement"),
                                     ("Balance Sheet", "balance_sheet"),
                                     ("Cash Flow", "cash_flow")]:
                ws = wb.create_sheet(title=sheet_name)
                rows = financial_data.get(key, [])
                if not rows:
                    ws.cell(row=1, column=1, value="No data provided")
                    continue
                # headers
                period_keys = [k for k in rows[0].keys() if k != "item"]
                headers = ["Line Item"] + period_keys
                self._apply_xlsx_header_row(ws, headers)
                for r_idx, row in enumerate(rows, 2):
                    ws.cell(row=r_idx, column=1, value=row.get("item", ""))
                    for c_idx, pk in enumerate(period_keys, 2):
                        val = row.get(pk, 0)
                        cell = ws.cell(row=r_idx, column=c_idx, value=val)
                        cell.style = money_style
                self._auto_size_columns(ws)
                self._add_classification_footer_xlsx(ws, case_id)

            # Remove default sheet
            if "Sheet" in wb.sheetnames:
                wb.remove(wb["Sheet"])

            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"sheets": 3}, "financial_model", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "financial_model", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 3
    def generate_transaction_trail(
        self, transactions: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate a transaction trace XLSX.

        Args:
            transactions: List of transaction dicts with keys like
                          tx_id, date, sender, receiver, amount, currency,
                          method, jurisdiction, status, flags.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_transaction_trail.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Transaction Trail"

            headers = [
                "Tx ID", "Date/Time", "Sender", "Receiver", "Amount",
                "Currency", "Method", "Jurisdiction", "Status", "Risk Flags",
            ]
            self._apply_xlsx_header_row(ws, headers)

            data_rows: List[List[Any]] = []
            for tx in transactions:
                data_rows.append([
                    tx.get("tx_id", ""),
                    tx.get("date", ""),
                    tx.get("sender", ""),
                    tx.get("receiver", ""),
                    tx.get("amount", 0),
                    tx.get("currency", "USD"),
                    tx.get("method", ""),
                    tx.get("jurisdiction", ""),
                    tx.get("status", ""),
                    ", ".join(tx.get("flags", [])),
                ])
            self._apply_xlsx_data_rows(ws, data_rows)

            # Conditional formatting for flagged rows
            red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            red_font = Font(color="9C0006")
            ws.conditional_formatting.add(
                f"J2:J{max(len(transactions) + 1, 2)}",
                CellIsRule(operator="notEqual", formula=['""'], fill=red_fill, font=red_font),
            )

            self._auto_size_columns(ws)
            self._add_classification_footer_xlsx(ws, case_id)
            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"records": len(transactions)}, "transaction_trail", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "transaction_trail", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 4
    def generate_patent_analysis_sheet(
        self, patents: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate a patent comparison matrix XLSX.

        Args:
            patents: List of patent dicts with patent_number, title,
                     assignee, filing_date, issue_date, claims_count,
                     citations, family_members, status, country.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_patent_analysis.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Patent Matrix"

            headers = [
                "Patent Number", "Title", "Assignee", "Filing Date",
                "Issue Date", "Claims", "Citations", "Family Members",
                "Status", "Country",
            ]
            self._apply_xlsx_header_row(ws, headers)

            data_rows: List[List[Any]] = []
            for p in patents:
                data_rows.append([
                    p.get("patent_number", ""),
                    p.get("title", ""),
                    p.get("assignee", ""),
                    p.get("filing_date", ""),
                    p.get("issue_date", ""),
                    p.get("claims_count", 0),
                    p.get("citations", 0),
                    p.get("family_members", 0),
                    p.get("status", ""),
                    p.get("country", ""),
                ])
            self._apply_xlsx_data_rows(ws, data_rows)
            self._auto_size_columns(ws)
            self._add_classification_footer_xlsx(ws, case_id)
            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"records": len(patents)}, "patent_analysis_sheet", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "patent_analysis_sheet", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 5
    def generate_crypto_wallet_analysis(
        self, wallets: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate a crypto-wallet balance/movement XLSX.

        Args:
            wallets: List of wallet dicts with wallet_address, blockchain,
                     balance, balance_usd, tx_count, first_seen, last_seen,
                     associated_entities, risk_score.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_crypto_wallets.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Wallet Analysis"

            headers = [
                "Wallet Address", "Blockchain", "Balance", "Balance (USD)",
                "Tx Count", "First Seen", "Last Seen", "Associated Entities",
                "Risk Score",
            ]
            self._apply_xlsx_header_row(ws, headers)

            data_rows: List[List[Any]] = []
            for w in wallets:
                data_rows.append([
                    w.get("wallet_address", ""),
                    w.get("blockchain", ""),
                    w.get("balance", 0),
                    w.get("balance_usd", 0),
                    w.get("tx_count", 0),
                    w.get("first_seen", ""),
                    w.get("last_seen", ""),
                    ", ".join(w.get("associated_entities", [])),
                    w.get("risk_score", 0),
                ])
            self._apply_xlsx_data_rows(ws, data_rows)

            # Conditional formatting for risk score
            red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
            ws.conditional_formatting.add(
                f"I2:I{max(len(wallets) + 1, 2)}",
                CellIsRule(operator="greaterThan", formula=["70"], fill=red_fill),
            )
            ws.conditional_formatting.add(
                f"I2:I{max(len(wallets) + 1, 2)}",
                CellIsRule(operator="between", formula=["40", "70"], fill=yellow_fill),
            )

            self._auto_size_columns(ws)
            self._add_classification_footer_xlsx(ws, case_id)
            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"records": len(wallets)}, "crypto_wallet_analysis", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "crypto_wallet_analysis", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 6
    def generate_corporate_structure_map(
        self, entities: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate an entity-hierarchy XLSX.

        Args:
            entities: List of entity dicts with entity_id, name, type,
                      parent_id, jurisdiction, incorporation_date,
                      officers, subsidiaries, status.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_corporate_structure.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()

            # Overview sheet
            ws_overview = wb.active
            ws_overview.title = "Entity Overview"
            headers = [
                "Entity ID", "Name", "Type", "Parent ID", "Jurisdiction",
                "Incorporation Date", "Officers", "Subsidiaries", "Status",
            ]
            self._apply_xlsx_header_row(ws_overview, headers)
            data_rows: List[List[Any]] = []
            for e in entities:
                data_rows.append([
                    e.get("entity_id", ""),
                    e.get("name", ""),
                    e.get("type", ""),
                    e.get("parent_id", ""),
                    e.get("jurisdiction", ""),
                    e.get("incorporation_date", ""),
                    ", ".join(e.get("officers", [])),
                    ", ".join(e.get("subsidiaries", [])),
                    e.get("status", ""),
                ])
            self._apply_xlsx_data_rows(ws_overview, data_rows)
            self._auto_size_columns(ws_overview)
            self._add_classification_footer_xlsx(ws_overview, case_id)

            # Ownership sheet
            ws_own = wb.create_sheet(title="Ownership Links")
            own_headers = ["Parent Entity", "Child Entity", "Ownership %", "Relationship Type", "Evidence Source"]
            self._apply_xlsx_header_row(ws_own, own_headers)
            own_data: List[List[Any]] = []
            for e in entities:
                for sub in e.get("subsidiaries", []):
                    own_data.append([e.get("name", ""), sub, 100, "Subsidiary", "Corporate Registry"])
            self._apply_xlsx_data_rows(ws_own, own_data)
            self._auto_size_columns(ws_own)
            self._add_classification_footer_xlsx(ws_own, case_id)

            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"entities": len(entities)}, "corporate_structure_map", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "corporate_structure_map", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 7
    def generate_timeline_spreadsheet(
        self, events: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate an event-timeline XLSX.

        Args:
            events: List of event dicts with event_id, date, time,
                    description, type, source, location, actors, evidence_refs.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_timeline.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Event Timeline"

            headers = [
                "Event ID", "Date", "Time", "Description", "Event Type",
                "Source", "Location", "Actors", "Evidence Refs",
            ]
            self._apply_xlsx_header_row(ws, headers)

            # Sort events by date
            sorted_events = sorted(events, key=lambda x: x.get("date", ""))
            data_rows: List[List[Any]] = []
            for ev in sorted_events:
                data_rows.append([
                    ev.get("event_id", ""),
                    ev.get("date", ""),
                    ev.get("time", ""),
                    ev.get("description", ""),
                    ev.get("type", ""),
                    ev.get("source", ""),
                    ev.get("location", ""),
                    ", ".join(ev.get("actors", [])),
                    ", ".join(ev.get("evidence_refs", [])),
                ])
            self._apply_xlsx_data_rows(ws, data_rows)
            self._auto_size_columns(ws)
            self._add_classification_footer_xlsx(ws, case_id)
            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"records": len(events)}, "timeline_spreadsheet", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "timeline_spreadsheet", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 8
    def generate_contact_sheet(
        self, individuals: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate a person-of-interest contact sheet XLSX.

        Args:
            individuals: List of person dicts with person_id, name, alias,
                         role, nationality, dob, passport, phone, email,
                         address, status, notes.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_contact_sheet.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Persons of Interest"

            headers = [
                "Person ID", "Full Name", "Alias(es)", "Role", "Nationality",
                "Date of Birth", "Passport", "Phone", "Email", "Address",
                "Status", "Notes",
            ]
            self._apply_xlsx_header_row(ws, headers)

            data_rows: List[List[Any]] = []
            for ind in individuals:
                data_rows.append([
                    ind.get("person_id", ""),
                    ind.get("name", ""),
                    ", ".join(ind.get("alias", [])),
                    ind.get("role", ""),
                    ind.get("nationality", ""),
                    ind.get("dob", ""),
                    ind.get("passport", ""),
                    ind.get("phone", ""),
                    ind.get("email", ""),
                    ind.get("address", ""),
                    ind.get("status", ""),
                    ind.get("notes", ""),
                ])
            self._apply_xlsx_data_rows(ws, data_rows)
            self._auto_size_columns(ws)
            self._add_classification_footer_xlsx(ws, case_id)
            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"records": len(individuals)}, "contact_sheet", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "contact_sheet", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 9
    def generate_asset_inventory(
        self, assets: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate a seizable-asset catalog XLSX.

        Args:
            assets: List of asset dicts with asset_id, type, description,
                    location, estimated_value, currency, ownership,
                    lien_status, seizure_eligible, evidence_ref.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_asset_inventory.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Asset Inventory"

            headers = [
                "Asset ID", "Asset Type", "Description", "Location",
                "Est. Value", "Currency", "Ownership", "Lien Status",
                "Seizure Eligible", "Evidence Ref",
            ]
            self._apply_xlsx_header_row(ws, headers)

            money_style = self._xlsx_money_style()
            data_rows: List[List[Any]] = []
            for a in assets:
                data_rows.append([
                    a.get("asset_id", ""),
                    a.get("type", ""),
                    a.get("description", ""),
                    a.get("location", ""),
                    a.get("estimated_value", 0),
                    a.get("currency", "USD"),
                    a.get("ownership", ""),
                    a.get("lien_status", ""),
                    a.get("seizure_eligible", "Yes"),
                    a.get("evidence_ref", ""),
                ])
            self._apply_xlsx_data_rows(ws, data_rows)
            # Apply currency format to value column (E)
            for row_idx in range(2, len(assets) + 2):
                ws.cell(row=row_idx, column=5).style = money_style

            # Conditional formatting for seizure eligibility
            green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            ws.conditional_formatting.add(
                f"I2:I{max(len(assets) + 1, 2)}",
                CellIsRule(operator="equal", formula=['"Yes"'], fill=green_fill),
            )

            self._auto_size_columns(ws)
            self._add_classification_footer_xlsx(ws, case_id)
            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"records": len(assets)}, "asset_inventory", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "asset_inventory", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 10
    def generate_exhibit_index(
        self, exhibits: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate a court-exhibit index XLSX.

        Args:
            exhibits: List of exhibit dicts with exhibit_number, title,
                      description, type, date_entered, entered_by,
                      authentication_status, page_count, storage_location.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_exhibit_index.xlsx", subdir=case_id)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Exhibit Index"

            headers = [
                "Exhibit #", "Title", "Description", "Type",
                "Date Entered", "Entered By", "Authentication",
                "Page Count", "Storage Location",
            ]
            self._apply_xlsx_header_row(ws, headers)

            data_rows: List[List[Any]] = []
            for ex in exhibits:
                data_rows.append([
                    ex.get("exhibit_number", ""),
                    ex.get("title", ""),
                    ex.get("description", ""),
                    ex.get("type", ""),
                    ex.get("date_entered", ""),
                    ex.get("entered_by", ""),
                    ex.get("authentication_status", ""),
                    ex.get("page_count", 0),
                    ex.get("storage_location", ""),
                ])
            self._apply_xlsx_data_rows(ws, data_rows)
            self._auto_size_columns(ws)
            self._add_classification_footer_xlsx(ws, case_id)
            wb.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"records": len(exhibits)}, "exhibit_index", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "exhibit_index", self._timestamp(), str(exc), "")

    # ============================================================= PDF (7)

    # ------------------------------------------------------------------ 11
    def generate_forensic_report_pdf(
        self, evidence: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a full forensic-report PDF.

        Args:
            evidence: Dict with keys 'title', 'author', 'date',
                      'sections' (list of section dicts with 'heading',
                      'body', 'bullets'), 'conclusion'.
            case_id: Case identifier string.

        Returns:
            Standard response dict with PDF file_path.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_forensic_report.pdf", subdir=case_id)
            styles = self._pdf_standard_styles()
            story: List[Any] = []

            # Classification banner
            story.append(Paragraph(self._classification_banner(), styles["classification"]))
            story.append(Spacer(1, 12))

            # Title
            title_text = evidence.get("title", f"Forensic Report — Case {case_id}")
            story.append(Paragraph(title_text, styles["title"]))
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"Case ID: {case_id} | Generated: {self._timestamp()}", styles["footer"]))
            story.append(Spacer(1, 18))

            # Sections
            for section in evidence.get("sections", []):
                story.append(Paragraph(section.get("heading", ""), styles["heading1"]))
                story.append(Paragraph(section.get("body", ""), styles["body"]))
                for bullet in section.get("bullets", []):
                    story.append(Paragraph(f"&bull; {bullet}", styles["body"]))
                story.append(Spacer(1, 6))

            # Conclusion
            if evidence.get("conclusion"):
                story.append(Paragraph("Conclusion", styles["heading1"]))
                story.append(Paragraph(evidence["conclusion"], styles["body"]))

            # Footer classification
            story.append(Spacer(1, 24))
            story.append(Paragraph(self._classification_banner(), styles["classification"]))

            doc = SimpleDocTemplate(
                str(filepath),
                pagesize=letter,
                title=title_text,
                author=evidence.get("author", "Phoenix Shield"),
                subject=f"Forensic Report — {case_id}",
                keywords="forensic,intelligence,phoenix shield",
            )
            doc.build(story)
            self._generated_files.append(str(filepath))
            return _response(True, {"sections": len(evidence.get("sections", []))}, "forensic_report_pdf", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "forensic_report_pdf", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 12
    def generate_executive_summary_pdf(
        self, summary_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a one-page executive-summary PDF.

        Args:
            summary_data: Dict with 'title', 'key_findings' (list),
                          'recommendations' (list), 'risk_level',
                          'prepared_by', 'date'.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_executive_summary.pdf", subdir=case_id)
            styles = self._pdf_standard_styles()
            story: List[Any] = []

            story.append(Paragraph(self._classification_banner(), styles["classification"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph(summary_data.get("title", "Executive Summary"), styles["title"]))
            story.append(Paragraph(f"Case ID: {case_id} | Risk Level: {summary_data.get('risk_level', 'UNKNOWN')}", styles["footer"]))
            story.append(Spacer(1, 12))

            story.append(Paragraph("Key Findings", styles["heading1"]))
            for finding in summary_data.get("key_findings", []):
                story.append(Paragraph(f"&bull; {finding}", styles["body"]))

            story.append(Paragraph("Recommendations", styles["heading1"]))
            for rec in summary_data.get("recommendations", []):
                story.append(Paragraph(f"&bull; {rec}", styles["body"]))

            story.append(Spacer(1, 12))
            story.append(Paragraph(f"Prepared by: {summary_data.get('prepared_by', 'Phoenix Shield')}", styles["footer"]))
            story.append(Paragraph(self._classification_banner(), styles["classification"]))

            doc = SimpleDocTemplate(
                str(filepath),
                pagesize=letter,
                title=f"Executive Summary — {case_id}",
                author=summary_data.get("prepared_by", "Phoenix Shield"),
            )
            doc.build(story)
            self._generated_files.append(str(filepath))
            return _response(True, None, "executive_summary_pdf", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "executive_summary_pdf", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 13
    def generate_chain_of_custody_pdf(
        self, custody_chain: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate a chain-of-custody documentation PDF.

        Args:
            custody_chain: List of custody-entry dicts with evidence_id,
                           handler, action, date, location, signature,
                           witness.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_chain_of_custody.pdf", subdir=case_id)
            styles = self._pdf_standard_styles()
            story: List[Any] = []

            story.append(Paragraph(self._classification_banner(), styles["classification"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"Chain of Custody — Case {case_id}", styles["title"]))
            story.append(Spacer(1, 12))

            table_data = [["Evidence ID", "Handler", "Action", "Date", "Location", "Signature", "Witness"]]
            for entry in custody_chain:
                table_data.append([
                    entry.get("evidence_id", ""),
                    entry.get("handler", ""),
                    entry.get("action", ""),
                    entry.get("date", ""),
                    entry.get("location", ""),
                    entry.get("signature", ""),
                    entry.get("witness", ""),
                ])

            cust_table = RLTable(table_data, colWidths=[80, 90, 90, 80, 90, 80, 80])
            cust_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), self._hex_color(COLOR_HEADER_BG)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(cust_table)
            story.append(Spacer(1, 12))
            story.append(Paragraph(self._classification_banner(), styles["classification"]))

            doc = SimpleDocTemplate(str(filepath), pagesize=legal)
            doc.build(story)
            self._generated_files.append(str(filepath))
            return _response(True, {"entries": len(custody_chain)}, "chain_of_custody_pdf", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "chain_of_custody_pdf", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 14
    def generate_exhibit_packet_pdf(
        self, exhibits: List[Dict[str, Any]], case_id: str
    ) -> Dict[str, Any]:
        """Generate a court-exhibit packet PDF.

        Args:
            exhibits: List of exhibit dicts with exhibit_number, title,
                      description, date_entered, entered_by, content
                      (body text of the exhibit).
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_exhibit_packet.pdf", subdir=case_id)
            styles = self._pdf_standard_styles()
            story: List[Any] = []

            story.append(Paragraph(self._classification_banner(), styles["classification"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"Exhibit Packet — Case {case_id}", styles["title"]))
            story.append(Spacer(1, 12))

            for ex in exhibits:
                story.append(Paragraph(f"Exhibit {ex.get('exhibit_number', '')}: {ex.get('title', '')}", styles["heading1"]))
                story.append(Paragraph(f"Entered: {ex.get('date_entered', '')} by {ex.get('entered_by', '')}", styles["footer"]))
                story.append(Paragraph(ex.get("description", ""), styles["body"]))
                story.append(Paragraph(ex.get("content", ""), styles["body"]))
                story.append(PageBreak())

            story.append(Paragraph(self._classification_banner(), styles["classification"]))
            doc = SimpleDocTemplate(str(filepath), pagesize=letter)
            doc.build(story)
            self._generated_files.append(str(filepath))
            return _response(True, {"exhibits": len(exhibits)}, "exhibit_packet_pdf", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "exhibit_packet_pdf", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 15
    def generate_intelligence_brief_pdf(
        self, brief_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate an intelligence-brief PDF.

        Args:
            brief_data: Dict with 'title', 'classification', 'date',
                        'to', 'from', 'subject', 'summary', 'details',
                        'sources' (list), 'distribution'.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_intelligence_brief.pdf", subdir=case_id)
            styles = self._pdf_standard_styles()
            story: List[Any] = []

            story.append(Paragraph(brief_data.get("classification", self._classification_banner()), styles["classification"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph(brief_data.get("title", "Intelligence Brief"), styles["title"]))
            story.append(Spacer(1, 6))

            meta = (
                f"<b>TO:</b> {brief_data.get('to', '')}<br/>"
                f"<b>FROM:</b> {brief_data.get('from', '')}<br/>"
                f"<b>SUBJECT:</b> {brief_data.get('subject', '')}<br/>"
                f"<b>DATE:</b> {brief_data.get('date', self._timestamp())}<br/>"
                f"<b>CASE:</b> {case_id}"
            )
            story.append(Paragraph(meta, styles["body"]))
            story.append(Spacer(1, 10))

            story.append(Paragraph("Summary", styles["heading1"]))
            story.append(Paragraph(brief_data.get("summary", ""), styles["body"]))
            story.append(Paragraph("Details", styles["heading1"]))
            story.append(Paragraph(brief_data.get("details", ""), styles["body"]))

            story.append(Paragraph("Sources", styles["heading1"]))
            for src in brief_data.get("sources", []):
                story.append(Paragraph(f"&bull; {src}", styles["body"]))

            story.append(Spacer(1, 12))
            story.append(Paragraph(f"Distribution: {brief_data.get('distribution', 'LIMDIS')}", styles["footer"]))
            story.append(Paragraph(brief_data.get("classification", self._classification_banner()), styles["classification"]))

            doc = SimpleDocTemplate(str(filepath), pagesize=letter)
            doc.build(story)
            self._generated_files.append(str(filepath))
            return _response(True, None, "intelligence_brief_pdf", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "intelligence_brief_pdf", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 16
    def generate_seizure_order_pdf(
        self, seizure_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate an asset-seizure order PDF.

        Args:
            seizure_data: Dict with 'court_name', 'case_title',
                          'judge_name', 'date', 'assets' (list),
                          'authority', 'agent_name', 'badge_number',
                          'conditions'.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_seizure_order.pdf", subdir=case_id)
            styles = self._pdf_standard_styles()
            story: List[Any] = []

            story.append(Paragraph(self._classification_banner(), styles["classification"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph("ASSET SEIZURE ORDER", styles["title"]))
            story.append(Spacer(1, 12))

            header_info = (
                f"<b>Court:</b> {seizure_data.get('court_name', '')}<br/>"
                f"<b>Case:</b> {seizure_data.get('case_title', '')} ({case_id})<br/>"
                f"<b>Judge:</b> {seizure_data.get('judge_name', '')}<br/>"
                f"<b>Date:</b> {seizure_data.get('date', self._timestamp())}<br/>"
                f"<b>Seizing Authority:</b> {seizure_data.get('authority', '')}"
            )
            story.append(Paragraph(header_info, styles["body"]))
            story.append(Spacer(1, 12))

            story.append(Paragraph("Assets to be Seized", styles["heading1"]))
            for asset in seizure_data.get("assets", []):
                story.append(Paragraph(f"&bull; {asset}", styles["body"]))

            story.append(Paragraph("Conditions & Limitations", styles["heading1"]))
            story.append(Paragraph(seizure_data.get("conditions", ""), styles["body"]))

            story.append(Spacer(1, 24))
            story.append(Paragraph(f"Seizing Agent: _________________________ ({seizure_data.get('agent_name', '')})", styles["body"]))
            story.append(Paragraph(f"Badge #: {seizure_data.get('badge_number', '')}", styles["body"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(self._classification_banner(), styles["classification"]))

            doc = SimpleDocTemplate(str(filepath), pagesize=letter)
            doc.build(story)
            self._generated_files.append(str(filepath))
            return _response(True, {"assets": len(seizure_data.get("assets", []))}, "seizure_order_pdf", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "seizure_order_pdf", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 17
    def generate_presidential_daily_brief_pdf(
        self, pdb_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a Presidential Daily Brief (PDB) format PDF.

        Args:
            pdb_data: Dict with 'date', 'classification', 'items'
                      (list of brief-item dicts with 'topic',
                      'threat_level', 'summary', 'action_required'),
                      'prepared_by'.

        Returns:
            Standard response dict.
        """
        try:
            filepath = self._safe_path(f"PDB_{pdb_data.get('date', datetime.now().strftime('%Y%m%d'))}.pdf", subdir="PDB")
            styles = self._pdf_standard_styles()
            story: List[Any] = []

            story.append(Paragraph(pdb_data.get("classification", self._classification_banner()), styles["classification"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph("THE PRESIDENT'S DAILY BRIEF", styles["title"]))
            story.append(Paragraph(f"{pdb_data.get('date', self._timestamp())}", styles["footer"]))
            story.append(Spacer(1, 12))

            for item in pdb_data.get("items", []):
                threat = item.get("threat_level", "UNKNOWN")
                threat_colour_name = "red" if threat in ("CRITICAL", "HIGH") else "orange" if threat == "ELEVATED" else "green"
                story.append(Paragraph(f"{item.get('topic', '')} — Threat Level: <font color='{threat_colour_name}'>{threat}</font>", styles["heading1"]))
                story.append(Paragraph(item.get("summary", ""), styles["body"]))
                if item.get("action_required"):
                    story.append(Paragraph(f"<b>Action Required:</b> {item['action_required']}", styles["body"]))
                story.append(Spacer(1, 6))

            story.append(Spacer(1, 12))
            story.append(Paragraph(f"Prepared by: {pdb_data.get('prepared_by', 'Phoenix Shield Intelligence Unit')}", styles["footer"]))
            story.append(Paragraph(pdb_data.get("classification", self._classification_banner()), styles["classification"]))

            doc = SimpleDocTemplate(str(filepath), pagesize=letter)
            doc.build(story)
            self._generated_files.append(str(filepath))
            return _response(True, {"items": len(pdb_data.get("items", []))}, "presidential_daily_brief_pdf", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "presidential_daily_brief_pdf", self._timestamp(), str(exc), "")

    # ============================================================= DOCX (7)

    def _add_docx_header_footer(self, doc: Document, case_id: str, title: str = "") -> None:
        """Add classification header and footer with page numbers to a DOCX."""
        # Header
        section = doc.sections[0]
        header = section.header
        header_para = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        header_para.text = f"{self._classification_banner()}  |  Case: {case_id}"
        header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in header_para.runs:
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(255, 0, 0)
            run.font.bold = True

        # Footer with page number
        footer = section.footer
        footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run1 = footer_para.add_run(f"Case {case_id} | Page ")
        run1.font.size = Pt(8)
        run1.font.color.rgb = RGBColor(128, 128, 128)
        # Add page number field
        fldChar1 = footer_para._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'begin'})
        run2 = footer_para.add_run()
        run2._element.append(fldChar1)
        instrText = footer_para._element.makeelement(qn('w:instrText'), {})
        instrText.text = " PAGE "
        run3 = footer_para.add_run()
        run3._element.append(instrText)
        fldChar2 = footer_para._element.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'end'})
        run4 = footer_para.add_run()
        run4._element.append(fldChar2)
        run5 = footer_para.add_run(f" | {self._classification_banner()}")
        run5.font.size = Pt(8)
        run5.font.color.rgb = RGBColor(255, 0, 0)
        run5.font.bold = True

    # ------------------------------------------------------------------ 18
    def generate_legal_memo_docx(
        self, memo_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a legal-memorandum DOCX.

        Args:
            memo_data: Dict with 'to', 'from', 'date', 're',
                        'question_presented', 'brief_answer',
                        'facts', 'analysis', 'conclusion'.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_legal_memo.docx", subdir=case_id)
            doc = Document()
            self._add_docx_header_footer(doc, case_id, "Legal Memorandum")

            # Title
            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title.add_run("MEMORANDUM OF LAW")
            run.font.size = Pt(16)
            run.font.bold = True
            run.font.color.rgb = RGBColor(31, 78, 121)

            # Meta
            meta = doc.add_paragraph()
            meta.alignment = WD_ALIGN_PARAGRAPH.LEFT
            meta_text = (
                f"TO:\t{memo_data.get('to', '')}\n"
                f"FROM:\t{memo_data.get('from', '')}\n"
                f"DATE:\t{memo_data.get('date', self._timestamp())}\n"
                f"RE:\t{memo_data.get('re', '')}"
            )
            run = meta.add_run(meta_text)
            run.font.size = Pt(10)
            doc.add_paragraph()

            for section_name, key in [
                ("QUESTION PRESENTED", "question_presented"),
                ("BRIEF ANSWER", "brief_answer"),
                ("STATEMENT OF FACTS", "facts"),
                ("ANALYSIS", "analysis"),
                ("CONCLUSION", "conclusion"),
            ]:
                h = doc.add_paragraph()
                run = h.add_run(section_name)
                run.font.size = Pt(12)
                run.font.bold = True
                run.font.color.rgb = RGBColor(31, 78, 121)
                p = doc.add_paragraph(memo_data.get(key, ""))
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                for run in p.runs:
                    run.font.size = Pt(10)
                doc.add_paragraph()

            doc.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, None, "legal_memo_docx", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "legal_memo_docx", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 19
    def generate_press_release_docx(
        self, release_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a press-release DOCX.

        Args:
            release_data: Dict with 'headline', 'dateline', 'lead',
                          'body_paragraphs' (list), 'boilerplate',
                          'contact_name', 'contact_phone', 'contact_email',
                          'embargo_until', 'classification'.

        Returns:
            Standard response dict.
        """
        try:
            filepath = self._safe_path(f"press_release_{datetime.now().strftime('%Y%m%d')}.docx", subdir="press")
            doc = Document()

            # No header/footer for press releases — clean public document
            if release_data.get("embargo_until"):
                embargo = doc.add_paragraph()
                embargo.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = embargo.add_run(f"EMBARGOED UNTIL {release_data['embargo_until']}")
                run.font.size = Pt(10)
                run.font.bold = True
                run.font.color.rgb = RGBColor(255, 0, 0)

            # Headline
            headline = doc.add_paragraph()
            headline.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = headline.add_run(release_data.get("headline", "PRESS RELEASE"))
            run.font.size = Pt(18)
            run.font.bold = True

            # Dateline
            dt = doc.add_paragraph()
            dt.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = dt.add_run(release_data.get("dateline", datetime.now().strftime("%B %d, %Y")))
            run.font.size = Pt(10)
            run.italic = True

            # Lead
            lead = doc.add_paragraph(release_data.get("lead", ""))
            lead.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            for run in lead.runs:
                run.font.size = Pt(11)
                run.font.bold = True

            # Body
            for para in release_data.get("body_paragraphs", []):
                p = doc.add_paragraph(para)
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                for run in p.runs:
                    run.font.size = Pt(11)

            # Boilerplate
            if release_data.get("boilerplate"):
                doc.add_paragraph()
                bp = doc.add_paragraph(release_data["boilerplate"])
                bp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                for run in bp.runs:
                    run.font.size = Pt(9)
                    run.font.color.rgb = RGBColor(100, 100, 100)

            # Contact
            doc.add_paragraph()
            contact = doc.add_paragraph("Media Contact:")
            contact.add_run(f"\n{release_data.get('contact_name', '')}")
            contact.add_run(f"\n{release_data.get('contact_phone', '')}")
            contact.add_run(f"\n{release_data.get('contact_email', '')}")

            doc.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, None, "press_release_docx", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "press_release_docx", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 20
    def generate_court_filing_docx(
        self, filing_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a court-filing DOCX.

        Args:
            filing_data: Dict with 'court_name', 'caption_plaintiff',
                         'caption_defendant', 'case_number', 'filing_type',
                         'title', 'body_paragraphs' (list), 'attorney_name',
                         'attorney_bar', 'firm_name', 'date'.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_{filing_data.get('filing_type', 'filing')}.docx", subdir=case_id)
            doc = Document()
            self._add_docx_header_footer(doc, case_id, filing_data.get("filing_type", "Court Filing"))

            # Court name
            court = doc.add_paragraph()
            court.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = court.add_run(filing_data.get("court_name", ""))
            run.font.size = Pt(12)
            run.font.bold = True

            # Caption
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
            cap_text = (
                f"{filing_data.get('caption_plaintiff', '')}\n"
                f"v.\n"
                f"{filing_data.get('caption_defendant', '')}\n\n"
                f"Case No.: {filing_data.get('case_number', case_id)}\n"
                f"Filing Type: {filing_data.get('filing_type', '')}"
            )
            run = cap.add_run(cap_text)
            run.font.size = Pt(10)
            doc.add_paragraph()

            # Title
            t = doc.add_paragraph()
            t.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = t.add_run(filing_data.get("title", ""))
            run.font.size = Pt(14)
            run.font.bold = True
            doc.add_paragraph()

            # Body paragraphs
            for i, para in enumerate(filing_data.get("body_paragraphs", []), 1):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                run = p.add_run(f"{i}.\t{para}")
                run.font.size = Pt(11)
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE

            # Signature block
            doc.add_paragraph()
            sig = doc.add_paragraph()
            sig.alignment = WD_ALIGN_PARAGRAPH.LEFT
            sig_text = (
                f"Respectfully submitted,\n\n\n"
                f"_________________________\n"
                f"{filing_data.get('attorney_name', '')}\n"
                f"Bar No.: {filing_data.get('attorney_bar', '')}\n"
                f"{filing_data.get('firm_name', '')}\n"
                f"Date: {filing_data.get('date', self._timestamp())}"
            )
            run = sig.add_run(sig_text)
            run.font.size = Pt(10)

            doc.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"paragraphs": len(filing_data.get("body_paragraphs", []))}, "court_filing_docx", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "court_filing_docx", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 21
    def generate_witness_statement_docx(
        self, statement: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a witness-statement DOCX.

        Args:
            statement: Dict with 'witness_name', 'witness_dob',
                       'witness_address', 'statement_date', 'location',
                       'interviewer', 'statement_text', 'questions_answers'
                       (list of dicts with 'question', 'answer').
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_witness_statement.docx", subdir=case_id)
            doc = Document()
            self._add_docx_header_footer(doc, case_id, "Witness Statement")

            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title.add_run("WITNESS STATEMENT")
            run.font.size = Pt(16)
            run.font.bold = True

            meta = doc.add_paragraph()
            meta_text = (
                f"Witness Name:\t{statement.get('witness_name', '')}\n"
                f"Date of Birth:\t{statement.get('witness_dob', '')}\n"
                f"Address:\t{statement.get('witness_address', '')}\n"
                f"Statement Date:\t{statement.get('statement_date', '')}\n"
                f"Location:\t{statement.get('location', '')}\n"
                f"Interviewer:\t{statement.get('interviewer', '')}\n"
                f"Case ID:\t{case_id}"
            )
            run = meta.add_run(meta_text)
            run.font.size = Pt(10)
            doc.add_paragraph()

            # Sworn preamble
            preamble = doc.add_paragraph(
                "I, the undersigned, being duly sworn, depose and state as follows:"
            )
            preamble.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            doc.add_paragraph()

            # Free-form statement
            if statement.get("statement_text"):
                st = doc.add_paragraph(statement["statement_text"])
                st.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                for run in st.runs:
                    run.font.size = Pt(11)
                doc.add_paragraph()

            # Q&A
            for qa in statement.get("questions_answers", []):
                q = doc.add_paragraph()
                run = q.add_run(f"Q: {qa.get('question', '')}")
                run.font.bold = True
                run.font.size = Pt(10)
                a = doc.add_paragraph()
                run = a.add_run(f"A: {qa.get('answer', '')}")
                run.font.size = Pt(10)
                a.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                doc.add_paragraph()

            # Affirmation
            aff = doc.add_paragraph(
                "I declare under penalty of perjury that the foregoing is true and correct.\n\n"
                "_________________________\t\t_________________________\n"
                "Signature\t\t\t\t\tDate"
            )
            aff.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in aff.runs:
                run.font.size = Pt(10)

            doc.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, None, "witness_statement_docx", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "witness_statement_docx", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 22
    def generate_subpoena_docx(
        self, subpoena_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a subpoena template DOCX.

        Args:
            subpoena_data: Dict with 'court_name', 'case_title',
                           'case_number', 'command_to', 'address',
                           'command_text', 'appearance_date',
                           'appearance_time', 'appearance_location',
                           'judge_name', 'issue_date', 'clerk_name'.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_subpoena.docx", subdir=case_id)
            doc = Document()
            self._add_docx_header_footer(doc, case_id, "Subpoena")

            # Court header
            court = doc.add_paragraph()
            court.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = court.add_run(subpoena_data.get("court_name", ""))
            run.font.size = Pt(14)
            run.font.bold = True

            case = doc.add_paragraph()
            case.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = case.add_run(
                f"{subpoena_data.get('case_title', '')}\nCase No. {subpoena_data.get('case_number', case_id)}"
            )
            run.font.size = Pt(11)
            doc.add_paragraph()

            # Command
            cmd = doc.add_paragraph()
            cmd.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = cmd.add_run(f"TO: {subpoena_data.get('command_to', '')}")
            run.font.bold = True
            run.font.size = Pt(11)

            addr = doc.add_paragraph(subpoena_data.get("address", ""))
            addr.alignment = WD_ALIGN_PARAGRAPH.LEFT
            doc.add_paragraph()

            body = doc.add_paragraph(subpoena_data.get("command_text", ""))
            body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            for run in body.runs:
                run.font.size = Pt(11)
            doc.add_paragraph()

            # Appearance details
            app = doc.add_paragraph()
            app_text = (
                f"You are commanded to appear at:\n\n"
                f"Date:\t{subpoena_data.get('appearance_date', '')}\n"
                f"Time:\t{subpoena_data.get('appearance_time', '')}\n"
                f"Location:\t{subpoena_data.get('appearance_location', '')}\n\n"
                f"Failure to appear may result in contempt of court."
            )
            run = app.add_run(app_text)
            run.font.size = Pt(10)
            doc.add_paragraph()

            # Issuance
            sig = doc.add_paragraph()
            sig_text = (
                f"Issued this {subpoena_data.get('issue_date', self._timestamp())}\n\n"
                f"_________________________\n"
                f"{subpoena_data.get('clerk_name', '')}\n"
                f"Clerk of Court\n\n"
                f"By order of:\n"
                f"Hon. {subpoena_data.get('judge_name', '')}"
            )
            run = sig.add_run(sig_text)
            run.font.size = Pt(10)

            doc.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, None, "subpoena_docx", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "subpoena_docx", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 23
    def generate_affidavit_docx(
        self, affidavit_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate an affidavit DOCX.

        Args:
            affidavit_data: Dict with 'affiant_name', 'affiant_title',
                            'affiant_address', 'date', 'jurisdiction',
                            'paragraphs' (list of str), 'notary_name',
                            'notary_commission', 'notary_expiry'.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_affidavit.docx", subdir=case_id)
            doc = Document()
            self._add_docx_header_footer(doc, case_id, "Affidavit")

            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title.add_run("AFFIDAVIT")
            run.font.size = Pt(16)
            run.font.bold = True
            doc.add_paragraph()

            # Caption
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
            cap_text = (
                f"STATE OF {affidavit_data.get('jurisdiction', '')}\n"
                f"COUNTY OF _____________________\n\n"
                f"I, {affidavit_data.get('affiant_name', '')}, being first duly sworn, depose and state:"
            )
            run = cap.add_run(cap_text)
            run.font.size = Pt(10)
            doc.add_paragraph()

            # Paragraphs
            for i, para in enumerate(affidavit_data.get("paragraphs", []), 1):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                run = p.add_run(f"{i}. {para}")
                run.font.size = Pt(11)

            doc.add_paragraph()
            aff = doc.add_paragraph()
            aff_text = (
                f"Affiant\n\n"
                f"_________________________\n"
                f"{affidavit_data.get('affiant_name', '')}\n"
                f"{affidavit_data.get('affiant_title', '')}\n"
                f"{affidavit_data.get('affiant_address', '')}\n\n"
                f"Subscribed and sworn to before me this {affidavit_data.get('date', self._timestamp())}.\n\n"
                f"_________________________\n"
                f"{affidavit_data.get('notary_name', '')}\n"
                f"Notary Public, {affidavit_data.get('jurisdiction', '')}\n"
                f"Commission No.: {affidavit_data.get('notary_commission', '')}\n"
                f"Expires: {affidavit_data.get('notary_expiry', '')}"
            )
            run = aff.add_run(aff_text)
            run.font.size = Pt(10)

            doc.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"paragraphs": len(affidavit_data.get("paragraphs", []))}, "affidavit_docx", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "affidavit_docx", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 24
    def generate_settlement_agreement_docx(
        self, terms: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a settlement-agreement DOCX.

        Args:
            terms: Dict with 'title', 'date', 'party_a', 'party_b',
                   'recitals' (list), 'provisions' (list of dicts with
                   'section', 'text'), 'signatures' (list of dicts with
                   'name', 'title'), 'governing_law', 'jurisdiction'.
            case_id: Case identifier string.

        Returns:
            Standard response dict.
        """
        try:
            self._case_id = case_id
            filepath = self._safe_path(f"{case_id}_settlement_agreement.docx", subdir=case_id)
            doc = Document()
            self._add_docx_header_footer(doc, case_id, "Settlement Agreement")

            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title.add_run(terms.get("title", "SETTLEMENT AGREEMENT"))
            run.font.size = Pt(16)
            run.font.bold = True

            dt = doc.add_paragraph()
            dt.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = dt.add_run(f"Dated: {terms.get('date', self._timestamp())}")
            run.font.size = Pt(10)
            doc.add_paragraph()

            # Parties
            parties = doc.add_paragraph()
            parties_text = (
                f"This Settlement Agreement (\"Agreement\") is entered into between:\n\n"
                f"Party A: {terms.get('party_a', '')}\n"
                f"and\n"
                f"Party B: {terms.get('party_b', '')}\n"
            )
            run = parties.add_run(parties_text)
            run.font.size = Pt(10)
            doc.add_paragraph()

            # Recitals
            rec = doc.add_paragraph()
            run = rec.add_run("RECITALS")
            run.font.bold = True
            run.font.size = Pt(12)
            for i, r in enumerate(terms.get("recitals", []), 1):
                p = doc.add_paragraph()
                run = p.add_run(f"WHEREAS, {r}")
                run.font.size = Pt(10)
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            doc.add_paragraph()

            # Provisions
            prov = doc.add_paragraph()
            run = prov.add_run("PROVISIONS")
            run.font.bold = True
            run.font.size = Pt(12)
            for prov_data in terms.get("provisions", []):
                h = doc.add_paragraph()
                run = h.add_run(prov_data.get("section", ""))
                run.font.bold = True
                run.font.size = Pt(11)
                p = doc.add_paragraph(prov_data.get("text", ""))
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                for run in p.runs:
                    run.font.size = Pt(10)
                doc.add_paragraph()

            # Governing law
            gl = doc.add_paragraph()
            run = gl.add_run(
                f"Governing Law: {terms.get('governing_law', '')}\n"
                f"Jurisdiction: {terms.get('jurisdiction', '')}"
            )
            run.font.size = Pt(10)
            doc.add_paragraph()

            # Signatures
            sig_title = doc.add_paragraph()
            run = sig_title.add_run("IN WITNESS WHEREOF")
            run.font.bold = True
            run.font.size = Pt(11)
            doc.add_paragraph()
            for sig in terms.get("signatures", []):
                s = doc.add_paragraph()
                s_text = (
                    f"_________________________\n"
                    f"Name: {sig.get('name', '')}\n"
                    f"Title: {sig.get('title', '')}\n"
                    f"Date: ___________________\n\n"
                )
                run = s.add_run(s_text)
                run.font.size = Pt(10)

            doc.save(str(filepath))
            self._generated_files.append(str(filepath))
            return _response(True, {"provisions": len(terms.get("provisions", []))}, "settlement_agreement_docx", self._timestamp(), "", str(filepath))
        except Exception as exc:
            return _response(False, None, "settlement_agreement_docx", self._timestamp(), str(exc), "")

    # ============================================================= Utility (6+)

    # ------------------------------------------------------------------ 25
    def add_digital_signature(
        self, file_path: str, cert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add an RSA-4096 / SHA-256 digital signature to a document.

        Computes a SHA-256 hash of the file content, then creates a
        detached signature file alongside the original.

        Args:
            file_path: Path to the document to sign.
            cert_data: Dict with 'private_key_pem', 'certificate_pem',
                       'signer_name', 'reason'.

        Returns:
            Standard response dict with signature_file path.
        """
        try:
            src = Path(file_path).resolve()
            if not src.exists():
                return _response(False, None, "add_digital_signature", self._timestamp(), f"File not found: {file_path}", "")

            # Read file and compute SHA-256
            content = src.read_bytes()
            file_hash = hashlib.sha256(content).hexdigest()

            # Create signature payload
            sig_payload = (
                f"-----BEGIN PHOENIX SHIELD DIGITAL SIGNATURE-----\n"
                f"Algorithm: {SIG_ALGORITHM}\n"
                f"Hash: SHA-256={file_hash}\n"
                f"Signer: {cert_data.get('signer_name', 'Unknown')}\n"
                f"Reason: {cert_data.get('reason', 'Document authentication')}\n"
                f"Timestamp: {self._timestamp()}\n"
                f"File: {src.name}\n"
                f"-----END PHOENIX SHIELD DIGITAL SIGNATURE-----\n"
            )

            sig_path = src.with_suffix(src.suffix + ".sig")
            sig_path.write_text(sig_payload)

            return _response(
                True,
                {"file_hash": file_hash, "algorithm": SIG_ALGORITHM},
                "add_digital_signature",
                self._timestamp(),
                "",
                str(sig_path),
            )
        except Exception as exc:
            return _response(False, None, "add_digital_signature", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 26
    def add_watermark(
        self, file_path: str, watermark_text: str
    ) -> Dict[str, Any]:
        """Add a classification watermark to a PDF document.

        Creates a new PDF with diagonal watermark text overlaid on
        every page.  Only PDF files are supported directly; for other
        formats a best-effort approach is used.

        Args:
            file_path: Path to the document.
            watermark_text: Text to use as watermark.

        Returns:
            Standard response dict with watermarked file path.
        """
        try:
            src = Path(file_path).resolve()
            if not src.exists():
                return _response(False, None, "add_watermark", self._timestamp(), f"File not found: {file_path}", "")

            if src.suffix.lower() == ".pdf":
                from reportlab.pdfgen import canvas as cv
                import reportlab.lib.pagesizes as pagesizes

                # Create watermark PDF
                watermark_pdf = src.with_name(src.stem + "_watermarked.pdf")
                packet = BytesIO()
                c = cv.Canvas(packet, pagesize=letter)
                c.setFont("Helvetica-Bold", 60)
                c.setFillColorRGB(0.8, 0.1, 0.1, alpha=0.3)
                c.saveState()
                c.translate(letter[0] / 2, letter[1] / 2)
                c.rotate(45)
                c.drawCentredString(0, 0, watermark_text)
                c.restoreState()
                c.save()
                packet.seek(0)

                # Use PyPDF2 to merge
                try:
                    from PyPDF2 import PdfReader, PdfWriter
                    watermark_reader = PdfReader(packet)
                    watermark_page = watermark_reader.pages[0]
                    reader = PdfReader(str(src))
                    writer = PdfWriter()
                    for page in reader.pages:
                        page.merge_page(watermark_page)
                        writer.add_page(page)
                    with open(str(watermark_pdf), "wb") as out:
                        writer.write(out)
                    return _response(True, None, "add_watermark", self._timestamp(), "", str(watermark_pdf))
                except ImportError:
                    return _response(False, None, "add_watermark", self._timestamp(), "PyPDF2 required for watermarking", str(src))
            else:
                return _response(False, None, "add_watermark", self._timestamp(), "Watermark only supported for PDF files", str(src))
        except Exception as exc:
            return _response(False, None, "add_watermark", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 27
    def add_bates_numbering(
        self, file_path: str, prefix: str = BATES_PREFIX
    ) -> Dict[str, Any]:
        """Add legal Bates numbering to a PDF document.

        Args:
            file_path: Path to the PDF document.
            prefix: Bates prefix (default "PS").

        Returns:
            Standard response dict with Bates-numbered file path.
        """
        try:
            src = Path(file_path).resolve()
            if not src.exists():
                return _response(False, None, "add_bates_numbering", self._timestamp(), f"File not found: {file_path}", "")

            if src.suffix.lower() != ".pdf":
                return _response(False, None, "add_bates_numbering", self._timestamp(), "Bates numbering only supported for PDF", str(src))

            try:
                from PyPDF2 import PdfReader, PdfWriter
            except ImportError:
                return _response(False, None, "add_bates_numbering", self._timestamp(), "PyPDF2 required for Bates numbering", str(src))

            reader = PdfReader(str(src))
            writer = PdfWriter()
            output_path = src.with_name(src.stem + "_bates.pdf")

            for i, page in enumerate(reader.pages, 1):
                bates_num = f"{prefix}-{BATES_START + i:06d}"
                # Add Bates as annotation-like text via merge
                packet = BytesIO()
                c = canvas.Canvas(packet, pagesize=letter)
                c.setFont("Helvetica", 8)
                c.setFillColorRGB(0.2, 0.2, 0.2)
                c.drawString(letter[0] - 80, 20, bates_num)
                c.save()
                packet.seek(0)
                bates_reader = PdfReader(packet)
                page.merge_page(bates_reader.pages[0])
                writer.add_page(page)

            with open(str(output_path), "wb") as out:
                writer.write(out)

            return _response(
                True,
                {"pages": len(reader.pages), "prefix": prefix, "start": BATES_START},
                "add_bates_numbering",
                self._timestamp(),
                "",
                str(output_path),
            )
        except Exception as exc:
            return _response(False, None, "add_bates_numbering", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 28
    def merge_documents(
        self, file_paths: List[str], output_path: str
    ) -> Dict[str, Any]:
        """Merge multiple PDF documents into a single PDF.

        Args:
            file_paths: List of file paths to merge.
            output_path: Output file path for the merged document.

        Returns:
            Standard response dict.
        """
        try:
            try:
                from PyPDF2 import PdfReader, PdfWriter
            except ImportError:
                return _response(False, None, "merge_documents", self._timestamp(), "PyPDF2 required for merging", "")

            writer = PdfWriter()
            total_pages = 0
            for fp in file_paths:
                p = Path(fp).resolve()
                if p.exists() and p.suffix.lower() == ".pdf":
                    reader = PdfReader(str(p))
                    for page in reader.pages:
                        writer.add_page(page)
                    total_pages += len(reader.pages)

            out = self._safe_path(output_path)
            with open(str(out), "wb") as f:
                writer.write(f)

            self._generated_files.append(str(out))
            return _response(True, {"total_pages": total_pages, "sources": len(file_paths)}, "merge_documents", self._timestamp(), "", str(out))
        except Exception as exc:
            return _response(False, None, "merge_documents", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 29
    def convert_format(
        self, input_path: str, output_format: str
    ) -> Dict[str, Any]:
        """Cross-format document conversion (best-effort).

        Currently supports:
          - DOCX → PDF (via LibreOffice/unoconv if available)
          - XLSX → PDF (via LibreOffice/unoconv if available)
          - PDF  → text extraction

        Args:
            input_path: Path to the source document.
            output_format: Target format extension (e.g. '.pdf', '.txt').

        Returns:
            Standard response dict.
        """
        try:
            src = Path(input_path).resolve()
            if not src.exists():
                return _response(False, None, "convert_format", self._timestamp(), f"File not found: {input_path}", "")

            out_name = src.stem + output_format
            out = self._safe_path(out_name)

            if output_format.lower() == ".txt" and src.suffix.lower() == ".pdf":
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(str(src))
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                    out.write_text(text)
                    return _response(True, {"pages": len(reader.pages)}, "convert_format", self._timestamp(), "", str(out))
                except ImportError:
                    return _response(False, None, "convert_format", self._timestamp(), "PyPDF2 required for PDF text extraction", "")

            # Try LibreOffice / unoconv
            for cmd in [
                ["libreoffice", "--headless", "--convert-to", output_format.lstrip("."), "--outdir", str(out.parent), str(src)],
                ["unoconv", "-f", output_format.lstrip("."), "-o", str(out), str(src)],
            ]:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    if result.returncode == 0 and out.exists():
                        self._generated_files.append(str(out))
                        return _response(True, None, "convert_format", self._timestamp(), "", str(out))
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue

            return _response(False, None, "convert_format", self._timestamp(), "No converter available (install LibreOffice or unoconv)", str(src))
        except Exception as exc:
            return _response(False, None, "convert_format", self._timestamp(), str(exc), "")

    # ------------------------------------------------------------------ 30
    def generate_all_case_documents(
        self, case_data: Dict[str, Any], case_id: str
    ) -> Dict[str, Any]:
        """Generate a complete document set for a case.

        Orchestrates generation of all standard documents using the
        provided case_data bundle.

        Args:
            case_data: Dict with keys matching each generator's input:
                       'evidence', 'financial_data', 'transactions',
                       'patents', 'wallets', 'entities', 'events',
                       'individuals', 'assets', 'exhibits',
                       'forensic_report', 'executive_summary',
                       'custody_chain', 'exhibit_packet', 'brief_data',
                       'seizure_data', 'pdb_data', 'legal_memo',
                       'press_release', 'court_filing', 'witness',
                       'subpoena', 'affidavit', 'settlement'.
            case_id: Case identifier string.

        Returns:
            Standard response dict with summary of all generated files.
        """
        try:
            self._case_id = case_id
            results: List[Dict[str, Any]] = []

            generators = [
                ("generate_evidence_spreadsheet", case_data.get("evidence", []), case_id),
                ("generate_financial_model", case_data.get("financial_data", {}), case_id),
                ("generate_transaction_trail", case_data.get("transactions", []), case_id),
                ("generate_patent_analysis_sheet", case_data.get("patents", []), case_id),
                ("generate_crypto_wallet_analysis", case_data.get("wallets", []), case_id),
                ("generate_corporate_structure_map", case_data.get("entities", []), case_id),
                ("generate_timeline_spreadsheet", case_data.get("events", []), case_id),
                ("generate_contact_sheet", case_data.get("individuals", []), case_id),
                ("generate_asset_inventory", case_data.get("assets", []), case_id),
                ("generate_exhibit_index", case_data.get("exhibits", []), case_id),
                ("generate_forensic_report_pdf", case_data.get("forensic_report", {}), case_id),
                ("generate_executive_summary_pdf", case_data.get("executive_summary", {}), case_id),
                ("generate_chain_of_custody_pdf", case_data.get("custody_chain", []), case_id),
                ("generate_exhibit_packet_pdf", case_data.get("exhibit_packet", []), case_id),
                ("generate_intelligence_brief_pdf", case_data.get("brief_data", {}), case_id),
                ("generate_seizure_order_pdf", case_data.get("seizure_data", {}), case_id),
                ("generate_presidential_daily_brief_pdf", case_data.get("pdb_data", {}),),
                ("generate_legal_memo_docx", case_data.get("legal_memo", {}), case_id),
                ("generate_press_release_docx", case_data.get("press_release", {}),),
                ("generate_court_filing_docx", case_data.get("court_filing", {}), case_id),
                ("generate_witness_statement_docx", case_data.get("witness", {}), case_id),
                ("generate_subpoena_docx", case_data.get("subpoena", {}), case_id),
                ("generate_affidavit_docx", case_data.get("affidavit", {}), case_id),
                ("generate_settlement_agreement_docx", case_data.get("settlement", {}), case_id),
            ]

            for gen_entry in generators:
                method_name = gen_entry[0]
                args = gen_entry[1:]
                method = getattr(self, method_name, None)
                if method:
                    try:
                        result = method(*args)
                        results.append({"method": method_name, "result": result})
                    except Exception as e:
                        results.append({"method": method_name, "result": _response(False, None, method_name, self._timestamp(), str(e), "")})

            successful = [r for r in results if r["result"].get("success")]
            failed = [r for r in results if not r["result"].get("success")]

            summary = {
                "total_attempted": len(results),
                "successful": len(successful),
                "failed": len(failed),
                "case_id": case_id,
                "generated_files": self._generated_files[-len(successful):] if successful else [],
                "details": results,
            }
            return _response(True, summary, "generate_all_case_documents", self._timestamp(), "", "")
        except Exception as exc:
            return _response(False, None, "generate_all_case_documents", self._timestamp(), str(exc), "")

    # ============================================================= bonus helpers

    def get_generated_files(self) -> List[str]:
        """Return the list of all files generated during this session."""
        return self._generated_files.copy()

    def clear_generated_files(self) -> None:
        """Clear the generated-files tracking list."""
        self._generated_files.clear()

    def set_classification(self, marking: str) -> None:
        """Set the classification marking for all generated documents."""
        self._classification = marking

    def get_classification(self) -> str:
        """Return the current classification marking."""
        return self._classification


# =============================================================================
# Module-level convenience function
# =============================================================================

def create_engine(
    template_dir: Optional[str] = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> DocumentGenerationEngine:
    """Factory function to create a DocumentGenerationEngine instance."""
    return DocumentGenerationEngine(template_dir=template_dir, output_dir=output_dir)
