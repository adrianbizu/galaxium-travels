# github-issues-mcp-server

Read-only MCP server (stdio, Node.js) that reads issues from GitHub repositories. It works with any
repository, each with its own access token.

## Tools

| Tool | Description |
|---|---|
| `list-issues` | List issues (`state`, `labels`, `per_page`, `page`); PRs excluded |
| `get-issue` | Single issue with full body |
| `list-issue-comments` | Comments of an issue |
| `search-issues` | Text search within the repository |
| `get-auth-status` | Config file path, default repo, repos with own token, token use + rate limit for a repo (never shows tokens) |

Every tool takes an optional `repo` argument: a GitHub URL (`https://github.com/owner/name`) or `owner/name`.

## Build

```bash
npm install
npm run build
```

## Configuration: repository and access tokens

Edit `github-config.json` in this directory (copy `github-config.example.json` to start). It is
**re-read on every request**, so changes apply immediately, with no restart. The file is git-ignored.

```json
{
  "defaultRepository": "https://github.com/owner/repo",
  "defaultToken": "",
  "repositories": {
    "https://github.com/owner/repo": { "token": "ghp_..." },
    "other-owner/other-repo": { "token": "ghp_..." }
  }
}
```

| Key | Meaning |
|---|---|
| `defaultRepository` | Repository used when a tool call has no `repo` argument |
| `defaultToken` | Token for repositories that have no entry under `repositories` |
| `repositories` | Per-repository token, keyed by URL or `owner/name` (both forms match each other) |

**Repository** resolution: `repo` tool argument → `defaultRepository` → `GITHUB_REPOSITORY` env var.

**Token** resolution: `repositories[<repo>].token` → `defaultToken` → `GITHUB_TOKEN` env var → none.
Without a token, public repositories still work (60 requests/hour). Private repositories need a token.

To use another config location, set `GITHUB_CONFIG_FILE` in the `env` block of the server entry in `.bob/mcp.json`.
