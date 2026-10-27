import test from "node:test";
import assert from "node:assert/strict";
import { guardedMerge } from "../dependabot-auto-merge.mjs";
import { dependencyChanges, isPatch, securityEvidence } from "./dependabot-policy.mjs";

const base = "a".repeat(40);
const head = "b".repeat(40);
const repoId = 739164541;
const bot = Object.freeze({ login: "dependabot[bot]", id: 49699333, type: "Bot" });
const hash = letter => `--hash=sha256:${letter.repeat(64)}`;

function fixture() {
  const relation = { number: 7, head: { sha: head }, base: { sha: base } };
  const run = {
    id: 100, run_attempt: 1, name: "CI Quality And Benchmark",
    path: ".github/workflows/ci-quality-and-benchmark.yml", head_sha: head,
    repository: { id: repoId }, head_repository: { id: repoId },
    event: "pull_request", status: "completed", conclusion: "success", pull_requests: [relation],
  };
  const pr = {
    number: 7, node_id: "PR_fixture", user: { ...bot }, state: "open", draft: false, merged: false,
    head: { sha: head, repo: { id: repoId } },
    base: { sha: base, ref: "main", repo: { id: repoId } }, changed_files: 1, commits: 1,
  };
  const commits = [{ sha: head, author: { ...bot }, committer: { id: 19864447, login: "web-flow" }, commit: { verification: { verified: true, reason: "valid" } } }];
  // Expected check names are deliberately independent of the implementation.
  const names = ["dependency-security / scan", "test-and-benchmark-gate", "web-test-and-build"];
  const jobs = { total_count: 3, jobs: names.map(name => ({ name, conclusion: "success", status: "completed", run_attempt: 1 })) };
  const protection = { data: { repository: {
    autoMergeAllowed: true, defaultBranchRef: { name: "main", target: { oid: base }, branchProtectionRule: {
      requiresStatusChecks: true, requiresStrictStatusChecks: true, isAdminEnforced: true,
      requiredStatusCheckContexts: names,
    } },
  } } };
  const contents = {
    before: `requests==2.32.3 \\\n    ${hash("a")}\n`,
    after: `requests==2.32.4 \\\n    ${hash("b")}\n`,
  };
  const state = { run, pr, commits, jobs, protection, contents,
    files: [{ filename: "requirements.txt", status: "modified" }], mutations: [], reads: 0 };
  const github = async (path, body) => {
    if (body?.query?.includes("mutation")) {
      state.mutations.push(structuredClone(body));
      return { data: { mergePullRequest: { pullRequest: { merged: true, mergeCommit: { oid: "c".repeat(40) } } } } };
    }
    if (path === "/graphql") return structuredClone(state.protection);
    if (path === "/actions/runs/100") return structuredClone(state.run);
    if (path === "/pulls/7") {
      state.reads++;
      const value = structuredClone(state.pr);
      if (state.changeHeadDuringReview && state.reads > 1) value.head.sha = "d".repeat(40);
      return value;
    }
    if (path === "/pulls/7/commits?per_page=100") return structuredClone(state.commits);
    if (path === "/actions/runs/100/jobs?filter=latest&per_page=100") return structuredClone(state.jobs);
    if (path === "/pulls/7/files?per_page=100") return structuredClone(state.files);
    if (path.startsWith("/contents/")) {
      const text = path.endsWith(`ref=${base}`) ? state.contents.before : state.contents.after;
      return { type: "file", encoding: "base64", size: Buffer.byteLength(text), content: Buffer.from(text).toString("base64") };
    }
    throw new Error(`Unexpected test request: ${path}`);
  };
  const osv = async (path) => {
    if (path === "querybatch") return { results: [{ vulns: [{ id: "GHSA-9hjg-9r4m-mvj7" }] }, {}] };
    return { id: "GHSA-9hjg-9r4m-mvj7", aliases: ["CVE-2024-47081"], affected: [{ package: { ecosystem: "PyPI", name: "requests" } }] };
  };
  return { state, options: { event: { repository: { id: repoId }, workflow_run: structuredClone(run) }, github, osv } };
}

test("a signed, advisory-backed patch merges once with an atomic head guard", async () => {
  const { state, options } = fixture();
  const result = await guardedMerge(options);
  assert.equal(result.mergeCommit, "c".repeat(40));
  assert.equal(state.mutations.length, 1);
  assert.deepEqual(state.mutations[0].variables.input, { pullRequestId: "PR_fixture", expectedHeadOid: head, mergeMethod: "SQUASH" });
});

test("dry run exercises every read but never merges", async () => {
  const { state, options } = fixture();
  const result = await guardedMerge({ ...options, dryRun: true });
  assert.equal(result.advisories.length, 1);
  assert.equal(state.reads, 2);
  assert.deepEqual(state.mutations, []);
});

const unsafeStates = {
  "human PR": s => { s.pr.user = { ...bot, login: "someone", id: 1 }; },
  "spoofed bot name": s => { s.pr.user = { ...bot, id: 1 }; },
  "fork PR": s => { s.pr.head.repo.id = 1; },
  "draft": s => { s.pr.draft = true; },
  "closed PR": s => { s.pr.state = "closed"; },
  "another base branch": s => { s.pr.base.ref = "other"; },
  "unverified commit": s => { s.commits[0].commit.verification.verified = false; },
  "human commit": s => { s.commits[0].author.id = 1; },
  "unexpected signer": s => { s.commits[0].committer.id = 41898282; },
  "incomplete commit inventory": s => { s.pr.commits = 2; },
  "stale head": s => { s.pr.head.sha = "c".repeat(40); },
  "stale base": s => { s.run.pull_requests[0].base.sha = "c".repeat(40); },
  "stale CI attempt": s => { s.run.run_attempt = 2; },
  "failed CI": s => { s.run.conclusion = "failure"; },
  "wrong workflow": s => { s.run.path = ".github/workflows/other.yml"; },
  "missing security job": s => { s.jobs.jobs.shift(); s.jobs.total_count--; },
  "skipped frontend job": s => { s.jobs.jobs[2].conclusion = "skipped"; },
  "truncated job inventory": s => { s.jobs.total_count++; },
  "workflow file change": s => { s.files[0].filename = ".github/workflows/ci-quality-and-benchmark.yml"; },
  "renamed file": s => { s.files[0].previous_filename = "elsewhere.txt"; },
  "Python source bounds change": s => { s.files[0].filename = "requirements.in"; },
  "minor update": s => { s.contents.after = `requests==2.33.0 ${hash("b")}\n`; },
  "major update": s => { s.contents.after = `requests==3.0.0 ${hash("b")}\n`; },
  "new package": s => { s.contents.after += `other==1.0.0 ${hash("b")}\n`; },
  "changed hash with same version": s => { s.contents.after = `requests==2.32.3 ${hash("b")}\n`; },
  "unhashed pin": s => { s.contents.after = "requests==2.32.4\n"; },
  "remote Python include": s => { s.contents.after += "-r https://example.com/requirements.txt\n"; },
  "auto merge disabled": s => { s.protection.data.repository.autoMergeAllowed = false; },
  "unprotected branch": s => { s.protection.data.repository.defaultBranchRef.branchProtectionRule = null; },
  "loose branch checks": s => { s.protection.data.repository.defaultBranchRef.branchProtectionRule.requiresStrictStatusChecks = false; },
  "admin bypass": s => { s.protection.data.repository.defaultBranchRef.branchProtectionRule.isAdminEnforced = false; },
  "required check removed": s => { s.protection.data.repository.defaultBranchRef.branchProtectionRule.requiredStatusCheckContexts.pop(); },
  "base advanced": s => { s.protection.data.repository.defaultBranchRef.target.oid = "c".repeat(40); },
  "head changed after validation": s => { s.changeHeadDuringReview = true; },
  "protection read denied": s => { s.protection = { errors: [{ message: "Forbidden" }] }; },
};
for (const [name, change] of Object.entries(unsafeStates)) {
  test(`merge withheld: ${name}`, async () => {
    const witness = fixture();
    await guardedMerge({ ...witness.options, dryRun: true });
    const { state, options } = fixture();
    change(state);
    await assert.rejects(guardedMerge(options));
    assert.deepEqual(state.mutations, []);
  });
}

for (const [name, response] of Object.entries({
  "ordinary version bump": { results: [{}, {}] },
  "malware": { results: [{ vulns: [{ id: "MAL-2026-17650" }] }, {}] },
  "still vulnerable": { results: [{ vulns: [{ id: "GHSA-9hjg-9r4m-mvj7" }] }, { vulns: [{ id: "GHSA-9hjg-9r4m-mvj7" }] }] },
  "incomplete OSV response": { results: [{}] },
  "paginated OSV response": { results: [{ next_page_token: "more" }, {}] },
  "malformed OSV response": { results: [{ vulns: {} }, {}] },
  "array OSV result": { results: [{ vulns: [{ id: "GHSA-9hjg-9r4m-mvj7" }] }, []] },
  "string OSV result": { results: [{ vulns: [{ id: "GHSA-9hjg-9r4m-mvj7" }] }, "unavailable"] },
  "OSV lookup error": { results: [{ vulns: [{ id: "GHSA-9hjg-9r4m-mvj7" }] }, { error: "lookup failed" }] },
  "unexpected OSV field": { results: [{ vulns: [{ id: "GHSA-9hjg-9r4m-mvj7" }] }, { code: 5 }] },
})) {
  test(`merge withheld: ${name}`, async () => {
    const witness = fixture();
    await guardedMerge({ ...witness.options, dryRun: true });
    const { state, options } = fixture();
    await assert.rejects(guardedMerge({ ...options, osv: (path, body) => path === "querybatch" ? response : options.osv(path, body) }));
    assert.deepEqual(state.mutations, []);
  });
}

test("service errors never permit a merge", async () => {
  for (const service of ["github", "osv"]) {
    const { state, options } = fixture();
    await assert.rejects(guardedMerge({ ...options, [service]: async () => { throw new Error("unavailable"); } }));
    assert.deepEqual(state.mutations, []);
  }
});

function npmFiles(version = "1.2.4") {
  const lock = v => ({ name: "web", version: "1.0.0", lockfileVersion: 3, packages: {
    "": { name: "web", version: "1.0.0", dependencies: { example: "^1.2.3" } },
    "node_modules/example": { version: v, resolved: `https://registry.npmjs.org/example/-/example-${v}.tgz`, integrity: "sha512-YWJjZA==", dev: false },
  } });
  return { "web/package-lock.json": { before: JSON.stringify(lock("1.2.3")), after: JSON.stringify(lock(version)) } };
}

test("a transitive npm patch is eligible for advisory verification", () => {
  assert.deepEqual(dependencyChanges(npmFiles()), [{ ecosystem: "npm", name: "example", before: "1.2.3", after: "1.2.4" }]);
});

for (const [name, change] of Object.entries({
  "new dependency": lock => { lock.packages["node_modules/extra"] = { version: "1.0.0" }; },
  "install script": lock => { lock.packages["node_modules/example"].hasInstallScript = true; },
  "registry change": lock => { lock.packages["node_modules/example"].resolved = "https://evil.example/payload.tgz"; },
  "missing integrity": lock => { delete lock.packages["node_modules/example"].integrity; },
  "engine change": lock => { lock.packages["node_modules/example"].engines = { node: ">=26" }; },
})) {
  test(`npm automatic policy rejects ${name}`, () => {
    const files = npmFiles();
    const lock = JSON.parse(files["web/package-lock.json"].after);
    change(lock);
    files["web/package-lock.json"].after = JSON.stringify(lock);
    assert.throws(() => dependencyChanges(files));
  });
}

test("minor, major, prerelease, downgrade and date-only updates stay manual", () => {
  for (const [a, b] of [["1.2.3", "1.3.0"], ["1.2.3", "2.0.0"], ["1.2.3", "1.2.4-rc.1"], ["1.2.3", "1.2.2"], ["2026.5", "2026.6"]]) assert.equal(isPatch(a, b), false);
  assert.equal(isPatch("1.2.3", "1.2.4"), true);
});

test("unreviewed or mismatched advisory metadata does not establish a security fix", async () => {
  for (const record of [
    { id: "GHSA-9hjg-9r4m-mvj7", withdrawn: "2026-10-01" },
    { id: "GHSA-9hjg-9r4m-mvj7", affected: [] },
    { id: "GHSA-9hjg-9r4m-mvj7", affected: [{ package: { ecosystem: "PyPI", name: "requests" } }] },
  ]) {
    const { state, options } = fixture();
    const original = options.osv;
    await assert.rejects(guardedMerge({ ...options, osv: (path, body) => path === "querybatch" ? original(path, body) : record }));
    assert.deepEqual(state.mutations, []);
  }
});
