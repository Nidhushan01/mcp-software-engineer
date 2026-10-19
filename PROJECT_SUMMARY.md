# AI-Powered Software Investigation Platform

## Project Summary

This project is an evidence-driven software investigation platform built with Python, FastAPI, React, LangGraph, MCP (Model Context Protocol), and Qdrant. It helps developers inspect a source-code repository, investigate reported bugs, collect traceable evidence, form hypotheses, and propose controlled code changes.

The system separates read-only analysis from write operations. Repository inspection is performed through a read-only MCP server, while code changes are handled by a dedicated Patch MCP server that requires explicit human approval.

## Main Objectives

- Explore and search source-code repositories safely.
- Investigate software defects using file- and line-level evidence.
- Combine source code, documentation, and GitHub history.
- Rank possible root causes using hypotheses and confidence scores.
- Generate proposed patches without immediately modifying files.
- Require human approval before applying a change.
- Provide the complete workflow through a web interface and REST API.

## Core Components

### Repository MCP Server

The Repository MCP server provides read-only access to a configured repository. It supports:

- Directory and file navigation
- Source-code, import, file, and symbol searches
- Repository structure inspection
- Git status, log, diff, commit, and blame operations
- Dependency discovery and version lookup

All paths are validated to prevent access outside the configured repository root.

### Knowledge MCP Server

The Knowledge MCP server searches internal and technical documentation. It supports literal document search and semantic retrieval using Qdrant.

Its capabilities include:

- Documentation and library searches
- Document and API-reference retrieval
- Semantic search
- Related-document discovery
- Vector-index refreshes

The default Qdrant configuration uses embedded local storage in `.qdrant_data`. A deterministic local hashing embedder is used, so a separate embedding API is not required.

### Patch MCP Server

The Patch MCP server isolates all source-code modification operations. It can:

1. Generate an immutable diff proposal.
2. Validate the repository boundary, original file hash, diff, and Python syntax.
3. Apply the validated patch only after explicit human approval.

Rejected proposals and change requests do not modify repository files.

### Optional GitHub MCP Server

The system can use GitHub's official MCP server through Docker to collect historical context from:

- Issues
- Pull requests
- Commits
- Discussions
- Historical source code

This integration is optional and operates in read-only and lockdown modes.

## Agent Workflow

The LangGraph workflow coordinates several specialized agents:

- **Supervisor:** routes requests and decides whether more evidence is needed.
- **Code Analyst:** examines local source code through the Repository MCP server.
- **Documentation Agent:** searches documentation through the Knowledge MCP server.
- **GitHub History Agent:** gathers optional historical evidence from GitHub.
- **Bug Investigator:** creates and evaluates competing root-cause hypotheses.

A typical bug investigation follows this flow:

```text
User request
    -> Supervisor
    -> Code Analyst
    -> Documentation Agent
    -> Optional GitHub History Agent
    -> Bug Investigator
    -> Supervisor review
    -> More evidence or final report
```

The investigation loop is bounded by a maximum iteration count. A hypothesis is not presented as a verified root cause unless the available evidence satisfies the required conditions.

## Investigation Output

An investigation can produce:

- A structured investigation plan
- Evidence with source, path, and line provenance
- Competing hypotheses
- Confidence scores and hypothesis status
- A root-cause decision
- Recommendations
- An optional patch proposal and unified diff

Hypotheses can be marked as `unverified`, `supported`, `contradicted`, or `confirmed`.

## Backend

The backend is a FastAPI service that provides endpoints to:

- Connect a repository
- Start and monitor an investigation
- Retrieve evidence and hypotheses
- Generate and inspect patch proposals
- Approve, reject, or request changes to a patch
- Check application health

Interactive API documentation is available at `http://127.0.0.1:8000/docs` while the backend is running.

## Frontend

The frontend is a React and Vite investigation console. It lets users:

- Connect a local repository
- Submit a problem description
- Monitor investigation progress
- Review evidence and hypotheses
- View root-cause results
- Inspect unified patch diffs
- Approve or reject proposed changes

During development, the frontend runs at `http://localhost:5173` and proxies API requests to the FastAPI backend.

## Project Structure

```text
api/                       FastAPI application and in-memory store
frontend/                  React/Vite user interface
mcp_clients/               MCP connection and multi-server management
mcp_servers/repository/    Read-only repository tools
mcp_servers/knowledge/     Documentation and Qdrant retrieval tools
mcp_servers/patch/         Controlled patch tools
services/agents/           LangGraph agents and orchestration
services/investigation/    Planning, evidence, hypotheses, and reports
knowledge_base/            Bundled internal and library documentation
sample_repos/              Example repository used for demonstrations
tests/                     Automated Python test suite
.qdrant_data/              Embedded Qdrant data
```

## Running the Application

### Install dependencies

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

cd frontend
npm.cmd install
cd ..
```

### Start the backend

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
$env:REPOSITORY_ALLOWED_ROOT = (Resolve-Path ".").Path
python -m uvicorn api.main:app --reload
```

### Start the frontend

In another PowerShell terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open `http://localhost:5173` in a browser.

## Testing

Run the Python tests from the project root:

```powershell
python -m unittest discover -s tests -v
```

Build the frontend with:

```powershell
cd frontend
npm.cmd run build
```

At the time this summary was prepared, all 22 Python tests passed and the frontend production build completed successfully.

## Current Completion Status

The project is substantially complete as a local prototype, learning project, or portfolio demonstration. Its principal workflows are implemented and tested.

It is not yet production-ready because:

- Repository and investigation records use process-local memory.
- Data is not shared safely across multiple API workers.
- Authentication and authorization are not implemented.
- Durable job processing and checkpoint storage are not configured.
- Production monitoring, rate limiting, and secrets management are absent.
- `.env.example` and `docker-compose.yml` still need useful configuration.
- Deployment and continuous-integration pipelines are not included.

Before production deployment, the in-memory store should be replaced by a database, background work should use a durable queue, API access should be authenticated and authorized, and operational configuration should be completed.

## Technology Stack

- Python 3
- FastAPI and Uvicorn
- Model Context Protocol (MCP)
- LangGraph
- Qdrant
- OpenAI Responses API for the optional repository assistant
- React
- TypeScript
- Vite

## Conclusion

This project demonstrates how MCP servers and specialized agents can cooperate to investigate software problems in a controlled and auditable manner. Its strongest design features are evidence provenance, repository-boundary enforcement, separation of read and write capabilities, bounded agent loops, and mandatory human approval for code modifications.
