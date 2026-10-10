# core/Makefile (owner: Agent A). Run from the repo root as `make -C core <target>`.
PYTHON ?= python

.PHONY: build deploy test test-contract

build:
	sam build

deploy: build
	sam deploy

## Unit tests for the risk model and core Lambdas (used by CI).
test:
	$(PYTHON) -m pip install -q -r ../model/requirements-dev.txt
	$(PYTHON) -m pytest -q ../model/tests $(wildcard tests/unit)
