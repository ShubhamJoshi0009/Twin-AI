"""Supply Chain Report Generator engine.

Generates downloadable PDF reports for supply chain operations.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.config import settings
from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.supply_chain.models.database import (
    InventoryItem,
    Shipment,
    Supplier,
    SupplyChainAlert,
    SupplyChainRisk,
    Warehouse,
)
from business_twin_ai.supply_chain.prompts.templates import (
    SC_REPORT_SUMMARY_SYSTEM,
    SC_REPORT_SUMMARY_USER,
    format_prompt,
)
from business_twin_ai.supply_chain.schemas.schemas import (
    SupplyChainReportRequest,
    SupplyChainReportResponse,
)


class SupplyChainReportEngine:
    """Generates supply chain PDF reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_client()

    async def generate_report(self, request: SupplyChainReportRequest) -> SupplyChainReportResponse:
        """Generate a supply chain report."""
        # Gather data
        suppliers = (await self.db.execute(select(Supplier).where(Supplier.is_active == True))).scalars().all()
        warehouses = (await self.db.execute(select(Warehouse).where(Warehouse.is_active == True))).scalars().all()
        inventory = (await self.db.execute(select(InventoryItem))).scalars().all()
        shipments = (await self.db.execute(select(Shipment))).scalars().all()
        risks = (await self.db.execute(
            select(SupplyChainRisk).where(SupplyChainRisk.status == "active")
        )).scalars().all()
        alerts = (await self.db.execute(
            select(SupplyChainAlert).where(SupplyChainAlert.status == "active")
        )).scalars().all()

        # Generate executive summary
        overview = {
            "suppliers": len(suppliers),
            "warehouses": len(warehouses),
            "inventory_items": len(inventory),
            "active_shipments": len(shipments),
            "active_risks": len(risks),
        }
        key_metrics = {
            "total_inventory": sum(i.current_stock for i in inventory),
            "total_transport_cost": sum(s.transport_cost for s in shipments),
            "avg_reliability": sum(s.reliability_score for s in suppliers) / max(len(suppliers), 1),
            "delayed_shipments": len([s for s in shipments if s.status == "delayed"]),
        }

        try:
            prompt = format_prompt(
                SC_REPORT_SUMMARY_USER,
                supply_chain_overview=str(overview),
                key_metrics=str(key_metrics),
                health_score="Calculating...",
                recent_risks=str([{"type": r.risk_type, "severity": r.severity} for r in risks[:5]]),
            )
            summary = await self.llm.chat(SC_REPORT_SUMMARY_SYSTEM, prompt)
        except Exception:
            summary = self._fallback_summary(overview, key_metrics)

        # Build report data
        report_data = {
            "report_type": request.report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "executive_summary": summary,
            "suppliers": [{"name": s.name, "reliability": s.reliability_score, "risk": s.risk_score} for s in suppliers],
            "warehouses": [{"name": w.name, "utilization": w.utilization, "capacity": w.capacity} for w in warehouses],
            "inventory": [
                {"name": i.product_name, "stock": i.current_stock, "status": "normal"}
                for i in inventory[:20]
            ],
            "shipments": [
                {"number": s.shipment_number, "status": s.status, "cost": s.transport_cost}
                for s in shipments[:20]
            ],
            "risks": [{"type": r.risk_type, "severity": r.severity, "score": r.risk_score} for r in risks],
            "alerts": [{"title": a.title, "severity": a.severity} for a in alerts[:10]],
        }

        # Generate PDF
        report_id = str(uuid.uuid4())
        pages = self._generate_pdf(report_data, report_id)

        return SupplyChainReportResponse(
            report_id=report_id,
            download_url=f"/api/v1/supply-chain/reports/{report_id}/download",
            generated_at=datetime.now(timezone.utc),
            pages=pages,
            report_type=request.report_type,
        )

    def _fallback_summary(self, overview: Dict, metrics: Dict) -> str:
        return (
            f"Supply Chain Executive Summary\n\n"
            f"The supply chain manages {overview['suppliers']} suppliers across "
            f"{overview['warehouses']} warehouses with {overview['inventory_items']} inventory items. "
            f"Currently {overview['active_shipments']} active shipments with {overview['active_risks']} active risks. "
            f"Total inventory: {metrics['total_inventory']:,} units. "
            f"Transport cost: ${metrics['total_transport_cost']:,.2f}. "
            f"Average supplier reliability: {metrics['avg_reliability']:.1f}/100."
        )

    def _generate_pdf(self, data: Dict[str, Any], report_id: str) -> int:
        """Generate PDF using reportlab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

            os.makedirs(settings.REPORT_OUTPUT_DIR, exist_ok=True)
            filepath = os.path.join(settings.REPORT_OUTPUT_DIR, f"sc_{report_id}.pdf")

            doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
            styles = getSampleStyleSheet()
            story = []

            # Title
            story.append(Paragraph("Supply Chain Report", styles["Title"]))
            story.append(Paragraph(f"Generated: {data.get('generated_at', '')}", styles["Normal"]))
            story.append(Spacer(1, 0.3 * inch))

            # Executive Summary
            story.append(Paragraph("Executive Summary", styles["Heading1"]))
            story.append(Paragraph(data.get("executive_summary", ""), styles["Normal"]))
            story.append(Spacer(1, 0.3 * inch))

            # Suppliers
            suppliers = data.get("suppliers", [])
            if suppliers:
                story.append(Paragraph("Suppliers", styles["Heading1"]))
                t_data = [["Name", "Reliability", "Risk"]]
                for s in suppliers:
                    t_data.append([s["name"], f"{s['reliability']:.1f}", f"{s['risk']:.1f}"])
                t = Table(t_data, colWidths=[3 * inch, 1.5 * inch, 1.5 * inch])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                story.append(t)
                story.append(Spacer(1, 0.3 * inch))

            # Warehouses
            warehouses = data.get("warehouses", [])
            if warehouses:
                story.append(Paragraph("Warehouses", styles["Heading1"]))
                t_data = [["Name", "Utilization", "Capacity"]]
                for w in warehouses:
                    t_data.append([w["name"], f"{w['utilization']:.1f}%", str(w["capacity"])])
                t = Table(t_data, colWidths=[3 * inch, 1.5 * inch, 1.5 * inch])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#059669")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                story.append(t)
                story.append(Spacer(1, 0.3 * inch))

            # Risks
            risks = data.get("risks", [])
            if risks:
                story.append(Paragraph("Active Risks", styles["Heading1"]))
                for r in risks[:10]:
                    severity_color = {"critical": "#dc2626", "high": "#ea580c", "medium": "#d97706", "low": "#2563eb"}.get(r["severity"], "#2563eb")
                    story.append(Paragraph(
                        f'<font color="{severity_color}">[{r["severity"].upper()}]</font> {r["type"]} (Score: {r["score"]:.0f})',
                        styles["Normal"],
                    ))
                story.append(Spacer(1, 0.2 * inch))

            # Alerts
            alerts = data.get("alerts", [])
            if alerts:
                story.append(Paragraph("Active Alerts", styles["Heading1"]))
                for a in alerts[:10]:
                    story.append(Paragraph(f'• [{a["severity"].upper()}] {a["title"]}', styles["Normal"]))

            doc.build(story)
            return max(1, len(story) // 8 + 1)

        except ImportError:
            os.makedirs(settings.REPORT_OUTPUT_DIR, exist_ok=True)
            filepath = os.path.join(settings.REPORT_OUTPUT_DIR, f"sc_{report_id}.txt")
            with open(filepath, "w") as f:
                f.write(json.dumps(data, indent=2, default=str))
            return 1
