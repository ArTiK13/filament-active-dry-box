# Override with: make geometry PYTHON=/path/to/venv/bin/python
PYTHON ?= python3

.PHONY: help build geometry render verify package

help:
	@echo "build     CAD, exports, checks and renders"
	@echo "geometry  CAD, exports and checks without rendering"
	@echo "render    Regenerate renders for the current verified geometry"
	@echo "verify    Audit source hashes, templates and render hashes"
	@echo "package   Audit and package sources plus generated CAD into dist/"

build:
	$(PYTHON) cad/build.py
	$(PYTHON) cad/verify_delivery.py

geometry:
	$(PYTHON) cad/build.py --no-render
	$(PYTHON) cad/verify_delivery.py

render:
	$(PYTHON) cad/render_project.py

verify:
	$(PYTHON) cad/verify_delivery.py

package:
	$(PYTHON) scripts/package.py
