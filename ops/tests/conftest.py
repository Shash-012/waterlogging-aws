import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

OPS = Path(__file__).resolve().parents[1]
CONTRACT = OPS.parent / "contract"


def load_app(name):
    spec = importlib.util.spec_from_file_location(f"{name}_app", OPS / "functions" / name / "app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def schema_check():
    schemas = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in (CONTRACT / "schemas").glob("*.json")}
    registry = Registry().with_resources((n, Resource.from_contents(s)) for n, s in schemas.items())

    def check(name, doc):
        errors = list(Draft202012Validator(schemas[f"{name}.schema.json"], registry=registry).iter_errors(doc))
        assert not errors, [e.message for e in errors]

    return check


@pytest.fixture
def fixture():
    return lambda name: json.loads((CONTRACT / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))
