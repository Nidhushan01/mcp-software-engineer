# Repository MCP Server

A read-only MCP server for navigating, searching, inspecting Git history, and
discovering dependencies inside one configured repository. It also includes a
multi-server MCP client manager and a minimal OpenAI tool-calling assistant
without LangGraph.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The default root is `sample_repos/vulnerable-fastapi-app`. Override it before
starting the server when you want to inspect another repository:

```powershell
$env:REPOSITORY_ROOT = "C:\path\to\project"
```

Every filesystem tool rejects absolute paths and paths that resolve outside
this root.

## Inspect the MCP server

```powershell
mcp dev mcp_servers/repository/server.py:mcp
```

Available tools:

- Navigation: `list_directory`, `read_file`, `get_repository_structure`,
  `get_file_metadata`
- Search: `search_code`, `find_files`, `search_imports`, `find_symbol`
- Git: `git_status`, `git_log`, `git_diff`, `git_show_commit`, `git_blame`
- Dependencies: `get_dependencies`, `find_dependency`, `get_dependency_version`

Resources are `repo://structure` and `repo://file/{path}`. For example, read
`repo://file/app/api/auth.py`.

## MCP manager

`MCPRegistry` stores launch configurations, `MCPSession` owns one connection,
and `MCPManager` owns and routes all registered sessions. Tools are namespaced
as `server__tool`, such as `repository__read_file`, to prevent collisions when
more servers are added.

## Ask the LLM

Set an API key and run the assistant:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
python repository_assistant.py "Where is authentication implemented?"
```

Select a different model or repository when needed:

```powershell
python repository_assistant.py "Where is authentication implemented?" `
  --model gpt-5.4 `
  --repository C:\path\to\project
```

The assistant passes MCP tool schemas to the OpenAI Responses API, executes
requested calls through `MCPManager`, returns each result to the model, and
continues until the model produces its answer. No LangGraph or agent framework
is involved.

## Investigate a bug

The investigation service builds an explicit plan, collects file/line evidence,
forms competing hypotheses, scores confidence, and renders an auditable report:

```powershell
python investigate.py "Login returns 401 after refresh."
```

Write the report to a file or inspect another repository:

```powershell
python investigate.py "Login returns 401 after refresh." `
  --repository C:\path\to\project `
  --output investigation.md
```

Hypotheses use `unverified`, `supported`, `contradicted`, or `confirmed` status.
Only an explicitly reproduced hypothesis is marked `confirmed`; code evidence
alone can mark it `supported`.

## LangGraph supervisor

The supervised graph routes requests through a Code Analyst and, for bug
reports, a Bug Investigator. The supervisor can send the case back to the Code
Analyst for missing evidence before producing the final report.

```text
START -> Supervisor -> Code Analyst -> Bug Investigator -> Supervisor
                          ^                                  |
                          +-------- more evidence -----------+
                                                             |
                                                        Synthesize -> END
```

For bug investigations this is a bounded, evidence-driven loop. Each cycle
runs the Code Analyst and every enabled context specialist, then the Bug
Investigator ranks hypotheses and asks for precise missing evidence. The
Supervisor records an auditable decision for every iteration:

```text
Supervisor
    -> Code Analyst -> Repository MCP
    -> Documentation Agent -> Knowledge MCP / Qdrant
    -> GitHub History Agent -> GitHub MCP
    -> Bug Investigator -> hypotheses + evidence requests
    -> enough evidence?
         no  -> repeat the specialist cycle
         yes -> root cause + recommendations
```

The loop stops when a supported hypothesis passes the evidence threshold or
when `--max-iterations` is reached. Reaching the limit never turns an
unverified hypothesis into a root cause. The report includes the termination
reason, per-cycle evidence counts, the root-cause decision, and recommendations.

Run a bug investigation:

```powershell
python langgraph_app.py "Login returns 401 after refresh."
```

Run a code question, which bypasses the Bug Investigator:

```powershell
python langgraph_app.py "Where is authentication implemented?"
```

Use `--max-iterations` to bound evidence delegation and `--output report.md`
to save the supervisor report. The graph itself does not require an API key;
its nodes use the Repository MCP and the evidence/confidence models directly.

If LangSmith tracing is configured in your shell but you are working offline,
disable it for the current PowerShell session:

```powershell
$env:LANGSMITH_TRACING = "false"
$env:LANGCHAIN_TRACING_V2 = "false"
```

## GitHub history through the official MCP server

The optional GitHub History Agent uses GitHub's official MCP Docker image. It
is restricted to the `repos`, `issues`, `pull_requests`, and `discussions` toolsets and starts
with both read-only and lockdown modes enabled.

Prerequisites:

1. Install and start Docker Desktop.
2. Create a fine-grained GitHub token with read access only to the repositories
   the agent may investigate.
3. Put the token in the process environment, never in source code:

```powershell
$env:GITHUB_PERSONAL_ACCESS_TOKEN = "your-token"
```

Run the complete local-code plus GitHub-history investigation:

```powershell
python langgraph_app.py "Login returns 401 after refresh." `
  --github OWNER/REPOSITORY `
  --output supervisor-report.md
```

The History Agent can call `search_issues`, `issue_read`,
`search_pull_requests`, `pull_request_read`, `list_commits`, `get_commit`, and
`search_code`, `list_discussions`, and `get_discussion`. GitHub content is recorded as historical evidence; general code
analysis remains the responsibility of the local Code Analyst.

## Knowledge MCP and Documentation Agent

The Knowledge MCP exposes technical and internal documentation under a separate
read-only `KNOWLEDGE_ROOT`. Its tools are `search_docs`, `search_library_docs`,
`get_document`, `get_api_reference`, `semantic_search`, `refresh_index`, and
`find_related_documents`.

The default documentation root is `knowledge_base`. The Documentation Agent is
enabled by default in `langgraph_app.py` and runs after local code analysis:

```text
Code Analyst -> Documentation Agent -> GitHub History Agent -> Bug Investigator
```

Run with the bundled documentation:

```powershell
python langgraph_app.py "Login returns 401 after refresh."
```

Use an internal documentation directory:

```powershell
python langgraph_app.py "Login returns 401 after refresh." `
  --knowledge-root "C:\path\to\internal-docs"
```

Use `--no-knowledge` when only repository evidence should be collected.

## Qdrant RAG

`semantic_search` uses Qdrant to find candidate documentation and repository
chunks. The default is embedded local Qdrant storage in `.qdrant_data`; no
embedding API is required because indexing uses a deterministic local hashing
embedder. Rebuild the index after code or documentation changes:

```powershell
python langgraph_app.py "Login returns 401 after refresh." --refresh-index
```

Each Qdrant payload preserves provenance including `source`, `path`,
`language`, `symbol`, `start_line`, and `end_line`. Repository results are not
accepted as authoritative evidence directly. The Documentation Agent uses them
as candidates, calls Repository MCP `read_file`, and records evidence from the
current file only. Literal documentation searches also remain enabled, so the
agent does not rely exclusively on RAG.

To use a running Qdrant server instead of embedded storage:

```powershell
$env:QDRANT_URL = "http://localhost:6333"
$env:QDRANT_API_KEY = "optional-api-key"
python langgraph_app.py "Login returns 401 after refresh." --refresh-index
```

You can override the embedded database directory with `QDRANT_PATH`, and the
collection name with `QDRANT_COLLECTION`.

Inspect the Knowledge MCP directly:

```powershell
mcp dev mcp_servers/knowledge/server.py:mcp
```

## Human-approved patch workflow

Repository MCP remains read-only. Code changes live behind a separate Patch
MCP with three tools:

- `generate_diff(path, new_content)` creates an immutable proposal.
- `validate_patch(proposal_id)` checks the repository boundary, source hash,
  non-empty diff, and Python syntax without writing.
- `apply_patch(proposal_id, approval)` writes atomically, but only for the exact
  validated proposal and approval phrase.

`PatchApprovalWorkflow` uses a LangGraph checkpointer and `interrupt()`. It
always stops at `WAITING_FOR_APPROVAL` after displaying the diff. A human can
reject it, request changes with feedback, or approve it. Reject and request
changes finish without touching the repository; only an explicit `approve`
resume reaches `apply_patch`.

To review a complete replacement for one file, put the proposed content in a
temporary review file and run:

```powershell
python patch_workflow.py app/services/auth_service.py `
  --content-file proposed_auth_service.py `
  --repository sample_repos/vulnerable-fastapi-app
```

The unified diff is printed before the prompt. Entering anything other than an
allowed decision is treated as rejection. Inspect the Patch MCP independently
with `mcp dev mcp_servers/patch/server.py:mcp` after setting
`REPOSITORY_ROOT`.

## FastAPI service

Start the investigation API from the project root:

```powershell
$env:REPOSITORY_ALLOWED_ROOT = (Resolve-Path ".").Path
uvicorn api.main:app --reload
```

Swagger UI is available at `http://127.0.0.1:8000/docs`. The primary lifecycle
is:

1. `POST /repositories/connect`
2. `POST /investigations` (returns `202`; poll the returned ID)
3. `GET /investigations/{id}`
4. Inspect `/evidence` and `/hypotheses`
5. `POST /investigations/{id}/patch` with a target path and proposed content
6. Inspect `GET /investigations/{id}/patch`
7. Call `/approve`, `/reject`, or `/request-changes`

Also available: `GET /health`. Patch generation requires a confirmed hypothesis
by default. `require_confirmed: false` is an explicit caller override, but human
approval is still mandatory. Invalid lifecycle transitions return `409`.

Repositories must be beneath `REPOSITORY_ALLOWED_ROOT`; do not expose this API
without authentication and authorization. The current repository and
investigation store is process-local, intended for this learning stage. Use a
database and durable job/checkpoint backend before running multiple API workers
or deploying to production.

## React investigation console

The `frontend` directory contains a responsive React/Vite dashboard for the
complete API lifecycle: repository connection, background status polling,
evidence and hypothesis review, root-cause results, unified patch diffs, and
human approval decisions.

Run the API in one PowerShell terminal:

```powershell
.\.venv\Scripts\Activate.ps1
$env:REPOSITORY_ALLOWED_ROOT = (Resolve-Path ".").Path
uvicorn api.main:app --reload
```

Run the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to
`http://127.0.0.1:8000`. For a separately hosted build, set `VITE_API_URL` to
the FastAPI origin before `npm run build`, and include the frontend origin in
the API's comma-separated `CORS_ORIGINS` environment variable.

## Tests

```powershell
python -m unittest discover -s tests -v
```
