"""GET /alerts?limit=N: the newest alerts first, as the contract's AlertLog."""
import json
import os

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

_table = None


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def parse_limit(params):
    raw = (params or {}).get("limit")
    if raw is None:
        return DEFAULT_LIMIT
    try:
        n = int(raw)
    except ValueError:
        n = 0
    if not 1 <= n <= MAX_LIMIT:
        raise ValueError(f"limit must be a whole number from 1 to {MAX_LIMIT}.")
    return n


def handler(event, context, table=None):
    global _table
    try:
        limit = parse_limit(event.get("queryStringParameters"))
    except ValueError as e:
        return respond(400, {"error": {"code": "bad_request", "message": str(e)}})

    if table is None:
        if _table is None:
            import boto3

            _table = boto3.resource("dynamodb").Table(os.environ["ALERTS_TABLE"])
        table = _table

    from boto3.dynamodb.conditions import Key

    items = table.query(
        KeyConditionExpression=Key("pk").eq("ALERT"),
        ScanIndexForward=False,
        Limit=limit,
    )["Items"]
    return respond(200, {"alerts": [json.loads(i["doc"]) for i in items]})
