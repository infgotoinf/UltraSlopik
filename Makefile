PYTHON ?= python3
.PHONY: help api-test backup build check check-deploy deploy deps-check docker-down docker-up format logs logs-check logs-security performance ports-check quality-check release-check restart restore run security-check setup stop test

help:
	@echo "api-test backup build check check-deploy deploy deps-check docker-down docker-up format logs logs-check logs-security performance ports-check quality-check release-check restart restore run security-check setup stop test"

api-test:
	$(PYTHON) tools.py api-test

backup:
	$(PYTHON) tools.py backup

build:
	$(PYTHON) tools.py build

check:
	$(PYTHON) tools.py check

check-deploy:
	$(PYTHON) tools.py check-deploy

deploy:
	$(PYTHON) tools.py deploy

deps-check:
	$(PYTHON) tools.py deps-check

docker-down:
	$(PYTHON) tools.py docker-down

docker-up:
	$(PYTHON) tools.py docker-up

format:
	$(PYTHON) tools.py format

logs:
	$(PYTHON) tools.py logs

logs-check:
	$(PYTHON) tools.py logs-check

logs-security:
	$(PYTHON) tools.py logs-security

performance:
	$(PYTHON) tools.py performance

ports-check:
	$(PYTHON) tools.py ports-check

quality-check:
	$(PYTHON) tools.py quality-check

release-check:
	$(PYTHON) tools.py release-check

restart:
	$(PYTHON) tools.py restart

restore:
	$(PYTHON) tools.py restore

run:
	$(PYTHON) tools.py run

security-check:
	$(PYTHON) tools.py security-check

setup:
	$(PYTHON) tools.py setup

stop:
	$(PYTHON) tools.py stop

test:
	$(PYTHON) tools.py test
