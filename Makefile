# Override with: make geometry PYTHON=/path/to/venv/bin/python
PYTHON ?= python3

.PHONY: help build geometry render verify package variants variants-geometry variants-render variants-package

help:
	@echo "build     CAD, exports, checks and renders"
	@echo "geometry  CAD, exports and checks without rendering"
	@echo "render    Regenerate renders for the current verified geometry"
	@echo "verify    Audit source hashes, templates and render hashes"
	@echo "package   Audit and package sources plus generated CAD into dist/"
	@echo "variants  Build both spring and magnetic valve prototypes"
	@echo "variants-geometry / variants-render / variants-package"

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

variants:
	$(PYTHON) cad/build_variants.py

variants-geometry:
	$(PYTHON) cad/build_variants.py --no-render

variants-render:
	$(PYTHON) cad/build_variants.py --render-only

variants-package:
	$(PYTHON) cad/build_variants.py --package-only
