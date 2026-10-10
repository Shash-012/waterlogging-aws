# core/Makefile (owner: Agent A). Run from the repo root as `make -C core <target>`.
# Needs AWS SAM CLI and the `wlew` AWS profile for build/deploy/seed/score.
PYTHON ?= python
API ?= $(shell aws cloudformation describe-stacks --stack-name wlew-core --profile wlew --region ap-south-1 --query "Stacks[0].Outputs[?OutputKey=='CoreApiUrl'].OutputValue" --output text)

.PHONY: stage build deploy seed score test test-contract

## Copy model/wlew_model + params.json into the Lambda layer folder.
stage:
	$(PYTHON) stage_layer.py

build: stage
	sam build

deploy: build
	sam deploy

## Load hotspots into DynamoDB and replays into S3 (after deploy).
seed:
	$(PYTHON) ../scripts/seed/seed.py

## Run the hourly scorer once now instead of waiting for the schedule.
score:
	aws lambda invoke --profile wlew --region ap-south-1 --function-name $(shell aws cloudformation describe-stacks --stack-name wlew-core --profile wlew --region ap-south-1 --query "Stacks[0].Outputs[?OutputKey=='ScoreFunctionName'].OutputValue" --output text) --log-type None score-out.json

## Unit tests for the risk model and core Lambdas (used by CI; no AWS needed).
test:
	$(PYTHON) -m pip install -q -r ../model/requirements-dev.txt
	$(PYTHON) -m pytest -q ../model/tests $(wildcard tests/unit)

## Contract tests against the deployed API: make -C core test-contract [API=https://...]
test-contract:
	$(PYTHON) -m pytest -q tests/contract --api $(API)
