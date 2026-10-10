"""Core read API (HTTP API payload v2). Routes per contract/CONTRACT.md."""
import json


def _json(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def _error(status, code, message):
    return _json(status, {"error": {"code": code, "message": message}})


def health(event):
    return _json(200, {"ok": True, "latest_run_id": None})


ROUTES = {
    "GET /health": health,
}


def handler(event, context):
    route = ROUTES.get(event.get("routeKey", ""))
    if route is None:
        return _error(404, "not_found", f"No route {event.get('routeKey')}")
    return route(event)
