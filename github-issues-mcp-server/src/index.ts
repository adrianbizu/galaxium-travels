#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/server";
import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import { z } from "zod/v4";

const API_BASE = "https://api.github.com";

// The config file sits next to the build/ directory by default and is re-read on every request,
// so it can be edited at any time without restarting the server.
const CONFIG_FILE = process.env.GITHUB_CONFIG_FILE
  ? resolve(process.env.GITHUB_CONFIG_FILE)
  : resolve(dirname(fileURLToPath(import.meta.url)), "..", "github-config.json");

interface Config {
  /** Repository (URL or "owner/name") used when a tool call does not pass `repo`. */
  defaultRepository?: string;
  /** Token used for repositories without their own entry. */
  defaultToken?: string;
  /** Per-repository settings, keyed by URL or "owner/name". */
  repositories?: Record<string, { token?: string }>;
}

function loadConfig(): Config {
  let raw: string;
  try {
    raw = readFileSync(CONFIG_FILE, "utf8");
  } catch {
    return {}; // no config file: fall back to environment variables only
  }
  if (!raw.trim()) return {};
  try {
    return JSON.parse(raw) as Config;
  } catch (error) {
    throw new Error(`Invalid JSON in ${CONFIG_FILE}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

interface Repo {
  owner: string;
  name: string;
  /** Normalized lowercase "owner/name", used as lookup key. */
  key: string;
}

/** Accepts "owner/name", https://github.com/owner/name[.git][/...], github.com/owner/name, git@github.com:owner/name.git */
function parseRepo(value: string): Repo | undefined {
  const match =
    /^([\w.-]+)\/([\w.-]+)$/.exec(value.trim()) ??
    /^(?:https?:\/\/|git@)?(?:www\.)?github\.com[/:]([\w.-]+)\/([\w.-]+?)(?:\.git)?(?:[/?#].*)?$/i.exec(value.trim());
  if (!match) return undefined;
  const owner = match[1];
  const name = match[2].replace(/\.git$/i, "");
  return { owner, name, key: `${owner}/${name}`.toLowerCase() };
}

/** Repository resolution: `repo` argument -> config.defaultRepository -> GITHUB_REPOSITORY env var. */
function resolveRepo(arg?: string): Repo {
  const value = (arg || loadConfig().defaultRepository || process.env.GITHUB_REPOSITORY || "").trim();
  const repo = parseRepo(value);
  if (!repo) {
    throw new Error(
      `Repository must be a GitHub URL or "owner/name" (got "${value}"). ` +
        `Pass the 'repo' argument or set "defaultRepository" in ${CONFIG_FILE}.`,
    );
  }
  return repo;
}

/**
 * Token resolution, evaluated on every request:
 *   1. config.repositories[<repo>].token
 *   2. config.defaultToken
 *   3. GITHUB_TOKEN environment variable
 *   4. none -> unauthenticated requests (works for public repos, lower rate limit)
 */
function getToken(repo?: Repo): string | undefined {
  const config = loadConfig();
  if (repo) {
    for (const [k, v] of Object.entries(config.repositories ?? {})) {
      if (parseRepo(k)?.key === repo.key && v.token?.trim()) return v.token.trim();
    }
  }
  return config.defaultToken?.trim() || process.env.GITHUB_TOKEN?.trim() || undefined;
}

async function github(
  repo: Repo | undefined,
  path: string,
  params: Record<string, string | number | undefined> = {},
) {
  const url = new URL(API_BASE + path);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  const headers: Record<string, string> = {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "github-issues-mcp-server",
  };
  const token = getToken(repo);
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, { headers });
  if (!res.ok) {
    const body = await res.text();
    const hint =
      res.status === 401
        ? " (the access token is invalid or expired - update it in the config file)"
        : res.status === 403 || res.status === 429
          ? " (possible rate limit or missing permissions - set a token for this repository in the config file)"
          : "";
    throw new Error(`GitHub API ${res.status} ${res.statusText}${hint}: ${body.slice(0, 500)}`);
  }
  return res.json();
}

interface GitHubIssue {
  number: number;
  title: string;
  state: string;
  html_url: string;
  user: { login: string } | null;
  labels: Array<string | { name?: string }>;
  assignees?: Array<{ login: string }>;
  comments: number;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  body?: string | null;
  pull_request?: unknown;
}

const labelNames = (issue: GitHubIssue) =>
  issue.labels.map((l) => (typeof l === "string" ? l : l.name ?? ""));

const summarize = (issue: GitHubIssue) => ({
  number: issue.number,
  title: issue.title,
  state: issue.state,
  author: issue.user?.login ?? null,
  labels: labelNames(issue),
  assignees: (issue.assignees ?? []).map((a) => a.login),
  comments: issue.comments,
  created_at: issue.created_at,
  updated_at: issue.updated_at,
  closed_at: issue.closed_at,
  url: issue.html_url,
});

const ok = (data: unknown) => ({ content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] });
const fail = (error: unknown) => ({
  content: [{ type: "text" as const, text: error instanceof Error ? error.message : String(error) }],
  isError: true,
});

const repoArg = z
  .string()
  .optional()
  .describe(
    'Repository as GitHub URL or "owner/name". Defaults to "defaultRepository" in the config file (or the GITHUB_REPOSITORY env var).',
  );

const server = new McpServer({ name: "github-issues-mcp-server", version: "1.0.0" });

server.registerTool(
  "list-issues",
  {
    description: "List issues of the GitHub repository (pull requests are excluded).",
    inputSchema: z.object({
      repo: repoArg,
      state: z.enum(["open", "closed", "all"]).default("open").describe("Issue state filter"),
      labels: z.string().optional().describe("Comma-separated label names"),
      per_page: z.number().int().min(1).max(100).default(30).describe("Results per page"),
      page: z.number().int().min(1).default(1).describe("Page number"),
    }),
  },
  async ({ repo, state, labels, per_page, page }) => {
    try {
      const r = resolveRepo(repo);
      const data = (await github(r, `/repos/${r.owner}/${r.name}/issues`, {
        state,
        labels,
        per_page,
        page,
      })) as GitHubIssue[];
      // The issues endpoint also returns pull requests; filter them out.
      return ok(data.filter((i) => !i.pull_request).map(summarize));
    } catch (error) {
      return fail(error);
    }
  },
);

server.registerTool(
  "get-issue",
  {
    description: "Get a single issue including its full body.",
    inputSchema: z.object({
      repo: repoArg,
      issue_number: z.number().int().min(1).describe("Issue number"),
    }),
  },
  async ({ repo, issue_number }) => {
    try {
      const r = resolveRepo(repo);
      const issue = (await github(r, `/repos/${r.owner}/${r.name}/issues/${issue_number}`)) as GitHubIssue;
      return ok({ ...summarize(issue), body: issue.body ?? "" });
    } catch (error) {
      return fail(error);
    }
  },
);

server.registerTool(
  "list-issue-comments",
  {
    description: "List the comments of an issue.",
    inputSchema: z.object({
      repo: repoArg,
      issue_number: z.number().int().min(1).describe("Issue number"),
      per_page: z.number().int().min(1).max(100).default(30).describe("Results per page"),
      page: z.number().int().min(1).default(1).describe("Page number"),
    }),
  },
  async ({ repo, issue_number, per_page, page }) => {
    try {
      const r = resolveRepo(repo);
      const data = (await github(r, `/repos/${r.owner}/${r.name}/issues/${issue_number}/comments`, {
        per_page,
        page,
      })) as Array<{ id: number; user: { login: string } | null; created_at: string; body: string; html_url: string }>;
      return ok(
        data.map((c) => ({
          id: c.id,
          author: c.user?.login ?? null,
          created_at: c.created_at,
          body: c.body,
          url: c.html_url,
        })),
      );
    } catch (error) {
      return fail(error);
    }
  },
);

server.registerTool(
  "search-issues",
  {
    description: "Search issues of the GitHub repository by text (pull requests are excluded).",
    inputSchema: z.object({
      repo: repoArg,
      query: z.string().describe("Search text, e.g. 'login bug label:bug'"),
      state: z.enum(["open", "closed", "all"]).default("all").describe("Issue state filter"),
      per_page: z.number().int().min(1).max(100).default(30).describe("Results per page"),
      page: z.number().int().min(1).default(1).describe("Page number"),
    }),
  },
  async ({ repo, query, state, per_page, page }) => {
    try {
      const r = resolveRepo(repo);
      const q = [query, `repo:${r.owner}/${r.name}`, "is:issue", state === "all" ? "" : `state:${state}`]
        .filter(Boolean)
        .join(" ");
      const data = (await github(r, "/search/issues", { q, per_page, page })) as {
        total_count: number;
        items: GitHubIssue[];
      };
      return ok({ total_count: data.total_count, items: data.items.map(summarize) });
    } catch (error) {
      return fail(error);
    }
  },
);

server.registerTool(
  "get-auth-status",
  {
    description:
      "Show the config file location, the default repository, which repositories have their own token, and whether a token is used for the given repository (never reveals tokens) plus its API rate limit.",
    inputSchema: z.object({ repo: repoArg }),
  },
  async ({ repo }) => {
    try {
      const config = loadConfig();
      const r = resolveRepo(repo);
      const rate = (await github(r, "/rate_limit")) as {
        resources: { core: { limit: number; remaining: number; reset: number } };
      };
      const core = rate.resources.core;
      return ok({
        config_file: CONFIG_FILE,
        default_repository: config.defaultRepository || process.env.GITHUB_REPOSITORY || null,
        repositories_with_own_token: Object.entries(config.repositories ?? {})
          .filter(([, v]) => v.token?.trim())
          .map(([k]) => k),
        checked_repository: r.key,
        token_used_for_repository: Boolean(getToken(r)),
        rate_limit: { limit: core.limit, remaining: core.remaining, resets_at: new Date(core.reset * 1000).toISOString() },
      });
    } catch (error) {
      return fail(error);
    }
  },
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("github-issues-mcp-server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
