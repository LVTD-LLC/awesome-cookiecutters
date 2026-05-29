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
DATA_PATH = ROOT / "entities.yml"
SUPPORTED_METADATA_MODES = {"github", "none"}

HEADER = """# Awesome Cookiecutters [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

A curated list of useful [Cookiecutter](https://github.com/cookiecutter/cookiecutter) templates, skills, and related resources.

We keep this list simple: useful entities, short descriptions, and enough structure to make discovery easy. Search will live at <https://awesome-repos.cap.gregagi.com/> when ready.

Entity data is generated from [entities.yml](entities.yml). GitHub repository metadata is refreshed by GitHub Actions.
"""

FOOTER_TEMPLATE = """## Contributing

Pull requests are welcome. Please add entities that are useful, maintained, and clearly documented.

Add entries to `entities.yml`, then regenerate the README:

```sh
python -m pip install -r scripts/requirements.txt
GITHUB_TOKEN="$(gh auth token)" python scripts/update_readme.py
```

For each entry, include:

- Type
- Link
- Short description
- Category

Supported entity types are currently: {supported_types}. New simple entity types can be added under `types` in `entities.yml`.

Entries can be placed anywhere in the flat `entities` list. The `category` field controls the README section; the top-level `categories` list only controls display order.

Keep descriptions concise and neutral.
"""


class GitHubAPIError(RuntimeError):
    pass


class DataValidationError(RuntimeError):
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


def render_entity(entry: dict[str, Any], metadata: dict[str, Any]) -> str:
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
    entry_text = f"[{name}]({url}) - {description}{metadata_suffix}"
    if archived:
        entry_text = f"~~{entry_text}~~"
    return f"- {entry_text}"


def metadata_mode_for(entry: dict[str, Any], type_configs: dict[str, dict[str, Any]]) -> str:
    return type_configs[entry["type"]].get("metadata", "none")


def maybe_fetch_entry_metadata(
    entry: dict[str, Any],
    type_configs: dict[str, dict[str, Any]],
    token: str | None,
    fetch: bool,
) -> dict[str, Any]:
    if not fetch or metadata_mode_for(entry, type_configs) != "github":
        return {}
    return fetch_entry_metadata(entry, token)


def category_names(data: dict[str, Any]) -> list[str]:
    configured = list(data.get("categories", []))
    discovered = []

    for entry in data["entities"]:
        category = entry["category"]
        if category not in configured and category not in discovered:
            discovered.append(category)

    return configured + discovered


def entries_for_category(data: dict[str, Any], category: str) -> list[dict[str, Any]]:
    return [entry for entry in data["entities"] if entry["category"] == category]


def entries_by_type(entries: list[dict[str, Any]], type_names: list[str]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped = []
    for type_name in type_names:
        type_entries = [entry for entry in entries if entry["type"] == type_name]
        if type_entries:
            grouped.append((type_name, type_entries))
    return grouped


def render_footer(data: dict[str, Any]) -> str:
    supported_types = ", ".join(f"`{type_name}`" for type_name in data["types"])
    return FOOTER_TEMPLATE.format(supported_types=supported_types)


def render_readme(data: dict[str, Any], token: str | None, fetch: bool) -> str:
    categories = [category for category in category_names(data) if entries_for_category(data, category)]
    type_names = list(data["types"])
    lines = [HEADER, "## Contents", ""]

    for category in categories:
        lines.append(f"- [{category}](#{slugify_heading(category)})")
    lines.append("- [Contributing](#contributing)")
    lines.append("")

    for category in categories:
        category_entries = entries_for_category(data, category)
        grouped_entries = entries_by_type(category_entries, type_names)

        lines.append(f"## {category}")
        lines.append("")

        if len(grouped_entries) == 1:
            for entry in grouped_entries[0][1]:
                metadata = maybe_fetch_entry_metadata(entry, data["types"], token, fetch)
                lines.append(render_entity(entry, metadata))
        else:
            for index, (type_name, entries) in enumerate(grouped_entries):
                if index > 0:
                    lines.append("")
                default_type_label = type_name.replace("-", " ").replace("_", " ").title()
                type_label = data["types"][type_name].get("label", default_type_label)
                lines.append(f"### {type_label}")
                lines.append("")
                for entry in entries:
                    metadata = maybe_fetch_entry_metadata(entry, data["types"], token, fetch)
                    lines.append(render_entity(entry, metadata))
        lines.append("")

    lines.append(render_footer(data))
    return "\n".join(lines).rstrip() + "\n"


def require_string(entry: dict[str, Any], field: str, index: int) -> None:
    if not isinstance(entry.get(field), str) or not entry[field].strip():
        raise DataValidationError(f"Entry #{index} must include a non-empty `{field}` string.")


def validate_data(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise DataValidationError("entities.yml must contain a mapping at the top level.")

    types = data.get("types")
    if not isinstance(types, dict) or not types:
        raise DataValidationError("entities.yml must define at least one entity type under `types`.")

    for type_name, type_config in types.items():
        if not isinstance(type_name, str) or not type_name:
            raise DataValidationError("Entity type names must be non-empty strings.")
        if not isinstance(type_config, dict):
            raise DataValidationError(f"Type `{type_name}` must be a mapping.")
        metadata_mode = type_config.get("metadata", "none")
        if metadata_mode not in SUPPORTED_METADATA_MODES:
            supported = ", ".join(sorted(SUPPORTED_METADATA_MODES))
            raise DataValidationError(
                f"Type `{type_name}` uses unsupported metadata mode `{metadata_mode}`. Supported modes: {supported}."
            )

    categories = data.get("categories", [])
    if not isinstance(categories, list) or not all(isinstance(category, str) for category in categories):
        raise DataValidationError("`categories` must be a list of strings.")
    if len(categories) != len(set(categories)):
        raise DataValidationError("`categories` must not contain duplicate entries.")

    entities = data.get("entities")
    if not isinstance(entities, list):
        raise DataValidationError("entities.yml must define a flat `entities` list.")

    for index, entry in enumerate(entities, start=1):
        if not isinstance(entry, dict):
            raise DataValidationError(f"Entry #{index} must be a mapping.")
        for field in ("name", "type", "category", "url", "description"):
            require_string(entry, field, index)
        if entry["type"] not in types:
            supported = ", ".join(types)
            raise DataValidationError(
                f"Entry #{index} ({entry['name']}) has unsupported type `{entry['type']}`. Supported types: {supported}."
            )


def load_data() -> dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    validate_data(data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate README.md from entities.yml and GitHub metadata.")
    parser.add_argument("--no-fetch", action="store_true", help="Render without fetching GitHub metadata.")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    content = render_readme(load_data(), token=token, fetch=not args.no_fetch)

    README_PATH.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
