#!/usr/bin/env python3
"""
Aggregate ADRs from all SemOps repositories into a single index.

Usage:
    python scripts/aggregate_adrs.py > docs/ADR_INDEX.md
    python scripts/aggregate_adrs.py --output docs/ADR_INDEX.md
"""

import argparse
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# Active repos to scan (relative to ~/GitHub/)
REPOS = [
    "semops-core",
    "semops-publisher",
    "semops-docs",
    "semops-data",
    "semops-sites",
]

# Decision document directory
DECISIONS_DIR = "docs/decisions"

# Pattern to extract metadata from ADR frontmatter
STATUS_PATTERN = re.compile(r"\*\*Status:\*\*\s*(\w+(?:\s+\w+)?)", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def get_github_base() -> Path:
    """Get the GitHub directory path."""
    return Path.home() / "GitHub"


def extract_metadata(file_path: Path) -> dict:
    """Extract metadata from an ADR file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"error": str(e)}

    metadata = {
        "filename": file_path.name,
        "path": str(file_path),
        "status": "Unknown",
        "date": None,
        "title": file_path.stem,
    }

    # Extract title from first heading
    title_match = TITLE_PATTERN.search(content)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    # Extract status
    status_match = STATUS_PATTERN.search(content)
    if status_match:
        metadata["status"] = status_match.group(1).strip()

    # Extract date
    date_match = DATE_PATTERN.search(content)
    if date_match:
        metadata["date"] = date_match.group(1)

    return metadata


def categorize_adr(filename: str) -> str:
    """Categorize ADR by its naming pattern."""
    filename_upper = filename.upper()
    if filename_upper.startswith("ADR-"):
        return "ADR"
    elif filename_upper.startswith("ISSUE-"):
        return "Issue"
    elif filename_upper.startswith("PHASE"):
        return "Phase"
    elif filename in ("TEMPLATE.md", "README.md"):
        return "Meta"
    else:
        return "Other"


def scan_repo(repo_name: str) -> list[dict]:
    """Scan a repository for ADRs."""
    github_base = get_github_base()
    decisions_path = github_base / repo_name / DECISIONS_DIR

    if not decisions_path.exists():
        return []

    adrs = []
    for md_file in decisions_path.glob("*.md"):
        if md_file.name in ("TEMPLATE.md", "README.md"):
            continue

        metadata = extract_metadata(md_file)
        metadata["repo"] = repo_name
        metadata["category"] = categorize_adr(md_file.name)
        metadata["relative_path"] = f"{repo_name}/{DECISIONS_DIR}/{md_file.name}"
        adrs.append(metadata)

    return adrs


def generate_index(adrs: list[dict]) -> str:
    """Generate the ADR index markdown."""
    lines = [
        "# SemOps ADR Index",
        "",
        f"> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> **Total ADRs:** {len(adrs)}",
        "",
        "This index aggregates Architecture Decision Records from all active SemOps repositories.",
        "",
        "---",
        "",
    ]

    # Group by repo
    by_repo = defaultdict(list)
    for adr in adrs:
        by_repo[adr["repo"]].append(adr)

    # Status summary
    status_counts = defaultdict(int)
    for adr in adrs:
        status_counts[adr["status"]] += 1

    lines.extend([
        "## Summary by Status",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ])
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(["", "---", ""])

    # By repository
    lines.append("## By Repository")
    lines.append("")

    for repo in REPOS:
        repo_adrs = by_repo.get(repo, [])
        lines.append(f"### {repo}")
        lines.append("")

        if not repo_adrs:
            lines.append("_No ADRs found._")
            lines.append("")
            continue

        lines.append("| Document | Status | Date | Category |")
        lines.append("|----------|--------|------|----------|")

        # Sort by category then filename
        sorted_adrs = sorted(repo_adrs, key=lambda x: (x["category"], x["filename"]))

        for adr in sorted_adrs:
            title = adr["title"]
            status = adr["status"]
            date = adr["date"] or "-"
            category = adr["category"]
            # Relative link from ike-semantic-ops/docs/
            rel_path = f"../../{adr['relative_path']}" if adr["repo"] != "ike-semantic-ops" else f"decisions/{adr['filename']}"
            lines.append(f"| [{title}]({rel_path}) | {status} | {date} | {category} |")

        lines.append("")

    # Timeline view (ADRs with dates)
    dated_adrs = [a for a in adrs if a["date"]]
    if dated_adrs:
        lines.extend([
            "---",
            "",
            "## Timeline",
            "",
            "| Date | Repo | Document | Status |",
            "|------|------|----------|--------|",
        ])

        for adr in sorted(dated_adrs, key=lambda x: x["date"], reverse=True):
            date = adr["date"]
            repo = adr["repo"]
            title = adr["title"]
            status = adr["status"]
            lines.append(f"| {date} | {repo} | {title} | {status} |")

        lines.append("")

    lines.extend([
        "---",
        "",
        "_Generated by `scripts/aggregate_adrs.py`_",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Aggregate ADRs from SemOps repos")
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
        type=Path,
    )
    args = parser.parse_args()

    # Scan all repos
    all_adrs = []
    for repo in REPOS:
        all_adrs.extend(scan_repo(repo))

    # Generate index
    index_content = generate_index(all_adrs)

    # Output
    if args.output:
        args.output.write_text(index_content, encoding="utf-8")
        print(f"ADR index written to {args.output}")
    else:
        print(index_content)


if __name__ == "__main__":
    main()
