import os, json, anyio
from typing import Dict, Any, List, Optional

# === Helpers: lazy imports so init won't crash ===
def _ga_client():
    from google.oauth2 import service_account
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    creds_json = os.environ.get("GA_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GA_CREDENTIALS_JSON is missing in environment")
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/analytics.readonly"]
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return BetaAnalyticsDataClient(credentials=creds)

def _prop_id(prop: Optional[str]) -> str:
    pid = prop or os.environ.get("GOOGLE_ANALYTICS_PROPERTY_ID")
    if not pid:
        raise ValueError("property_id is required (env GOOGLE_ANALYTICS_PROPERTY_ID or pass in call)")
    return pid if str(pid).startswith("properties/") else f"properties/{pid}"

def _top_pages(property_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    from google.analytics.data_v1beta import RunReportRequest, DateRange, Dimension, Metric
    client = _ga_client()
    req = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
        dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
        metrics=[Metric(name="screenPageViews")],
        order_bys=[{"metric": {"metric_name": "screenPageViews"}, "desc": True}],
        limit=limit,
    )
    resp = client.run_report(req)
    return [{
        "id": r.dimension_values[0].value or "/",
        "title": r.dimension_values[1].value or "(no title)",
        "url": r.dimension_values[0].value or "/",
        "snippet": f"views={r.metric_values[0].value}",
        "views": int(r.metric_values[0].value or 0),
    } for r in resp.rows]

def _page_detail(property_id: str, path: str) -> Dict[str, Any]:
    from google.analytics.data_v1beta import RunReportRequest, DateRange, Dimension, Metric
    client = _ga_client()
    req = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews"), Metric(name="totalUsers"), Metric(name="sessions")],
        dimension_filter={"filter":{"field_name":"pagePath","string_filter":{"value": path}}},
        limit=1,
    )
    resp = client.run_report(req)
    if not resp.rows:
        return {"id": path, "note": "No data"}
    r = resp.rows[0]
    return {
        "id": path,
        "metrics": {
            "views": int(r.metric_values[0].value or 0),
            "users": int(r.metric_values[1].value or 0),
            "sessions": int(r.metric_values[2].value or 0),
        },
    }

# === MCP server over STDIO ===
from mcp.server import Server
from mcp.server.stdio import stdio_server

srv = Server("ga4-mcp-wrapper")

@srv.tool()
def search(q: str = "", property_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return top pages for last 7 days (title, path, views)."""
    return _top_pages(_prop_id(property_id))

@srv.tool()
def fetch(id: str, property_id: Optional[str] = None) -> Dict[str, Any]:
    """Fetch metrics for a given pagePath (id)."""
    return _page_detail(_prop_id(property_id), id)

async def main() -> None:
    async with stdio_server(srv).run():
        await anyio.sleep_forever()

if __name__ == "__main__":
    anyio.run(main)
