"""Phase 7: auto-commit, tag and push to dedicated GitHub repo via API + git CLI."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_NAME = "jev-autonomous-eval-harness"
REPO_DESC = "Jev-Automated AI Evaluation & Regression Pipeline — Full Web Dashboard"


class GitHubPusher:
    """Creates/updates the target repo with a scoped PAT (GITHUB_TOKEN env) and pushes main."""

    def __init__(self, root: str | Path = ".", token: str | None = None):
        self.root = Path(root)
        self.token = token or os.environ.get("GITHUB_TOKEN", "")

    @staticmethod
    def _git(args: list[str], cwd: Path) -> tuple[int, str]:
        """Run a git subcommand; return (rc, combined output)."""
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()

    def owner(self) -> str:
        """Resolve authenticated account login from the GitHub API."""
        if not self.token:
            return ""
        try:
            from github import Github
            return Github(self.token).get_user().login
        except Exception:
            return ""

    def ensure_repo(self) -> str:
        """Create the repo if missing; return its clone URL (empty when no token)."""
        if not self.token:
            return ""
        from github import Github
        gh = Github(self.token)
        user = gh.get_user()
        try:
            repo = user.get_repo(REPO_NAME)
        except Exception:
            repo = user.create_repo(REPO_NAME, description=REPO_DESC, auto_init=False, private=False)
        return repo.clone_url

    def commit_all(self, message: str = "feat: jev autopilot cycle results") -> bool:
        """git init/add/conventional-commit inside project root."""
        self._git(["init", "-b", "main"], self.root)
        self._git(["config", "user.email", "jev-bot@autopilot.local"], self.root)
        self._git(["config", "user.name", "Jev Autopilot"], self.root)
        self._git(["add", "-A"], self.root)
        rc, out = self._git(["commit", "-m", message], self.root)
        return rc == 0 or "nothing to commit" in out

    def tag_release(self, tag: str = "v1.0.0-autopilot") -> None:
        """Create annotated release tag."""
        self._git(["tag", "-f", "-a", tag, "-m", f"Jev autopilot release {tag}"], self.root)

    def push(self, clone_url: str, force: bool = True) -> tuple[bool, str]:
        """Add authenticated remote and push main (+tags)."""
        scheme, _, rest = clone_url.partition("://")
        auth_url = f"{scheme}://x-access-token:{self.token}@{rest}"
        self._git(["remote", "remove", "origin"], self.root)
        self._git(["remote", "add", "origin", auth_url], self.root)
        rc, out = self._git(["push", "--force", "origin", "main"] + (["--follow-tags"] if True else []), self.root)
        ok = rc == 0
        return ok, out.replace(self.token, "[REDACTED]") if self.token else out

    def deploy(self, message: str = "feat: jev autopilot full-cycle artifacts", tag: str = "v1.0.0-autopilot") -> dict:
        """Full Phase 7 sequence; returns status dict safe to log/publish."""
        result = {"committed": False, "repo_url": "", "pushed": False, "tag": tag, "detail": ""}
        result["committed"] = self.commit_all(message)
        url = self.ensure_repo()
        if not url:
            result["detail"] = "No GITHUB_TOKEN set — local commit only, push skipped."
            return result
        result["repo_url"] = url
        self.tag_release(tag)
        ok, out = self.push(url)
        result["pushed"], result["detail"] = ok, out[-400:]
        return result
