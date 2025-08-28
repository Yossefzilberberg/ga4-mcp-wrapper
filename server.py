import os, json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from google.analytics.data_v1beta import (
    BetaAnalyticsDataClient,
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
)
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

def build_ga_client():
    creds_json = os.environ.get("GA_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GA_CREDENTIALS_JSON missing")
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return BetaAnalyticsDataClient(credentials=creds)

GA_CLIENT = build_ga_client()

def get_property_id(prop: Optional[str]) -> str:
    pid = prop or os.environ.get("GOOGLE_ANALYTICS_PROPERTY_ID")
    if not pid:
        raise HTTPException(400, "property_id is required")
    if not str(pid).startswith("properties/"):
        pid = f"properties/{pid}"
    return pid

app = FastAPI()

TOOLS = [
    {
        "name": "search",
        "description": "Search GA4 top pages (last 7 days). Optional: property_id",
        "input_schema": {"type": "object","properties":{"q":{"type":"string"},"property_id":{"type":"string"}}}
    },
    {
        "name": "fetch",
        "description": "Fetch GA4 metrics for a given page path. Required: id",
        "input_schema": {"type": "object","properties":{"id":{"type":"string"},"property_id":{"type":"string"}},"required":["id"]}
    }
]

@app.get("/tools/list")
def tools_list():
    return {"tools": TOOLS}

def run_top_pages(property_id: str) -> List[Dict[str, Any]]:
    req = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
        dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
        metrics=[Metric(name="screenPageViews")],
        limit=10,
        order_bys=[{"metric": {"metric_name": "screenPageViews"}, "desc": True}],
    )
    resp = GA_CLIENT.run_report(req)
    return [{"id": r.dimension_values[0].value, "title": r.dimension_values[1].value, "views": r.metric_values[0].value} for r in resp.rows]

def run_page_details(property_id: str, path: str) -> Dict[str, Any]:
    req = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews"), Metric(name="totalUsers"), Metric(name="sessions")],
        dimension_filter={"filter":{"field_name":"pagePath","string_filter":{"value": path}}},
        limit=1,
    )
    resp = GA_CLIENT.run_report(req)
    if not resp.rows:
        return {"id": path, "note": "No data"}
    r = resp.rows[0]
    return {"id": path,"views": r.metric_values[0].value,"users": r.metric_values[1].value,"sessions": r.metric_values[2].value}

@app.post("/tools/call")
def tools_call(body: Dict[str, Any]):
    name = body.get("name")
    args = body.get("arguments") or {}
    property_id = get_property_id(args.get("property_id"))

    if name == "search":
        return {"content": run_top_pages(property_id)}
    if name == "fetch":
        return {"content": run_page_details(property_id, args["id"])}
    raise HTTPException(400, f"unknown tool: {name}")

@app.get("/sse")
async def sse(request: Request):
    async def eventgen():
        yield "event: ready\ndata: {}\n\n"
        import asyncio
        while True:
            if await request.is_disconnected():
                break
            yield "event: ping\ndata: {}\n\n"
            await asyncio.sleep(15)
    return StreamingResponse(eventgen(), media_type="text/event-stream")

@app.get("/")
def root():
    return JSONResponse({"status":"ok","endpoints":["/sse","/tools/list","/tools/call"]})
