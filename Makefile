VERSION=$(shell python3 aib/version.py)

PREFIX=/usr
BINDIR=$(PREFIX)/bin
DATADIR=$(PREFIX)/lib/automotive-image-builder
DESTDIR=

OSBUILD_MPP_TAG=v124

.PHONY: all
all:
	@echo Run "make install DESTDIR=..." to install, otherwise run directly from checkout

install:
	mkdir -p $(DESTDIR)$(BINDIR)
	install automotive-image-builder.installed $(DESTDIR)$(BINDIR)/automotive-image-builder
	install -t $(DESTDIR)$(BINDIR) automotive-image-runner
	install -t $(DESTDIR)$(BINDIR) automotive-image-vm
	for dir in distro include targets ; do \
		mkdir -p $(DESTDIR)$(DATADIR)/$$dir ; \
		install -m 0644 -t $(DESTDIR)$(DATADIR)/$$dir $$dir/*.yml ; \
	done
	mkdir -p $(DESTDIR)$(DATADIR)/files
	install -m 0644 -t $(DESTDIR)$(DATADIR)/files files/*
	mkdir -p $(DESTDIR)$(DATADIR)/aib
	install  -t $(DESTDIR)$(DATADIR)/aib aib/*.py
	mkdir -p $(DESTDIR)$(DATADIR)/mpp/aibosbuild/util
	install  -t $(DESTDIR)$(DATADIR)/mpp mpp/aib-osbuild-mpp
	install  -t $(DESTDIR)$(DATADIR)/mpp/aibosbuild/util mpp/aibosbuild/util/*.py

.PHONY: test-compose
test-compose:
	tests/test-compose tests/test-compose.json

.PHONY: test-unit
test-unit:
	pytest aib/tests

.PHONY: test-integration
test-integration:
	cd tests && \
	tmt --feeling-safe run -v -ePROJECT_DIR=$$PWD/.. plan --name local

.PHONY: test
test: test-compose test-unit test-integration yamllint

rpm:
	./.copr/build-rpm.sh -bb automotive-image-builder.spec.in

srpm:
	./.copr/build-rpm.sh -bs automotive-image-builder.spec.in

rpm_dev:
	./.copr/build-rpm.sh -bb .copr/dev.spec

srpm_dev:
	./.copr/build-rpm.sh -bs .copr/dev.spec

import-mpp:
	./import-osbuild-mpp.sh $(OSBUILD_MPP_TAG)

yamllint:
	yamllint -c .yamllint distro/ include/ targets/ examples files/

.venv:
	python3 -m venv .venv
	. .venv/bin/activate; pip install json-schema-for-humans

generate-manifest-doc: .venv
	mkdir -p docs
	. .venv/bin/activate; generate-schema-doc files/manifest_schema.yml docs/manifest.html
	. .venv/bin/activate; generate-schema-doc --config template_name=md files/manifest_schema.yml docs/manifest.md
