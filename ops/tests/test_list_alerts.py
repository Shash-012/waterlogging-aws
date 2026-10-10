import json

import pytest
from conftest import load_app

app = load_app("list_alerts")


class FakeTable:
    def __init__(self, records):
        self.items = [{"pk": "ALERT", "sk": f"{r['sent_at']}#{r['alert_id']}", "doc": json.dumps(r)} for r in records]
        self.last_query = None

    def query(self, **kw):
        self.last_query = kw
        items = sorted(self.items, key=lambda i: i["sk"], reverse=not kw["ScanIndexForward"])
        return {"Items": items[: kw["Limit"]]}


def get(table, params=None):
    res = app.handler({"queryStringParameters": params}, None, table)
    return res["statusCode"], json.loads(res["body"])


def test_lists_newest_first_in_the_contract_shape(fixture, schema_check):
    old = fixture("alert_log")["alerts"][0]
    new = {**old, "alert_id": "alrt-2", "sent_at": "2026-10-09T15:00:00Z"}
    table = FakeTable([old, new])
    status, body = get(table)
    assert status == 200
    schema_check("alert_log", body)
    assert [a["alert_id"] for a in body["alerts"]] == ["alrt-2", old["alert_id"]]
    assert table.last_query["Limit"] == 50

    status, body = get(table, {"limit": "1"})
    assert [a["alert_id"] for a in body["alerts"]] == ["alrt-2"]


@pytest.mark.parametrize("limit", ["0", "201", "ten", "-3"])
def test_bad_limit_is_400(limit, schema_check):
    status, body = get(FakeTable([]), {"limit": limit})
    assert status == 400
    schema_check("error", body)
