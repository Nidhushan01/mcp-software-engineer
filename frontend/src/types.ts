export type InvestigationStatus = "queued" | "running" | "completed" | "failed";

export interface Repository {
  id: string;
  name: string;
  path: string;
  connected_at: string;
}

export interface Investigation {
  id: string;
  repository_id: string;
  issue: string;
  status: InvestigationStatus;
  created_at: string;
  updated_at: string;
  termination_reason?: string;
  evidence_sufficient?: boolean;
  root_cause?: string;
  report?: string;
  error?: string;
}

export interface Evidence {
  id: string;
  source_type: string;
  observation: string;
  file?: string;
  line_start?: number;
  line_end?: number;
  symbol?: string;
  quality?: number;
}

export interface Hypothesis {
  id: string;
  statement: string;
  status: "unverified" | "supported" | "contradicted" | "confirmed";
  confidence: number;
  evidence: string[];
  recommendation?: string;
}

export interface PatchProposal {
  status: string;
  proposal_id?: string;
  path?: string;
  diff?: string;
  validation?: Record<string, unknown>;
  feedback?: string;
  apply_result?: Record<string, unknown>;
}
