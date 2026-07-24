.PHONY: setup up down demo logs preflight
setup:      ## bootstrap: keys, preflight, build
	./setup.sh
up:         ## run Sentinel (http://localhost:8080)
	docker compose up -d --build && echo "→ http://localhost:8080"
down:       ## stop
	docker compose down
demo:       ## trigger the demo (optional: make demo PR=123)
	./demo.sh $(PR)
logs:       ## tail orchestrator logs
	docker compose logs -f sentinel
