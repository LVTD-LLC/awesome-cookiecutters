# Contributing

Thanks for helping improve Awesome Cookiecutters.

## Adding a repository

Please include:

- A GitHub repository URL
- A short, factual description
- The most relevant category

Good entries are useful, documented, and reasonably maintained. Avoid adding abandoned or very narrow templates unless they are still clearly valuable.

Add entries to `repos.yml`, then regenerate `README.md`:

```sh
python -m pip install -r scripts/requirements.txt
GITHUB_TOKEN="$(gh auth token)" python scripts/update_readme.py
```

GitHub Actions also refreshes README metadata weekly.

## Style

- One sentence per description.
- Keep entries alphabetized when practical.
- Prefer direct repository links over blog posts or docs pages.
