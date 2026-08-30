"""Disaster / Emergency Report Validation Layer.

A modular extension that validates every incoming disaster/emergency report
through an independent stage pipeline (location → metadata → image → duplicate
→ suspicious → confidence), then stores it and updates the disaster map warning
state.

Public entry points:
- ``business_twin_ai.disaster.engines.service.ValidationService`` — orchestrates
  the full validate-and-store flow.
- ``business_twin_ai.disaster.middleware.ValidationMiddleware`` — ASGI middleware
  that forces every report-creation API through the validation service.
- ``business_twin_ai.disaster.api.routes.register_disaster_routes`` — wires the
  new API endpoints onto the FastAPI app.
"""
