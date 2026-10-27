import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import {
  dependencyChanges, repository, repositoryId, requireGuard,
  securityEvidence, validateProtection, validatePullRequest, validateRun,
} from "./lib/dependabot-policy.mjs";

const protectionQuery = `query {
  repository(owner: "j0shcd", name: "risk-metric") {
    autoMergeAllowed
    defaultBranchRef {
      name
      target { ... on Commit { oid } }
      branchProtectionRule {
        requiresStatusChecks requiresStrictStatusChecks isAdminEnforced
        requiredStatusCheckContexts
      }
    }
  }
}`;

export async function guardedMerge({ event, github, osv, dryRun = false }) {
  requireGuard(event.repository?.id === repositoryId, "Unexpected event repository");
  const original = event.workflow_run;
  requireGuard(Number.isSafeInteger(original?.id) && original.id > 0, "Missing workflow run");
  const run = await github(`/actions/runs/${original.id}`);
  requireGuard(run.pull_requests?.length === 1, "CI must identify exactly one PR");
  const number = run.pull_requests[0].number;
  requireGuard(Number.isSafeInteger(number) && number > 0, "Invalid PR number");
  const pr = await github(`/pulls/${number}`);
  const commits = await github(`/pulls/${number}/commits?per_page=100`);
  validatePullRequest(pr, run, commits);
  const jobs = await github(`/actions/runs/${run.id}/jobs?filter=latest&per_page=100`);
  requireGuard(jobs.total_count === jobs.jobs?.length, "Incomplete CI job inventory");
  validateRun(run, original, jobs.jobs);
  const files = await github(`/pulls/${number}/files?per_page=100`);
  requireGuard(files.length === pr.changed_files, "Incomplete file inventory");
  const contents = {};
  const allowed = new Set(["web/package.json", "web/package-lock.json", "requirements.txt"]);
  for (const file of files) {
    requireGuard(file.status === "modified" && !file.previous_filename && allowed.has(file.filename), "PR changes a file outside dependency policy");
    requireGuard(!Object.hasOwn(contents, file.filename), "Duplicate file entry");
    const versions = {};
    for (const [label, ref] of [["before", pr.base.sha], ["after", pr.head.sha]]) {
      requireGuard(/^[a-f0-9]{40}$/.test(ref), "Invalid commit identity");
      const blob = await github(`/contents/${file.filename}?ref=${ref}`);
      requireGuard(blob.type === "file" && blob.encoding === "base64" && blob.size > 0 && blob.size <= 1_048_576, "Missing or oversized dependency file");
      const bytes = Buffer.from(blob.content, "base64");
      requireGuard(bytes.length === blob.size, "Dependency file response was truncated");
      versions[label] = bytes.toString("utf8");
    }
    contents[file.filename] = versions;
  }
  const changes = dependencyChanges(contents);
  const advisories = await securityEvidence(changes, osv);

  // Check native protections and refresh mutable state immediately before the
  // sole write. GitHub then enforces protections and the exact expected head.
  const protection = await github("/graphql", { query: protectionQuery });
  requireGuard(!protection.errors, "Cannot verify GitHub branch protection");
  validateProtection(protection.data?.repository, pr);
  const current = await github(`/pulls/${number}`);
  requireGuard(current.head?.sha === pr.head.sha && current.base?.sha === pr.base.sha, "PR changed during validation");
  validatePullRequest(current, run, commits);
  const latestRun = await github(`/actions/runs/${run.id}`);
  requireGuard(latestRun.run_attempt === run.run_attempt && latestRun.conclusion === "success" && latestRun.status === "completed", "CI was rerun or invalidated");
  const result = { number, head: pr.head.sha, base: pr.base.sha, changes, advisories, dryRun };
  if (dryRun) return result;
  const merged = await github("/graphql", {
    query: `mutation($input: MergePullRequestInput!) {
      mergePullRequest(input: $input) { pullRequest { merged mergeCommit { oid } } }
    }`,
    variables: { input: { pullRequestId: current.node_id, expectedHeadOid: pr.head.sha, mergeMethod: "SQUASH" } },
  });
  requireGuard(!merged.errors && merged.data?.mergePullRequest?.pullRequest?.merged === true, "GitHub refused the protected merge; manual review required");
  return { ...result, mergeCommit: merged.data.mergePullRequest.pullRequest.mergeCommit.oid };
}

async function request(url, body, token) {
  const response = await fetch(url, {
    method: body ? "POST" : "GET", redirect: "error",
    signal: AbortSignal.timeout(20_000),
    headers: {
      Accept: "application/json", "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}`, "X-GitHub-Api-Version": "2022-11-28" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  requireGuard(response.ok, `Security guard request failed: HTTP ${response.status}`);
  return response.json();
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  try {
    requireGuard(process.env.GITHUB_EVENT_NAME === "workflow_run", "Only a completed CI event can start the guard");
    requireGuard(process.env.GITHUB_REPOSITORY === repository && process.env.GH_TOKEN, "Missing repository or GitHub token");
    requireGuard(process.argv.slice(2).every(arg => arg === "--dry-run"), "Unknown guard argument");
    const event = JSON.parse(await readFile(process.env.GITHUB_EVENT_PATH, "utf8"));
    const result = await guardedMerge({
      event, dryRun: process.argv.includes("--dry-run"),
      github: (path, body) => request(path === "/graphql" ? "https://api.github.com/graphql" : `https://api.github.com/repos/${repository}${path}`, body, process.env.GH_TOKEN),
      osv: (path, body) => request(`https://api.osv.dev/v1/${path}`, body),
    });
    console.log(JSON.stringify(result));
  } catch (error) {
    console.error(`Automatic merge withheld: ${error.message}`);
    process.exitCode = 1;
  }
}
