#!/bin/sh
# usage: AGENT_HUB_URL=http://127.0.0.1:8080/<token> ./report.sh my-agent info "hello"
curl -fsS -X POST "$AGENT_HUB_URL/report" -H 'Content-Type: application/json' \
  -d "{\"agent_id\":\"$1\",\"level\":\"$2\",\"msg\":\"$3\"}"
