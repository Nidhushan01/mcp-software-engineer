from __future__ import annotations

import unittest

from mcp_clients.registry import create_github_config
from services.agents.github_agent import GitHubHistoryAgent


class FakeGitHubManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    async def call_tool(self, server: str, tool: str, arguments: dict):
        self.calls.append((server, tool, arguments))
        if tool == "search_issues":
            return {"items": [{"number": 12, "title": "Refresh returns 401", "html_url": "https://example/issues/12"}]}
        if tool == "search_pull_requests":
            return {"items": [{"number": 15, "title": "Fix refresh validation", "html_url": "https://example/pull/15"}]}
        if tool == "list_commits":
            return [{"sha": "abc123456789", "commit": {"message": "Change JWT verification"}}]
        if tool == "search_code":
            return {"items": [{"name": "auth.py", "html_url": "https://example/auth.py"}]}
        if tool == "list_discussions":
            return {"items": [{"number": 7, "title": "Token refresh design", "html_url": "https://example/discussions/7"}]}
        return {"detail": f"result from {tool}"}


class GitHubAgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_history_agent_uses_only_read_tools_and_returns_evidence(self) -> None:
        manager = FakeGitHubManager()
        state = {
            "request": "Login returns 401 after refresh",
            "evidence": [],
            "supervisor_notes": [],
            "github_enabled": True,
            "github_owner": "acme",
            "github_repo": "api",
        }
        result = await GitHubHistoryAgent(manager).research(state)  # type: ignore[arg-type]
        called = {item[1] for item in manager.calls}
        self.assertTrue({"search_issues", "search_pull_requests", "list_commits", "search_code", "list_discussions"}.issubset(called))
        self.assertTrue(called.issubset({"search_issues", "issue_read", "search_pull_requests", "pull_request_read", "list_commits", "get_commit", "search_code", "list_discussions", "get_discussion"}))
        self.assertTrue(result["github_searched"])
        self.assertTrue(all(item["source_type"] == "github" for item in result["evidence"]))

    async def test_disabled_agent_does_not_call_github(self) -> None:
        manager = FakeGitHubManager()
        result = await GitHubHistoryAgent(manager).research({"github_enabled": False})  # type: ignore[arg-type]
        self.assertEqual(manager.calls, [])
        self.assertFalse(result["github_searched"])


class GitHubRegistryTest(unittest.TestCase):
    def test_official_server_is_read_only_and_token_is_hidden_from_repr(self) -> None:
        config = create_github_config("secret-token")
        self.assertEqual(config.command, "docker")
        self.assertEqual(config.env["GITHUB_READ_ONLY"], "1")
        self.assertEqual(config.env["GITHUB_LOCKDOWN_MODE"], "1")
        self.assertIn("discussions", config.env["GITHUB_TOOLSETS"])
        self.assertNotIn("secret-token", repr(config))


if __name__ == "__main__":
    unittest.main()
