.PHONY: help dev backend frontend test demo install seed

help:
	@echo "AgentQR — common dev targets"
	@echo ""
	@echo "  make install   Install backend + frontend deps"
	@echo "  make backend   Run the FastAPI backend (http://localhost:8000)"
	@echo "  make frontend  Run the Next.js frontend (http://localhost:3000)"
	@echo "  make dev       Run both concurrently (requires two terminals or 'foreman')"
	@echo "  make test      Run backend unit tests"
	@echo "  make seed      Insert a demo strategy + activity + paper orders into the DB"
	@echo "  make demo      Submit the canonical demo command to /api/command"

install:
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

# Convenience: spawn both processes and wait. Press Ctrl-C to kill the group.
dev:
	@( cd backend && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload ) & \
	 ( cd frontend && npm run dev ) ; \
	 wait

test:
	cd backend && .venv/bin/python -m pytest tests/test_research_pipeline.py -q

seed:
	cd backend && .venv/bin/python scripts/seed_demo.py

demo:
	@echo "Submitting demo command to http://localhost:8000/api/command ..."
	@curl -s -X POST http://localhost:8000/api/command \
	  -H 'Content-Type: application/json' \
	  -d '{"command":"Research a momentum strategy for AAPL, MSFT, NVDA, and TSLA over the last 2 years."}' \
	  | tee /dev/stderr | python3 -c "import sys,json; print('\\nJob:', json.load(sys.stdin)['job_id'])"
