#!/usr/bin/env python3
"""
GitHub content fetcher for SemOps ingestion pipeline.

Uses the `gh` CLI to fetch files from GitHub repositories, supporting
private repos through authenticated gh CLI sessions.

Usage:
    from github_fetcher import GitHubFetcher

    fetcher = GitHubFetcher("semops-ai", "semops-core")
    files = fetcher.list_files("docs", extensions=[".md"])
    content, metadata = fetcher.fetch_file("docs/SEMANTIC_OPERATIONS/semantic-operations.md")
"""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FileMetadata:
    """Metadata for a fetched file."""

    path: str
    size_bytes: int
    sha: str
    content_hash: str  # SHA256 of content


@dataclass
class FetchedFile:
    """A file fetched from GitHub."""

    content: str
    metadata: FileMetadata


class GitHubFetcher:
    """
    Fetches files from GitHub using the gh CLI.

    Requires `gh` CLI to be installed and authenticated.
    """

    def __init__(self, owner: str, repo: str, branch: str = "main"):
        """
        Initialize fetcher.

        Args:
            owner: GitHub repository owner
            repo: Repository name
            branch: Branch to fetch from
        """
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self._verify_gh_cli()

    def _verify_gh_cli(self) -> None:
        """Verify gh CLI is available and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError("gh CLI not authenticated. Run 'gh auth login' first.")
        except FileNotFoundError:
            raise RuntimeError("gh CLI not found. Install from https://cli.github.com/")

    def _run_gh_api(self, endpoint: str) -> dict:
        """
        Run a gh api command and return JSON response.

        Args:
            endpoint: API endpoint path

        Returns:
            Parsed JSON response

        Raises:
            RuntimeError: If API call fails
        """
        cmd = ["gh", "api", endpoint]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            raise RuntimeError(f"gh api failed: {result.stderr}")

        return json.loads(result.stdout)

    def list_files(
        self,
        base_path: str = "",
        extensions: Optional[list[str]] = None,
        include_dirs: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ) -> list[str]:
        """
        List files in repository.

        Args:
            base_path: Base directory to search from
            extensions: File extensions to include (e.g., [".md"])
            include_dirs: Subdirectories to include (relative to base_path)
            exclude_patterns: Glob patterns to exclude

        Returns:
            List of file paths relative to repo root
        """
        files: list[str] = []

        # Determine directories to scan
        if include_dirs:
            dirs_to_scan = [f"{base_path}/{d}" if base_path else d for d in include_dirs]
        else:
            dirs_to_scan = [base_path] if base_path else [""]

        for dir_path in dirs_to_scan:
            try:
                endpoint = f"repos/{self.owner}/{self.repo}/contents/{dir_path}"
                if self.branch != "main":
                    endpoint += f"?ref={self.branch}"

                items = self._run_gh_api(endpoint)

                # Handle single file response
                if isinstance(items, dict):
                    items = [items]

                for item in items:
                    if item["type"] == "file":
                        file_path = item["path"]

                        # Check extension filter
                        if extensions:
                            if not any(file_path.endswith(ext) for ext in extensions):
                                continue

                        # Check exclude patterns
                        if exclude_patterns:
                            if any(fnmatch.fnmatch(file_path, pat) for pat in exclude_patterns):
                                continue

                        files.append(file_path)

                    elif item["type"] == "dir":
                        # Recursively list subdirectory
                        sub_files = self.list_files(
                            item["path"],
                            extensions=extensions,
                            exclude_patterns=exclude_patterns,
                        )
                        files.extend(sub_files)

            except RuntimeError as e:
                if "404" in str(e):
                    # Directory doesn't exist, skip
                    continue
                raise

        return sorted(files)

    def fetch_file(self, path: str) -> FetchedFile:
        """
        Fetch a single file from the repository.

        Args:
            path: File path relative to repo root

        Returns:
            FetchedFile with content and metadata

        Raises:
            RuntimeError: If file fetch fails
        """
        endpoint = f"repos/{self.owner}/{self.repo}/contents/{path}"
        if self.branch != "main":
            endpoint += f"?ref={self.branch}"

        data = self._run_gh_api(endpoint)

        # Decode base64 content
        content = base64.b64decode(data["content"]).decode("utf-8")

        # Calculate content hash
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        metadata = FileMetadata(
            path=data["path"],
            size_bytes=data["size"],
            sha=data["sha"],
            content_hash=content_hash,
        )

        return FetchedFile(content=content, metadata=metadata)

    def build_uri(self, path: str) -> str:
        """
        Build a github:// URI for a file.

        Args:
            path: File path relative to repo root

        Returns:
            URI in format github://owner/repo/path
        """
        return f"github://{self.owner}/{self.repo}/{path}"


if __name__ == "__main__":
    # Simple test/demo
    import sys

    if len(sys.argv) < 3:
        print("Usage: python github_fetcher.py <owner> <repo> [base_path]")
        sys.exit(1)

    owner = sys.argv[1]
    repo = sys.argv[2]
    base_path = sys.argv[3] if len(sys.argv) > 3 else ""

    fetcher = GitHubFetcher(owner, repo)

    print(f"Listing .md files in {owner}/{repo}/{base_path}:")
    files = fetcher.list_files(base_path, extensions=[".md"])

    for f in files[:10]:  # Show first 10
        print(f"  - {f}")

    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")

    if files:
        print(f"\nFetching first file: {files[0]}")
        fetched = fetcher.fetch_file(files[0])
        print(f"  Size: {fetched.metadata.size_bytes} bytes")
        print(f"  Hash: {fetched.metadata.content_hash[:16]}...")
        print(f"  Content preview: {fetched.content[:100]}...")
