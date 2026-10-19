import { FormEvent, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, Check, CheckCircle2, CircleDot, Code2, FileCode2, GitBranch, Library, LoaderCircle, Search, ShieldCheck, X } from "lucide-react";
import { api } from "./api";
import type { Evidence, Hypothesis, Investigation, PatchProposal, Repository } from "./types";

type Tab = "overview" | "evidence" | "hypotheses" | "patch";

const sourceIcon: Record<string, typeof Code2> = { repository: Code2, documentation: Library, github: GitBranch, test: CheckCircle2 };

function App() {
  const [repository, setRepository] = useState<Repository | null>(null);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [patch, setPatch] = useState<PatchProposal | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!investigation || !["queued", "running"].includes(investigation.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const current = await api.getInvestigation(investigation.id);
        setInvestigation(current);
        if (current.status === "completed") {
          const [ev, hy] = await Promise.all([api.getEvidence(current.id), api.getHypotheses(current.id)]);
          setEvidence(ev.evidence); setHypotheses(hy.hypotheses);
        }
      } catch (reason) { setError(message(reason)); }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [investigation?.id, investigation?.status]);

  const act = async (operation: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await operation(); } catch (reason) { setError(message(reason)); } finally { setBusy(false); }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#"><span className="brand-mark"><CircleDot size={18} /></span><span>TRACE</span></a>
        <div className="top-status"><span className="live-dot" /> LOCAL SYSTEM <span className="divider" /> HUMAN-GATED</div>
      </header>

      <main>
        {!repository ? <ConnectView busy={busy} error={error} onConnect={(path, name) => act(async () => setRepository(await api.connectRepository(path, name)))} /> :
          !investigation ? <NewInvestigation repository={repository} busy={busy} error={error} onStart={(issue, iterations, knowledge, github) => act(async () => setInvestigation(await api.createInvestigation(repository.id, issue, iterations, knowledge, github)))} /> :
          <Workspace repository={repository} investigation={investigation} evidence={evidence} hypotheses={hypotheses} patch={patch} tab={tab} busy={busy} error={error}
            onTab={setTab} onPatch={setPatch} act={act} onNew={() => { setInvestigation(null); setEvidence([]); setHypotheses([]); setPatch(null); setTab("overview"); }} />}
      </main>
    </div>
  );
}

const message = (value: unknown) => value instanceof Error ? value.message : "Something went wrong";

function ConnectView({ busy, error, onConnect }: { busy: boolean; error: string; onConnect: (path: string, name: string) => void }) {
  const [path, setPath] = useState("sample_repos/vulnerable-fastapi-app");
  const [name, setName] = useState("Vulnerable FastAPI");
  return <section className="entry-grid">
    <div className="hero-copy"><div className="eyebrow">EVIDENCE-DRIVEN ENGINEERING</div><h1>Find the cause.<br /><em>Prove</em> the fix.</h1><p>Trace coordinates repository code, documentation, and history into one auditable investigation—then waits for you before changing a line.</p>
      <div className="pipeline"><span>Inspect</span><ArrowRight /><span>Hypothesize</span><ArrowRight /><span>Validate</span><ArrowRight /><span>Approve</span></div></div>
    <form className="card connect-card" onSubmit={(event) => { event.preventDefault(); onConnect(path, name); }}>
      <div className="card-kicker"><GitBranch size={16} /> REPOSITORY</div><h2>Connect a codebase</h2><p>Paths must be inside the server’s allowed repository root.</p>
      <label>Repository path<input value={path} onChange={(e) => setPath(e.target.value)} required /></label>
      <label>Display name <span>optional</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
      {error && <ErrorBanner text={error} />}<button className="primary" disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <ArrowRight />} Connect repository</button>
    </form>
  </section>;
}

function NewInvestigation({ repository, busy, error, onStart }: { repository: Repository; busy: boolean; error: string; onStart: (issue: string, iterations: number, knowledge: boolean, github: string) => void }) {
  const [issue, setIssue] = useState("Login returns 401 after refresh."); const [iterations, setIterations] = useState(3); const [knowledge, setKnowledge] = useState(true); const [github, setGithub] = useState("");
  return <section className="new-case"><div className="context-bar"><span><GitBranch size={15} /> {repository.name}</span><code>{repository.path}</code></div>
    <div className="case-layout"><div><div className="eyebrow">NEW INVESTIGATION</div><h1>What broke?</h1><p>Describe observed behavior, not your suspected solution. The system will gather evidence before forming a conclusion.</p></div>
      <form className="card case-form" onSubmit={(e) => { e.preventDefault(); onStart(issue, iterations, knowledge, github); }}>
        <label>Issue report<textarea rows={6} value={issue} onChange={(e) => setIssue(e.target.value)} required /></label>
        <div className="form-row"><label>Max iterations<input type="number" min="1" max="10" value={iterations} onChange={(e) => setIterations(Number(e.target.value))} /></label><label>GitHub repository <span>optional</span><input placeholder="owner/repository" value={github} onChange={(e) => setGithub(e.target.value)} /></label></div>
        <label className="check"><input type="checkbox" checked={knowledge} onChange={(e) => setKnowledge(e.target.checked)} /><span><strong>Consult Knowledge MCP</strong><small>Search internal and library documentation using Qdrant.</small></span></label>
        {error && <ErrorBanner text={error} />}<button className="primary" disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <Search />} Start investigation</button>
      </form></div></section>;
}

function Workspace(props: { repository: Repository; investigation: Investigation; evidence: Evidence[]; hypotheses: Hypothesis[]; patch: PatchProposal | null; tab: Tab; busy: boolean; error: string; onTab: (tab: Tab) => void; onPatch: (patch: PatchProposal) => void; act: (fn: () => Promise<void>) => void; onNew: () => void }) {
  const { investigation: item } = props; const running = ["queued", "running"].includes(item.status);
  return <section className="workspace"><aside><div className="repo-label">ACTIVE REPOSITORY</div><strong>{props.repository.name}</strong><nav>{(["overview", "evidence", "hypotheses", "patch"] as Tab[]).map((tab) => <button className={props.tab === tab ? "active" : ""} key={tab} onClick={() => props.onTab(tab)}><span>{tab === "overview" ? "01" : tab === "evidence" ? "02" : tab === "hypotheses" ? "03" : "04"}</span>{tab}</button>)}</nav><button className="new-button" onClick={props.onNew}>+ New investigation</button></aside>
    <div className="work-content"><header className="case-header"><div><div className="eyebrow">INVESTIGATION / {item.id.slice(0, 8)}</div><h1>{item.issue}</h1></div><Status status={item.status} /></header>
      {props.error && <ErrorBanner text={props.error} />}
      {running && <RunningState />}
      {!running && props.tab === "overview" && <Overview item={item} evidence={props.evidence} hypotheses={props.hypotheses} />}
      {!running && props.tab === "evidence" && <EvidenceList evidence={props.evidence} />}
      {!running && props.tab === "hypotheses" && <HypothesisList hypotheses={props.hypotheses} />}
      {!running && props.tab === "patch" && <PatchPanel {...props} />}
    </div></section>;
}

function Status({ status }: { status: string }) { return <span className={`status ${status}`}>{status === "running" || status === "queued" ? <LoaderCircle className="spin" /> : status === "completed" ? <CheckCircle2 /> : <AlertTriangle />}{status}</span>; }
function RunningState() { return <div className="running"><div className="radar"><Search /><i /><i /><i /></div><h2>Investigation in progress</h2><p>Specialists are collecting code, documentation, and historical evidence.</p><div className="steps"><span className="done">Repository connected</span><span className="active">Evidence loop active</span><span>Root cause decision</span></div></div>; }

function Overview({ item, evidence, hypotheses }: { item: Investigation; evidence: Evidence[]; hypotheses: Hypothesis[] }) {
  const top = [...hypotheses].sort((a, b) => b.confidence - a.confidence)[0];
  return <><div className="metric-grid"><Metric label="Evidence items" value={evidence.length} /><Metric label="Hypotheses" value={hypotheses.length} /><Metric label="Sufficiency" value={item.evidence_sufficient ? "Met" : "Not met"} accent={item.evidence_sufficient} /><Metric label="Termination" value={item.termination_reason || "—"} /></div>
    <section className="decision-panel"><div className="section-label"><ShieldCheck size={17} /> ROOT CAUSE DECISION</div><h2>{item.root_cause || "Evidence was insufficient for a defensible root cause."}</h2>{top && <div className="confidence"><span>Leading confidence</span><div><i style={{ width: `${top.confidence * 100}%` }} /></div><strong>{Math.round(top.confidence * 100)}%</strong></div>}</section>
    {item.report && <details className="report"><summary>View full supervisor report</summary><pre>{item.report}</pre></details>}</>;
}
function Metric({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) { return <div className="metric"><span>{label}</span><strong className={accent ? "positive" : ""}>{value}</strong></div>; }

function EvidenceList({ evidence }: { evidence: Evidence[] }) { return <section><div className="section-head"><div><div className="eyebrow">PROVENANCE LEDGER</div><h2>{evidence.length} evidence records</h2></div></div><div className="evidence-list">{evidence.map((item) => { const Icon = sourceIcon[item.source_type] || FileCode2; return <article key={item.id}><div className="evidence-id">{item.id}</div><div className="source-icon"><Icon /></div><div><div className="evidence-meta"><span>{item.source_type}</span>{item.file && <code>{item.file}{item.line_start ? `:${item.line_start}` : ""}</code>}</div><p>{item.observation}</p></div><div className="quality">{item.quality != null ? `${Math.round(item.quality * 100)}%` : "—"}<small>quality</small></div></article>; })}</div></section>; }

function HypothesisList({ hypotheses }: { hypotheses: Hypothesis[] }) { return <section><div className="section-head"><div><div className="eyebrow">COMPETING EXPLANATIONS</div><h2>Ranked hypotheses</h2></div></div><div className="hypothesis-list">{[...hypotheses].sort((a, b) => b.confidence - a.confidence).map((item, index) => <article key={item.id}><div className="rank">{String(index + 1).padStart(2, "0")}</div><div className="hypothesis-main"><div><span className={`pill ${item.status}`}>{item.status}</span><strong>{item.id}</strong></div><h3>{item.statement}</h3>{item.recommendation && <p>{item.recommendation}</p>}<div className="evidence-refs">Evidence: {item.evidence.join(", ") || "none"}</div></div><div className="score">{Math.round(item.confidence * 100)}<small>% confidence</small></div></article>)}</div></section>; }

function PatchPanel(props: { investigation: Investigation; patch: PatchProposal | null; onPatch: (patch: PatchProposal) => void; busy: boolean; act: (fn: () => Promise<void>) => void }) {
  const [path, setPath] = useState("app/services/auth_service.py"); const [content, setContent] = useState(""); const [feedback, setFeedback] = useState("");
  const lines = useMemo(() => (props.patch?.diff || "").split("\n"), [props.patch?.diff]);
  if (!props.patch) return <section className="patch-empty"><div className="section-label"><FileCode2 /> PATCH PROPOSAL</div><h2>Create a reviewable diff</h2><p>Paste the complete proposed file. Validation happens before any approval is requested.</p><label>Repository-relative path<input value={path} onChange={(e) => setPath(e.target.value)} /></label><label>Proposed complete content<textarea className="code-input" rows={14} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Paste the complete replacement file…" /></label><button className="primary" disabled={props.busy || !content} onClick={() => props.act(async () => props.onPatch(await api.proposePatch(props.investigation.id, path, content, true)))}><FileCode2 /> Generate & validate diff</button></section>;
  return <section><div className="patch-toolbar"><div><div className="eyebrow">PATCH / {props.patch.proposal_id?.slice(0, 8)}</div><h2>{props.patch.path}</h2></div><span className={`pill ${props.patch.status === "waiting_for_approval" ? "supported" : props.patch.status}`}>{props.patch.status.replaceAll("_", " ")}</span></div>
    <div className="diff">{lines.map((line, index) => <div key={index} className={line.startsWith("+") && !line.startsWith("+++") ? "add" : line.startsWith("-") && !line.startsWith("---") ? "remove" : line.startsWith("@@") ? "hunk" : ""}><span>{index + 1}</span><code>{line || " "}</code></div>)}</div>
    {props.patch.status === "waiting_for_approval" && <div className="approval"><div><ShieldCheck /><div><strong>Human decision required</strong><p>Approval applies exactly this validated proposal.</p></div></div><div className="change-box"><input placeholder="Feedback for requested changes" value={feedback} onChange={(e) => setFeedback(e.target.value)} /><button disabled={!feedback || props.busy} onClick={() => props.act(async () => props.onPatch(await api.requestChanges(props.investigation.id, feedback)))}>Request changes</button></div><div className="approval-actions"><button className="danger" disabled={props.busy} onClick={() => props.act(async () => props.onPatch(await api.rejectPatch(props.investigation.id)))}><X /> Reject</button><button className="approve" disabled={props.busy} onClick={() => props.act(async () => props.onPatch(await api.approvePatch(props.investigation.id)))}><Check /> Approve & apply</button></div></div>}
  </section>;
}

function ErrorBanner({ text }: { text: string }) { return <div className="error"><AlertTriangle />{text}</div>; }

export default App;
