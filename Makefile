# Root Makefile (owner: Agent C). Agents add folder-level Makefiles (core/Makefile, ops/Makefile).
PYTHON ?= python

CORE_API_URL ?= https://x6klvfqev1.execute-api.ap-south-1.amazonaws.com

.PHONY: contract-check fixtures

## Validate every fixture against its schema and the risk formulas: the synthetic set
## in contract/fixtures and the real set in contract/fixtures/live.
contract-check:
	$(PYTHON) contract/tools/validate.py
	$(PYTHON) contract/tools/validate.py --fixtures contract/fixtures/live --real

## Regenerate contract/fixtures/live from handoff/samples-a and the live core API,
## plus the synthetic dry replay. Never hand-edit these files.
fixtures:
	$(PYTHON) contract/tools/regen_fixtures.py --api $(CORE_API_URL)
