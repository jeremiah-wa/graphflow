#!/usr/bin/env bash
# Run the company_officers demo end-to-end
#
# Usage: scripts/run_demo.sh
#
# Prerequisites:
# - Docker running
# - uv installed
# - NEO4J_PASSWORD environment variable set

set -euo pipefail

EXAMPLE="${1:-examples/company_officers}"
SKIP_SERVICES="${SKIP_SERVICES:-false}"
VERBOSE="${VERBOSE:-false}"

# Colors for output
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

write_step() {
    echo -e "\n${CYAN}==> $1${NC}"
}

write_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

write_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check prerequisites
write_step "Checking prerequisites"

if ! command -v docker &> /dev/null; then
    write_error "Docker not found. Please install Docker."
    exit 1
fi

if ! command -v uv &> /dev/null; then
    write_error "uv not found. Please install uv: https://github.com/astral-sh/uv"
    exit 1
fi

if [ -z "${NEO4J_PASSWORD:-}" ]; then
    write_error "NEO4J_PASSWORD environment variable not set"
    echo "Please set it: export NEO4J_PASSWORD='your-password'"
    exit 1
fi

write_success "Prerequisites OK"

# Start services if requested
if [ "$SKIP_SERVICES" != "true" ]; then
    write_step "Starting Docker services"
    docker compose up -d
    
    echo -n "Waiting for Neo4j to be ready..."
    max_attempts=30
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        attempt=$((attempt + 1))
        if docker exec graphflow-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" &>/dev/null; then
            echo ""
            write_success "Neo4j is ready"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            echo ""
            write_error "Neo4j failed to start after 30 seconds"
            exit 1
        fi
        sleep 1
        echo -n "."
    done
fi

# Validate manifests
write_step "Validating connector manifests"
if [ "$VERBOSE" = "true" ]; then
    uv run graphflow config validate "$EXAMPLE"
else
    uv run graphflow config validate "$EXAMPLE" > /dev/null
fi
write_success "Manifests valid"

# Preview ingestion
write_step "Previewing data ingestion"
if [ "$VERBOSE" = "true" ]; then
    uv run graphflow ingest "$EXAMPLE" --limit 3
fi
write_success "Ingestion preview OK"

# Preview mapping
write_step "Previewing graph mapping"
uv run graphflow map "$EXAMPLE"
write_success "Mapping preview OK"

# Check Neo4j connectivity
write_step "Checking Neo4j connectivity"
uv run graphflow graph ping "$EXAMPLE" > /dev/null
write_success "Neo4j connection OK"

# Load the graph
write_step "Loading graph into Neo4j"
uv run graphflow load "$EXAMPLE"
write_success "Graph loaded successfully"

# Run verification query
write_step "Running verification query"
query="MATCH (p:Person)-[r:OFFICER_OF]->(c:Company) RETURN COUNT(p) AS persons, COUNT(DISTINCT c) AS companies, COUNT(r) AS relationships"

if docker exec graphflow-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "$query" --format plain 2>/dev/null; then
    write_success "Verification complete"
else
    write_error "Verification query failed"
fi

echo ""
write_success "Demo completed successfully!"
echo -e "\nYou can now:"
echo "  - Open Neo4j Browser at http://localhost:7474"
echo "  - Login with neo4j / $NEO4J_PASSWORD"
echo "  - Run queries from docs/demo-scenario.md"
