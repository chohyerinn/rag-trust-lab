.PHONY: install-dev lint test eval-smoke report docker-build clean-reports

install-dev:
	python -m pip install -e ".[test]"

lint:
	python -m ruff check rag_trust_lab tests api.py streamlit_app.py

test:
	python -m pytest -q

eval-smoke:
	python -m rag_trust_lab run --config configs/basic.json --name smoke-basic --out reports
	python -m rag_trust_lab run --config configs/trusted.json --name smoke-trusted --out reports
	python -m rag_trust_lab compare --a reports/smoke-basic.json --b reports/smoke-trusted.json --out reports

report: eval-smoke
	python scripts/write_latest_summary.py

docker-build:
	docker build -t rag-trust-lab .

clean-reports:
	python -c "from pathlib import Path; [p.unlink() for p in Path('reports').glob('smoke-*.*')]; [p.unlink() for p in Path('reports').glob('compare-smoke-*')]; Path('reports/latest-summary.md').unlink(missing_ok=True)"
