"""Report Generator engine.

Generates downloadable PDF reports with:
- Business Summary
- Current KPIs
- Simulation Details
- Predictions
- Recommendations
- Confidence Scores
- Charts Data
- Executive Summary
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.config import settings
from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.engines.health import HealthEngine
from business_twin_ai.core.models.database import Insight, Simulation, Strategy
from business_twin_ai.core.schemas.schemas import ReportRequest, ReportResponse
from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.services.prompts.templates import (
    REPORT_SUMMARY_SYSTEM,
    REPORT_SUMMARY_USER,
    format_prompt,
)


class ReportEngine:
    """Generates PDF business reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.twin_engine = DigitalTwinEngine(db)
        self.health_engine = HealthEngine(db)
        self.llm = get_llm_client()

    async def generate_report(
        self, twin_id: uuid.UUID, request: ReportRequest
    ) -> ReportResponse:
        """Generate a complete PDF report."""
        twin = await self.twin_engine.get_twin(twin_id)
        if not twin:
            raise ValueError(f"Digital twin {twin_id} not found")

        state = self.twin_engine.get_twin_state(twin)
        health = await self.health_engine.calculate_health(twin_id)

        # Gather data
        simulations = await self._get_simulations(twin_id) if request.include_simulations else []
        insights = await self._get_insights(twin_id) if request.include_insights else []
        strategies = await self._get_strategies(twin_id) if request.include_strategies else []

        # Generate executive summary via LLM
        executive_summary = await self._generate_executive_summary(
            state, simulations, health.overall_score, insights
        )

        # Build report data
        report_data = {
            "business_name": twin.name,
            "industry": twin.industry,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "executive_summary": executive_summary,
            "current_state": state,
            "health_score": health.model_dump(),
            "simulations": [
                {
                    "decision_type": s.decision_type,
                    "decision_params": s.decision_params,
                    "predicted_revenue": s.predicted_revenue,
                    "predicted_profit": s.predicted_profit,
                    "confidence_score": s.confidence_score,
                    "created_at": s.created_at.isoformat(),
                }
                for s in simulations
            ],
            "insights": [
                {
                    "type": i.insight_type,
                    "title": i.title,
                    "description": i.description,
                    "severity": i.severity,
                }
                for i in insights
            ],
            "strategies": [
                {
                    "type": s.strategy_type,
                    "title": s.title,
                    "description": s.description,
                    "priority": s.priority,
                }
                for s in strategies
            ],
            "kpis": state.get("kpis", {}),
        }

        # Generate PDF
        report_id = str(uuid.uuid4())
        pages = self._generate_pdf(report_data, report_id)

        return ReportResponse(
            report_id=report_id,
            download_url=f"/api/v1/reports/{report_id}/download",
            generated_at=datetime.now(timezone.utc),
            pages=pages,
        )

    async def _generate_executive_summary(
        self,
        state: Dict[str, Any],
        simulations: List[Simulation],
        health_score: float,
        insights: List[Insight],
    ) -> str:
        """Generate an executive summary via LLM."""
        sims_data = [
            {"type": s.decision_type, "revenue": s.predicted_revenue, "profit": s.predicted_profit}
            for s in simulations[:5]
        ]
        insights_data = [{"title": i.title, "type": i.insight_type} for i in insights[:5]]

        prompt = format_prompt(
            REPORT_SUMMARY_USER,
            business_state=str(state),
            simulations=str(sims_data),
            health_score=str(health_score),
            insights=str(insights_data),
        )

        try:
            return await self.llm.chat(REPORT_SUMMARY_SYSTEM, prompt)
        except Exception:
            return self._fallback_summary(state, health_score)

    async def _get_simulations(self, twin_id: uuid.UUID) -> List[Simulation]:
        """Fetch simulations for a twin."""
        result = await self.db.execute(
            select(Simulation)
            .where(Simulation.twin_id == twin_id)
            .order_by(Simulation.created_at.desc())
            .limit(10)
        )
        return list(result.scalars().all())

    async def _get_insights(self, twin_id: uuid.UUID) -> List[Insight]:
        """Fetch insights for a twin."""
        result = await self.db.execute(
            select(Insight)
            .where(Insight.twin_id == twin_id)
            .order_by(Insight.created_at.desc())
            .limit(10)
        )
        return list(result.scalars().all())

    async def _get_strategies(self, twin_id: uuid.UUID) -> List[Strategy]:
        """Fetch strategies for a twin."""
        result = await self.db.execute(
            select(Strategy)
            .where(Strategy.twin_id == twin_id)
            .order_by(Strategy.created_at.desc())
            .limit(10)
        )
        return list(result.scalars().all())

    def _fallback_summary(self, state: Dict[str, Any], health_score: float) -> str:
        """Generate a fallback summary without LLM."""
        return (
            f"Executive Summary\n\n"
            f"The business '{state.get('name', 'Unknown')}' operates in the {state.get('industry', 'general')} industry "
            f"with current revenue of ${state.get('revenue', 0):,.0f} and profit of ${state.get('profit', 0):,.0f}. "
            f"The business serves {state.get('customers', 0)} customers with {state.get('employees', 0)} employees. "
            f"The overall business health score is {health_score:.1f}/100. "
            f"{'The business is in a healthy position.' if health_score > 60 else 'The business needs strategic improvements.'}"
        )

    def _generate_pdf(self, data: Dict[str, Any], report_id: str) -> int:
        """Generate PDF using reportlab. Returns number of pages."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )

            output_dir = settings.REPORT_OUTPUT_DIR
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, f"{report_id}.pdf")

            doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
            styles = getSampleStyleSheet()
            story = []

            # Title
            story.append(Paragraph(f"Business Report: {data.get('business_name', 'N/A')}", styles["Title"]))
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(f"Generated: {data.get('generated_at', '')}", styles["Normal"]))
            story.append(Spacer(1, 0.3 * inch))

            # Executive Summary
            story.append(Paragraph("Executive Summary", styles["Heading1"]))
            story.append(Paragraph(data.get("executive_summary", ""), styles["Normal"]))
            story.append(Spacer(1, 0.3 * inch))

            # KPIs Table
            story.append(Paragraph("Key Performance Indicators", styles["Heading1"]))
            kpis = data.get("kpis", {})
            if kpis:
                kpi_data = [["Metric", "Value"]]
                for k, v in kpis.items():
                    kpi_data.append([k.replace("_", " ").title(), str(v)])
                t = Table(kpi_data, colWidths=[3 * inch, 3 * inch])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ]))
                story.append(t)
                story.append(Spacer(1, 0.3 * inch))

            # Health Score
            health = data.get("health_score", {})
            story.append(Paragraph("Business Health", styles["Heading1"]))
            story.append(Paragraph(f"Overall Score: {health.get('overall_score', 0)}/100", styles["Normal"]))
            story.append(Paragraph(f"Trend: {health.get('trend', 'N/A')}", styles["Normal"]))
            story.append(Spacer(1, 0.2 * inch))

            # Simulations
            sims = data.get("simulations", [])
            if sims:
                story.append(Paragraph("Recent Simulations", styles["Heading1"]))
                sim_data = [["Decision", "Predicted Revenue", "Predicted Profit", "Confidence"]]
                for s in sims:
                    sim_data.append([
                        s.get("decision_type", ""),
                        f"${s.get('predicted_revenue', 0):,.0f}",
                        f"${s.get('predicted_profit', 0):,.0f}",
                        f"{s.get('confidence_score', 0):.0f}%",
                    ])
                t = Table(sim_data, colWidths=[2 * inch, 1.5 * inch, 1.5 * inch, 1 * inch])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#059669")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]))
                story.append(t)
                story.append(Spacer(1, 0.3 * inch))

            # Insights
            insights = data.get("insights", [])
            if insights:
                story.append(Paragraph("Business Insights", styles["Heading1"]))
                for ins in insights:
                    severity_color = {"critical": "#dc2626", "warning": "#d97706", "info": "#2563eb"}.get(
                        ins.get("severity", "info"), "#2563eb"
                    )
                    story.append(Paragraph(
                        f'<font color="{severity_color}">[{ins.get("severity", "info").upper()}]</font> '
                        f'{ins.get("title", "")}',
                        styles["Normal"],
                    ))
                    story.append(Paragraph(ins.get("description", ""), styles["Normal"]))
                    story.append(Spacer(1, 0.1 * inch))

            # Strategies
            strats = data.get("strategies", [])
            if strats:
                story.append(Spacer(1, 0.2 * inch))
                story.append(Paragraph("Recommended Strategies", styles["Heading1"]))
                for s in strats:
                    story.append(Paragraph(
                        f'<b>{s.get("title", "")}</b> (Priority: {s.get("priority", "N/A")})',
                        styles["Normal"],
                    ))
                    story.append(Paragraph(s.get("description", ""), styles["Normal"]))
                    story.append(Spacer(1, 0.1 * inch))

            doc.build(story)
            return len(story) // 5 + 1  # rough page estimate

        except ImportError:
            # If reportlab isn't installed, create a placeholder
            os.makedirs(settings.REPORT_OUTPUT_DIR, exist_ok=True)
            filepath = os.path.join(settings.REPORT_OUTPUT_DIR, f"{report_id}.txt")
            with open(filepath, "w") as f:
                f.write(json.dumps(data, indent=2, default=str))
            return 1
