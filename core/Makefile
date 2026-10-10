# core/Makefile (owner: Agent A). Run from the repo root as `make -C core <target>`.
PYTHON ?= python

.PHONY: build deploy

build:
	sam build

deploy: build
	sam deploy
