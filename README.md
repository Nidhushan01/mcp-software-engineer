# Agentic Software Investigator

An evidence-driven, multi-agent platform for investigating software repositories, identifying likely root causes, and producing human-approved code patches.

Built with **Model Context Protocol (MCP)**, **LangGraph**, **FastAPI**, **React**, and **Qdrant**.

> This project is a local prototype and portfolio project. It demonstrates the complete investigation workflow, but requires additional security and infrastructure work before production deployment.

## Overview

Agentic Software Investigator turns a bug report or code question into a structured, auditable investigation. Specialized agents inspect source code, search technical documentation, optionally review GitHub history, form competing hypotheses, and explain their conclusions using file- and line-level evidence.

Source-code analysis is read-only. Any proposed modification is isolated behind a separate Patch MCP server and requires explicit human approval before it can be applied.

## Key Features

- Read-only repository navigation, code search, Git inspection, and dependency discovery
- Evidence-driven bug investigation with precise source provenance
- Multi-agent orchestration with bounded investigation loops
- Competing root-cause hypotheses with confidence scores and statuses
- Documentation retrieval using literal search and Qdrant semantic search
- Optional GitHub issue, pull request, commit, and discussion history
- Immutable patch proposals with validation and human approval
- FastAPI REST API with interactive Swagger documentation
- Responsive React investigation dashboard
- Repository-boundary protections for filesystem operations
- Automated tests for MCP tools, agents, API workflows, and patch safety

## How It Works

```text
Bug report or code question
          |
          v
      Supervisor
          |
          +--> Code Analyst ----------> Repository MCP
          |
          +--> Documentation Agent ---> Knowledge MCP / Qdrant
          |
          +--> GitHub History Agent --> GitHub MCP (optional)
          |
          v
    Bug Investigator
          |
          +--> More evidence required? --> Repeat bounded cycle
          |
          v
 Evidence-backed report
          |
          v
 Patch proposal --> Validation --> Human approval --> Apply
```

The supervisor stops when sufficient evidence supports a conclusion or when the configured iteration limit is reached. Reaching the limit does not automatically promote an unverified hypothesis to a root cause.

## MCP Servers

### Repository MCP

A read-only interface to the configured source repository.

- Navigate directories and read files
- Search code, filenames, imports, and symbols
- Inspect repository structure and file metadata
- Read Git status, logs, diffs, commits, and blame information
- Discover project dependencies and versions

### Knowledge MCP

Searches internal and technical documentation.

- Literal documentation search
- Library documentation and API-reference lookup
- Qdrant semantic search
- Related-document discovery
- Documentation and repository index refresh

The default configuration uses embedded Qdrant storage and a deterministic local hashing embedder. It does not require an external embedding API.

### Patch MCP

Separates write operations from repository analysis.

1. `generate_diff` creates an immutable proposal without changing the file.
2. `validate_patch` checks the path boundary, source hash, diff, and Python syntax.
3. `apply_patch` writes the exact validated proposal after explicit approval.

### GitHub MCP (optional)

GitHub's official MCP server can be launched through Docker in read-only and lockdown modes. It provides historical context from issues, pull requests, commits, discussions, and code search.

## Technology Stack

| Area | Technologies |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Agent orchestration | LangGraph |
| Tool protocol | Model Context Protocol (MCP) |
| Vector retrieval | Qdrant, local hashing embedder |
| Optional LLM assistant | OpenAI Responses API |
| Frontend | React, TypeScript, Vite |
| Testing | Python `unittest` |

## Project Structure

```text
.
|-- api/                       # FastAPI routes, models, and local store
|-- frontend/                  # React and Vite investigation console
|-- knowledge_base/            # Bundled technical documentation
|-- mcp_clients/               # MCP sessions, registry, and routing
|-- mcp_servers/
|   |-- knowledge/             # Documentation and semantic-search tools
|   |-- patch/                 # Validated, approval-gated write tools
|   `-- repository/            # Read-only repository inspection tools
|-- sample_repos/              # Vulnerable sample application
|-- services/
|   |-- agents/                # Supervisor and specialist agents
|   `-- investigation/         # Plans, evidence, hypotheses, and reports
|-- tests/                     # Automated test suite
|-- investigate.py             # Standalone investigation CLI
|-- langgraph_app.py           # Multi-agent CLI
|-- patch_workflow.py           # Interactive patch approval CLI
`-- repository_assistant.py    # OpenAI tool-calling assistant
```

## Getting Started

### Prerequisites

- Python 3.11 or newer
- Node.js and npm
- Git
- Docker Desktop only if using the optional GitHub MCP integration

### 1. Clone and enter the repository

```powershell
git clone <your-repository-url>
cd agentic-software-investigator
```

### 2. Create the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Install frontend dependencies

```powershell
cd frontend
npm.cmd install
cd ..
```

`npm.cmd` is used in the examples because some Windows PowerShell configurations block the `npm.ps1` wrapper.

## Run the Web Application

### Start the backend

In the first PowerShell terminal, from the project root:

```powershell
.\.venv\Scripts\Activate.ps1
$env:REPOSITORY_ALLOWED_ROOT = (Resolve-Path ".").Path
python -m uvicorn api.main:app --reload
```

Available endpoints:

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

### Start the frontend

In a second PowerShell terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open `http://localhost:5173`.

The Vite development server proxies `/api` requests to `http://127.0.0.1:8000`.

### Try an investigation

Connect the bundled sample repository:

```text
<project-root>\sample_repos\vulnerable-fastapi-app
```

Example investigation request:

```text
Login returns 401 after token refresh.
```

The dashboard displays investigation progress, collected evidence, ranked hypotheses, the root-cause decision, recommendations, and any patch proposal.

## Command-Line Usage

### Run a multi-agent investigation

```powershell
python langgraph_app.py "Login returns 401 after token refresh."
```

Write the result to a file and control the investigation limit:

```powershell
python langgraph_app.py "Login returns 401 after token refresh." `
  --max-iterations 3 `
  --output supervisor-report.md
```

Ask a code question:

```powershell
python langgraph_app.py "Where is authentication implemented?"
```

Disable knowledge retrieval when only local source evidence is needed:

```powershell
python langgraph_app.py "Where is authentication implemented?" --no-knowledge
```

Refresh the Qdrant index after changing code or documentation:

```powershell
python langgraph_app.py "Analyze authentication" --refresh-index
```

### Run the standalone investigation engine

```powershell
python investigate.py "Login returns 401 after token refresh."
```

### Run the OpenAI repository assistant

Set an API key in the current terminal:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
python repository_assistant.py "Where is authentication implemented?"
```

Do not commit API keys or tokens to the repository.

## Optional GitHub History Integration

Prerequisites:

1. Install and start Docker Desktop.
2. Create a fine-grained GitHub token with read access only to the required repositories.
3. Set the token in the current shell.

```powershell
$env:GITHUB_PERSONAL_ACCESS_TOKEN = "your-token"
python langgraph_app.py "Login returns 401 after token refresh." `
  --github OWNER/REPOSITORY `
  --output supervisor-report.md
```

The token is passed to the official GitHub MCP container and should never be stored in source code.

## Inspect the MCP Servers

Activate the virtual environment, then launch an MCP development inspector:

```powershell
mcp dev mcp_servers/repository/server.py:mcp
mcp dev mcp_servers/knowledge/server.py:mcp
```

For the Patch MCP, configure the repository root first:

```powershell
$env:REPOSITORY_ROOT = (Resolve-Path "sample_repos/vulnerable-fastapi-app").Path
mcp dev mcp_servers/patch/server.py:mcp
```

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `REPOSITORY_ROOT` | Repository used by local MCP and CLI operations | Bundled sample repository |
| `REPOSITORY_ALLOWED_ROOT` | Highest directory the API may connect to | Current working directory |
| `KNOWLEDGE_ROOT` | Documentation directory | `knowledge_base` |
| `QDRANT_PATH` | Embedded Qdrant storage path | `.qdrant_data` |
| `QDRANT_URL` | External Qdrant server URL | Not set |
| `QDRANT_API_KEY` | Optional external Qdrant credential | Not set |
| `QDRANT_COLLECTION` | Vector collection name | Project default |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins | Local development origin |
| `OPENAI_API_KEY` | OpenAI key for `repository_assistant.py` | Not set |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub MCP credential | Not set |

## Testing

Run the backend and MCP test suite:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

Build the frontend:

```powershell
cd frontend
npm.cmd run build
```

The current suite contains 22 tests covering repository boundaries, MCP protocol access, investigation logic, agent routing, knowledge retrieval, GitHub-agent restrictions, API lifecycles, and human-approved patch behavior.

## Security Design

- Repository and knowledge paths are resolved against configured roots.
- Absolute paths and traversal outside those roots are rejected.
- Repository analysis tools are read-only.
- Patch generation and application are separated into another MCP server.
- Proposals are validated against the original file hash before application.
- Only an exact human approval decision can reach the write operation.
- GitHub integration uses read-only and lockdown modes.

These controls reduce risk but do not replace application-level authentication, authorization, isolation, and audit infrastructure.

## Current Status and Limitations

The core workflow is implemented and suitable for local demonstrations, learning, and portfolio use. It is not production-ready yet.

Known limitations:

- API records and investigation state are process-local and disappear on restart.
- Multiple API workers cannot safely share the current store.
- Authentication and authorization are not implemented.
- Background work does not use a durable job queue.
- Production monitoring, rate limiting, and secrets management are not configured.
- Deployment and continuous-integration pipelines are not included.
- The included `docker-compose.yml` and `.env.example` are starter placeholders.

Production deployment would require a persistent database, durable task processing and checkpoints, access control, operational observability, secure secret storage, and deployment automation.

## Documentation

See [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for a compact project description suitable for reports, portfolios, and presentations.

## Future Improvements

- Persistent PostgreSQL storage for repositories and investigations
- Durable background workers and LangGraph checkpoints
- User authentication and role-based access control
- LLM-assisted hypothesis generation with configurable providers
- Containerized local deployment
- CI/CD and automated security scanning
- Investigation export and team collaboration
- More language-aware code parsing and symbol analysis

## License

No license has been selected yet. Add a `LICENSE` file before distributing or accepting external contributions.
