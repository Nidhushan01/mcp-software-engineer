import type { Evidence, Hypothesis, Investigation, PatchProposal, Repository } from "./types";

const BASE = import.meta.env.VITE_API_URL || "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  connectRepository: (path: string, name?: string) => request<Repository>("/repositories/connect", {
    method: "POST", body: JSON.stringify({ path, name: name || undefined }),
  }),
  createInvestigation: (repositoryId: string, issue: string, maxIterations: number, useKnowledge: boolean, githubRepository?: string) =>
    request<Investigation>("/investigations", {
      method: "POST",
      body: JSON.stringify({ repository_id: repositoryId, issue, max_iterations: maxIterations, use_knowledge: useKnowledge, github_repository: githubRepository || undefined }),
    }),
  getInvestigation: (id: string) => request<Investigation>(`/investigations/${id}`),
  getEvidence: (id: string) => request<{ evidence: Evidence[] }>(`/investigations/${id}/evidence`),
  getHypotheses: (id: string) => request<{ hypotheses: Hypothesis[] }>(`/investigations/${id}/hypotheses`),
  getPatch: (id: string) => request<PatchProposal>(`/investigations/${id}/patch`),
  proposePatch: (id: string, path: string, newContent: string, requireConfirmed: boolean) => request<PatchProposal>(`/investigations/${id}/patch`, {
    method: "POST", body: JSON.stringify({ path, new_content: newContent, require_confirmed: requireConfirmed }),
  }),
  approvePatch: (id: string) => request<PatchProposal>(`/investigations/${id}/approve`, { method: "POST" }),
  rejectPatch: (id: string) => request<PatchProposal>(`/investigations/${id}/reject`, { method: "POST" }),
  requestChanges: (id: string, feedback: string) => request<PatchProposal>(`/investigations/${id}/request-changes`, {
    method: "POST", body: JSON.stringify({ feedback }),
  }),
};
