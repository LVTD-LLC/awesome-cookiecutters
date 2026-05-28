#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
REPOS_PATH = ROOT / "repos.yml"

HEADER = """# Awesome Cookiecutters [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

A curated list of useful [Cookiecutter](https://github.com/cookiecutter/cookiecutter) templates and related resources.

We keep this list simple: great repositories, short descriptions, and enough structure to make discovery easy. Search will live at <https://awesome-repos.cap.gregagi.com/> when ready.

Repository metadata is generated from [repos.yml](repos.yml) and refreshed by GitHub Actions.
"""

FOOTER = """## Contributing

Pull requests are welcome. Please add repositories that are useful, maintained, and clearly documented.

For each entry, include:

- Repository link
- Short description
- The category where it fits best

Keep descriptions concise and neutral.
"""


class GitHubAPIError(RuntimeError):
    pass


def github_request(path: str, token: str | None) -> dict[str, Any]:
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "awesome-cookiecutters-readme-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise GitHubAPIError(f"GitHub API request failed for {url}: {error.code} {body}") from error
    except urllib.error.URLError as error:
        raise GitHubAPIError(f"GitHub API request failed for {url}: {error.reason}") from error


def parse_github_repo(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError(f"Only GitHub repository URLs are supported: {url}")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise ValueError(f"Could not parse GitHub owner and repository from: {url}")

    owner = parts[0]
    repo = parts[1].removesuffix(".git")
    return owner, repo


def fetch_metadata(url: str, token: str | None) -> dict[str, Any]:
    owner, repo = parse_github_repo(url)
    repository = github_request(f"/repos/{owner}/{repo}", token)
    default_branch = repository["default_branch"]
    commit = github_request(f"/repos/{owner}/{repo}/commits/{urllib.parse.quote(default_branch, safe='')}", token)

    return {
        "archived": repository.get("archived", False),
        "last_commit": commit["commit"]["committer"]["date"],
        "stars": repository["stargazers_count"],
    }


def fetch_entry_metadata(entry: dict[str, Any], token: str | None) -> dict[str, Any]:
    try:
        return fetch_metadata(entry["url"], token)
    except (GitHubAPIError, KeyError, TypeError, ValueError) as error:
        print(f"Warning: could not fetch metadata for {entry['url']}: {error}", file=sys.stderr)
        return {"metadata_unavailable": True}


def format_count(value: int) -> str:
    return f"{value:,}"


def format_date(value: str) -> str:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.date().isoformat()


def slugify_heading(value: str) -> str:
    slug = value.lower()
    slug = re.sub(r"[^a-z0-9 -]", "", slug)
    return re.sub(r"\s+", "-", slug).strip("-")


def render_repository(entry: dict[str, Any], metadata: dict[str, Any]) -> str:
    name = entry["name"]
    url = entry["url"]
    description = entry["description"]
    archived = entry.get("archived", False) or metadata.get("archived", False)

    details = []
    if "stars" in metadata:
        details.append(f"{format_count(metadata['stars'])} stars")
    if "last_commit" in metadata:
        details.append(f"last commit {format_date(metadata['last_commit'])}")
    if metadata.get("metadata_unavailable"):
        details.append("metadata unavailable")
    if archived:
        details.append("archived")

    metadata_suffix = f" _{' | '.join(details)}._" if details else ""
    repository_text = f"[{name}]({url}) - {description}{metadata_suffix}"
    if archived:
        repository_text = f"~~{repository_text}~~"
    return f"- {repository_text}"


def render_readme(data: dict[str, Any], token: str | None, fetch: bool) -> str:
    categories = data["categories"]
    lines = [HEADER, "## Contents", ""]

    for category in categories:
        lines.append(f"- [{category['name']}](#{slugify_heading(category['name'])})")
    lines.append("- [Contributing](#contributing)")
    lines.append("")

    for category in categories:
        lines.append(f"## {category['name']}")
        lines.append("")
        for entry in category["repositories"]:
            metadata = fetch_entry_metadata(entry, token) if fetch else {}
            lines.append(render_repository(entry, metadata))
        lines.append("")

    lines.append(FOOTER)
    return "\n".join(lines).rstrip() + "\n"


def load_repos() -> dict[str, Any]:
    with REPOS_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate README.md from repos.yml and GitHub metadata.")
    parser.add_argument("--no-fetch", action="store_true", help="Render without fetching GitHub metadata.")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    content = render_readme(load_repos(), token=token, fetch=not args.no_fetch)

    README_PATH.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
