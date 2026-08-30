"""Status Workflow with Accountability Log.

Generic lifecycle engine for reports, rescues, waste, emissions, routes and
resource requests. Every transition is role-limited and recorded in an
append-only audit log with actor + timestamp history.
"""
