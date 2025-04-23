# Makefile at project root (e.g., ripper/)

# Define variables
PYTHON_EXEC = python
SCRIPT_PATH = /Users/bosungkim/bosungkim/src/github/ripper/src/main.py

# If needed for imports, set PYTHONPATH to current directory
PYTHONPATH = .

# Common host/port for backend
HOST = 0.0.0.0
PORT = 8000

.PHONY: help run clean-pycache backend frontend both build clean clean-docker clean-all docker-run

help:
	@echo "Available targets:"
	@echo "  run         - Run the main Python script (main.py)."
	@echo "  alert-backend     - Start the FastAPI alert service (uvicorn)."
	@echo "  alert-frontend    - Start the Panel dashboard."
	@echo "  alert-both        - Run both backend and frontend in parallel."
	@echo "  clean-pycache - Clean Python cache (__pycache__ and .pyc files)."
	@echo "  build       - (Placeholder) Build target."
	@echo "  clean       - (Placeholder) Clean target."
	@echo "  clean-docker - (Placeholder) Clean Docker artifacts."
	@echo "  clean-all   - (Placeholder) Clean all artifacts."
	@echo "  docker-run  - (Placeholder) Run Docker container."

# Run the Python script (clears __pycache__ first)
run: clean-pycache
	@echo "🚀 Running Python script (main.py)..."
	$(PYTHON_EXEC) $(SCRIPT_PATH)

# Clean __pycache__ directories and .pyc files
clean-pycache:
	@echo "🧹 Cleaning Python cache (__pycache__ and .pyc files)..."
	find . -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +

# Start the FastAPI backend (alert service)
alert-backend:
	@echo "🚀 Starting FastAPI backend on port $(PORT)..."
	PYTHONPATH=$(PYTHONPATH) uvicorn src.alert_service.backend.app:app \
		--reload --host $(HOST) --port $(PORT)

# Start the Panel dashboard
alert-frontend:
	@echo "🚀 Starting Panel dashboard..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON_EXEC) -m panel serve src/alert_service/frontend/dashboard.py --show

# Run both backend and frontend in parallel
alert-both:
	@echo "🚀 Starting backend in background..."
	$(MAKE) backend &
	@echo "⌛ Waiting 3 seconds for backend to initialize..."
	sleep 3
	@echo "🚀 Starting frontend..."
	$(MAKE) frontend

# Placeholder targets - customize as needed
build:
	@echo "🏗  Build placeholder. Customize as needed."

clean:
	@echo "🧹 Clean placeholder. Customize as needed."

clean-docker:
	@echo "🧹 Docker clean placeholder. Customize as needed."

clean-all:
	@echo "🧹 Clean all placeholder. Customize as needed."

docker-run:
	@echo "🐳 Docker run placeholder. Customize as needed."