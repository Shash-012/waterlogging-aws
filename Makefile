# Root Makefile (owner: Agent C). Agents add folder-level Makefiles (core/Makefile, ops/Makefile).
PYTHON ?= python

.PHONY: contract-check

## Validate every fixture in contract/fixtures against its schema and the risk formulas.
contract-check:
	$(PYTHON) contract/tools/validate.py
