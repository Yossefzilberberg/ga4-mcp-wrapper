import os, json
from typing import Any, Dict
from mcp.server.fastapi import FastAPI, run
from mcp.types import Tool, CallToolRequest, CallToolResult, TextContent
from google.analytics.data_v1beta import BetaAnalyticsDataClient, RunReportRequest, DateRange, Dimension, Metric
from google.oauth2 import service_account

app = FastAPI()

# ----- GA4 client setup -----
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

def build_ga_client():
    creds_json = os.environ.get("GA_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GA_CREDENTIALS_JSON missing")
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return BetaAnalyticsDataClient(credentials=creds)

GA_CLIENT = build_ga_client()

def get_property_id(pid: str | None) -> str:
    if not pid:
        pid = os.environ.get("GOOGLE_ANALYTICS_PROPERTY_ID")
    if not pid:
        raise RuntimeError("property_id is required")
    if not str(pid).startswith("properties/"):
        pid = f"properties/{pid}"
    return pid

# ----- Tools -----
@app.tool()
def search(q: str = "", property_id: str | None = None) -> list[dict[str, Any]]:
    """Return top pages from GA4 (ignores q for now)."""
    pid = get_property_id(property_id)
    req = RunReportRequest(
        property=pid,
        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
        dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
        metrics=[Metric(name="screenPageViews")],
        limit=10,
    )
    resp = GA_CLIENT.run_report(req)
    return [{"id": r.dimension_values[0].value,
             "title": r.dimension_values[1].value,
             "views": r.metric_values[0].value} for r in resp.rows]

@app.tool()
def fetch(id: str, property_id: str | None = None) -> dict[str, Any]:
    """Fetch GA4 metrics for a given page path."""
    pid = get_property_id(property_id)
    req = RunReportRequest(
        property=pid,
        date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews"), Metric(name="totalUsers"), Metric(name="sessions")],
        dimension_filter={"filter": {"field_name": "pagePath", "string_filter": {"value": id}}},
        limit=1,
    )
    resp = GA_CLIENT.run_report(req)
    if not resp.rows:
        return {"id": id, "note": "No data"}
    r = resp.rows[0]
    return {"id": id,
            "views": r.metric_values[0].value,
            "users": r.metric_values[1].value,
            "sessions": r.metric_values[2].value}

if __name__ == "__main__":
    run(app)
