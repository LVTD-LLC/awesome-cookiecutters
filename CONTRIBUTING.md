# Contributing

Thanks for helping improve Awesome Cookiecutters.

## Adding an entity

Please include:

- A supported `type`
- A link
- A short, factual description
- The most relevant category

Good entries are useful, documented, and reasonably maintained. Avoid adding abandoned or very narrow resources unless they are still clearly valuable.

Add entries to the flat `entities` list in `entities.yml`, then regenerate `README.md`:

```sh
python -m pip install -r scripts/requirements.txt
GITHUB_TOKEN="$(gh auth token)" python scripts/update_readme.py
```

GitHub Actions also refreshes README metadata after changes are merged into `main`.

An entry looks like this:

```yaml
- name: example-template
  type: repository
  category: Python Packages and CLI
  url: https://github.com/example/example-template
  description: Template for example Python projects.
```

Entries can be placed anywhere in the flat list. The `category` field controls the README section; the top-level `categories` list only controls display order.

Supported types live under `types` in `entities.yml`. The current supported types are:

- `repository`, `cookiecutter-template`, `copier-template`, `github-template`, `project-generator`, `template-tool`, and `awesome-list` for GitHub-backed entities. These use `metadata: github`, so stars and last commit dates are refreshed automatically.
- `documentation`, `catalog`, and `skill` for non-repository entities. These use `metadata: none`.

To add a simple future type, add it under `types` with a label and `metadata: none`, then use that type on entries. Add a custom metadata mode only when the generator has code to support it.

## Style

- One sentence per description.
- Keep entries alphabetized when practical.
- Prefer direct source links over blog posts or docs pages.
- Set `type` for entries with a specific subtype, including repository-backed template types.
