.PHONY: dev build start lint typecheck test format checkall

# Port for the Next.js server (override: make dev FRONTEND_PORT=3100)
FRONTEND_PORT ?= 3000

# Detect package manager: prefer bun if available, otherwise use npm
PKG_MGR := $(shell command -v bun >/dev/null 2>&1 && echo "bun" || echo "npm")

dev:
	$(PKG_MGR) run dev -- --port $(FRONTEND_PORT)

build:
	$(PKG_MGR) run build

start:
	$(PKG_MGR) run start -- --port $(FRONTEND_PORT)

lint:
	$(PKG_MGR) run lint

typecheck:
	$(PKG_MGR) run typecheck

test:
	$(PKG_MGR) run test

fmt:
	$(PKG_MGR) run format

checkall: fmt lint typecheck build
	# Run tests after linting and formatting to ensure coverage
	$(PKG_MGR) run test
