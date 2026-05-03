#!/usr/bin/env pwsh
# Run the company_officers demo end-to-end
#
# Usage: scripts/run_demo.ps1
#
# Prerequisites:
# - Docker Desktop running
# - uv installed
# - NEO4J_PASSWORD environment variable set

param(
    [string]$Example = "examples/company_officers",
    [switch]$SkipServices = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

# Check prerequisites
Write-Step "Checking prerequisites"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not found. Please install Docker Desktop."
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Please install uv: https://github.com/astral-sh/uv"
    exit 1
}

if (-not $env:GRAPHFLOW_NEO4J_PASSWORD) {
    Write-Error "GRAPHFLOW_NEO4J_PASSWORD environment variable not set"
    Write-Host "Please set it: `$env:GRAPHFLOW_NEO4J_PASSWORD = 'your-password'"
    exit 1
}

Write-Success "Prerequisites OK"

# Start services if requested
if (-not $SkipServices) {
    Write-Step "Starting Docker services"
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start Docker services"
        exit 1
    }
    
    Write-Host "Waiting for Neo4j to be ready..."
    $maxAttempts = 30
    $attempt = 0
    while ($attempt -lt $maxAttempts) {
        $attempt++
        try {
            docker exec graphflow-neo4j cypher-shell -u neo4j -p $env:GRAPHFLOW_NEO4J_PASSWORD "RETURN 1" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Neo4j is ready"
                break
            }
        } catch {}
        
        if ($attempt -eq $maxAttempts) {
            Write-Error "Neo4j failed to start after 30 seconds"
            exit 1
        }
        Start-Sleep -Seconds 1
        Write-Host "." -NoNewline
    }
    Write-Host ""
}

# Validate manifests
Write-Step "Validating connector manifests"
if ($Verbose) {
    uv run graphflow config validate $Example
} else {
    uv run graphflow config validate $Example | Out-Null
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Manifest validation failed"
    exit 1
}
Write-Success "Manifests valid"

# Preview ingestion
Write-Step "Previewing data ingestion"
if ($Verbose) {
    uv run graphflow ingest $Example --limit 3
}
Write-Success "Ingestion preview OK"

# Preview mapping
Write-Step "Previewing graph mapping"
$mapOutput = uv run graphflow map $Example
if ($LASTEXITCODE -ne 0) {
    Write-Error "Mapping failed"
    exit 1
}
Write-Host $mapOutput
Write-Success "Mapping preview OK"

# Check Neo4j connectivity
Write-Step "Checking Neo4j connectivity"
uv run graphflow graph ping $Example | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Neo4j connection failed"
    exit 1
}
Write-Success "Neo4j connection OK"

# Load the graph
Write-Step "Loading graph into Neo4j"
$loadOutput = uv run graphflow load $Example
if ($LASTEXITCODE -ne 0) {
    Write-Error "Graph loading failed"
    exit 1
}
Write-Host $loadOutput
Write-Success "Graph loaded successfully"

# Run verification query
Write-Step "Running verification query"
$query = @"
MATCH (p:Person)-[r:OFFICER_OF]->(c:Company)
RETURN COUNT(p) AS persons, COUNT(DISTINCT c) AS companies, COUNT(r) AS relationships
"@

$result = docker exec graphflow-neo4j cypher-shell -u neo4j -p $env:GRAPHFLOW_NEO4J_PASSWORD "$query" --format plain 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host $result
    Write-Success "Verification complete"
} else {
    Write-Error "Verification query failed"
}

Write-Host "`n" -NoNewline
Write-Success "Demo completed successfully!"
Write-Host "`nYou can now:"
Write-Host "  - Open Neo4j Browser at http://localhost:7474"
Write-Host "  - Login with neo4j / $env:GRAPHFLOW_NEO4J_PASSWORD"
Write-Host "  - Run queries from docs/demo-scenario.md"
