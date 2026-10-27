import { isDeepStrictEqual } from "node:util";

export const repository = "j0shcd/risk-metric";
export const repositoryId = 739164541;
export const requiredJobs = ["dependency-security / scan", "test-and-benchmark-gate", "web-test-and-build"];
const bot = { login: "dependabot[bot]", id: 49699333 };

export function requireGuard(condition, reason) {
  if (!condition) throw new Error(reason);
}

function same(left, right, reason) {
  requireGuard(isDeepStrictEqual(left, right), reason);
}

export function isPatch(before, after) {
  const pattern = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
  const a = pattern.exec(before);
  const b = pattern.exec(after);
  return Boolean(a && b && a[1] === b[1] && a[2] === b[2] && BigInt(b[3]) > BigInt(a[3]));
}

function versionMap(before, after) {
  same(Object.keys(before).sort(), Object.keys(after).sort(), "Dependency names changed");
  for (const name of Object.keys(before)) {
    if (before[name] === after[name]) continue;
    const pattern = /^([~^]?)(\d+\.\d+\.\d+)$/;
    const a = pattern.exec(before[name]);
    const b = pattern.exec(after[name]);
    requireGuard(a && b && a[1] === b[1] && isPatch(a[2], b[2]), "Dependency range is not a patch upgrade");
  }
}

function manifest(before, after) {
  const a = structuredClone(before);
  const b = structuredClone(after);
  for (const field of ["dependencies", "devDependencies"]) {
    versionMap(a[field] ?? {}, b[field] ?? {});
    delete a[field];
    delete b[field];
  }
  same(a, b, "Manifest changed scripts, engines, or other non-dependency fields");
}

function npmChanges(files) {
  const lock = files["web/package-lock.json"];
  requireGuard(lock, "Missing npm lockfile change");
  const before = JSON.parse(lock.before);
  const after = JSON.parse(lock.after);
  requireGuard(before.lockfileVersion === 3 && after.lockfileVersion === 3, "Unsupported npm lockfile");
  const a = structuredClone(before);
  const b = structuredClone(after);
  delete a.packages;
  delete b.packages;
  same(a, b, "Lockfile header changed");
  same(Object.keys(before.packages).sort(), Object.keys(after.packages).sort(), "Package added or removed");
  manifest(before.packages[""], after.packages[""]);
  if (files["web/package.json"]) {
    const original = JSON.parse(files["web/package.json"].before);
    const updated = JSON.parse(files["web/package.json"].after);
    manifest(original, updated);
    for (const field of ["dependencies", "devDependencies"]) {
      same(original[field], before.packages[""][field], "Original manifest and lock disagree");
      same(updated[field], after.packages[""][field], "Updated manifest and lock disagree");
    }
  } else {
    same(before.packages[""], after.packages[""], "Lock root changed without its manifest");
  }
  const changes = [];
  for (const path of Object.keys(before.packages).filter(Boolean)) {
    const original = before.packages[path];
    const updated = after.packages[path];
    if (isDeepStrictEqual(original, updated)) continue;
    requireGuard(isPatch(original.version, updated.version), "A resolved npm package is not a patch upgrade");
    requireGuard(/^sha512-[A-Za-z0-9+/]+=*$/.test(updated.integrity), "Missing npm integrity");
    const expectedUrl = new URL(original.resolved);
    requireGuard(expectedUrl.origin === "https://registry.npmjs.org" && !expectedUrl.search && !expectedUrl.hash, "Unexpected npm registry");
    requireGuard(expectedUrl.pathname.endsWith(`-${original.version}.tgz`), "Unexpected npm artifact name");
    expectedUrl.pathname = expectedUrl.pathname.slice(0, -`${original.version}.tgz`.length) + `${updated.version}.tgz`;
    requireGuard(updated.resolved === expectedUrl.href, "npm artifact source changed");
    const oldMetadata = structuredClone(original);
    const newMetadata = structuredClone(updated);
    for (const field of ["dependencies", "optionalDependencies", "peerDependencies"]) {
      versionMap(oldMetadata[field] ?? {}, newMetadata[field] ?? {});
      delete oldMetadata[field];
      delete newMetadata[field];
    }
    for (const field of ["version", "resolved", "integrity"]) {
      delete oldMetadata[field];
      delete newMetadata[field];
    }
    same(oldMetadata, newMetadata, "npm package changed install behavior, engines, or other metadata");
    changes.push({ ecosystem: "npm", name: path.split("node_modules/").at(-1), before: original.version, after: updated.version });
  }
  return changes;
}

function pythonPins(text) {
  const pins = new Map();
  for (const raw of text.replace(/\\\r?\n/g, " ").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const match = /^([\w.-]+)==(\d+(?:\.\d+){1,2})((?:\s+--hash=sha256:[a-f0-9]{64})+)$/.exec(line);
    requireGuard(match, "Unpinned, unhashed, or unsupported Python requirement");
    const name = match[1].toLowerCase().replace(/[-_.]+/g, "-");
    requireGuard(!pins.has(name), "Duplicate Python dependency");
    pins.set(name, { version: match[2], hashes: match[3].trim().split(/\s+/).sort() });
  }
  requireGuard(pins.size > 0, "Empty Python inventory");
  return pins;
}

function pythonChanges(file) {
  const before = pythonPins(file.before);
  const after = pythonPins(file.after);
  same([...before.keys()].sort(), [...after.keys()].sort(), "Python package added or removed");
  const changes = [];
  for (const [name, original] of before) {
    const updated = after.get(name);
    if (original.version === updated.version) {
      same(original, updated, "Python artifact hashes changed without a version change");
    } else {
      requireGuard(isPatch(original.version, updated.version), "Python update is not a patch upgrade");
      changes.push({ ecosystem: "PyPI", name, before: original.version, after: updated.version });
    }
  }
  return changes;
}

// One policy owns all allowed file/version changes. No PR code is executed.
export function dependencyChanges(files) {
  const names = Object.keys(files).sort();
  const npm = names.every(name => ["web/package.json", "web/package-lock.json"].includes(name));
  const python = names.length === 1 && names[0] === "requirements.txt";
  requireGuard(names.length > 0 && (npm || python), "Files outside one dependency inventory changed");
  const changes = npm ? npmChanges(files) : pythonChanges(files["requirements.txt"]);
  requireGuard(changes.length > 0 && changes.length <= 12, "Expected 1–12 resolved patch upgrades");
  return changes;
}

export function validatePullRequest(pr, run, commits) {
  requireGuard(pr.state === "open" && !pr.draft && !pr.merged, "PR is not open and ready");
  requireGuard(pr.user?.login === bot.login && pr.user?.id === bot.id && pr.user?.type === "Bot", "PR author is not verified Dependabot");
  requireGuard(pr.base?.repo?.id === repositoryId && pr.head?.repo?.id === repositoryId && pr.base.ref === "main", "Wrong repository or base branch");
  requireGuard(pr.head.sha === run.head_sha, "CI tested a different PR head");
  requireGuard(pr.changed_files >= 1 && pr.changed_files <= 2, "PR changed too many files");
  requireGuard(commits.length > 0 && commits.length === pr.commits && commits.length <= 20, "Incomplete or excessive commit inventory");
  for (const commit of commits) {
    requireGuard(commit.author?.id === bot.id && commit.author?.login === bot.login, "A commit was not authored by Dependabot");
    requireGuard((commit.committer?.id === bot.id && commit.committer.login === bot.login) || (commit.committer?.id === 19864447 && commit.committer.login === "web-flow"), "Unexpected commit signer");
    requireGuard(commit.commit?.verification?.verified === true && commit.commit.verification.reason === "valid", "A commit signature is unverified");
  }
  requireGuard(commits.at(-1).sha === pr.head.sha, "Commit inventory does not end at PR head");
  const relation = run.pull_requests?.find(item => item.number === pr.number);
  requireGuard(relation?.head?.sha === pr.head.sha && relation.base?.sha === pr.base.sha, "CI did not test the current PR/base pair");
}

export function validateRun(run, event, jobs) {
  requireGuard(run.name === "CI Quality And Benchmark" && run.path === ".github/workflows/ci-quality-and-benchmark.yml", "Wrong CI workflow");
  requireGuard(run.repository?.id === repositoryId && run.head_repository?.id === repositoryId, "CI belongs to another repository");
  requireGuard(run.event === "pull_request" && run.status === "completed" && run.conclusion === "success", "CI has not succeeded");
  requireGuard(run.id === event.id && run.run_attempt === event.run_attempt && run.head_sha === event.head_sha, "Stale CI event");
  same(jobs.map(job => job.name).sort(), [...requiredJobs].sort(), "Missing or unexpected CI jobs");
  requireGuard(jobs.every(job => job.status === "completed" && job.conclusion === "success" && job.run_attempt === run.run_attempt), "A CI job failed, skipped, or belongs to an older attempt");
}

export function validateProtection(repo, pr) {
  requireGuard(repo?.autoMergeAllowed === true, "Repository Allow auto-merge is disabled");
  const branch = repo.defaultBranchRef;
  requireGuard(branch?.name === "main" && branch.target?.oid === pr.base.sha, "Base branch advanced since CI");
  const rule = branch.branchProtectionRule;
  requireGuard(rule?.requiresStatusChecks === true && rule.requiresStrictStatusChecks === true && rule.isAdminEnforced === true, "Strict, enforced branch protection is required");
  requireGuard(requiredJobs.every(job => rule.requiredStatusCheckContexts?.includes(job)), "Required security/backend/frontend checks are not protected");
}

export async function securityEvidence(changes, osv) {
  const queries = changes.flatMap(change => [change.before, change.after].map(version => ({ package: { ecosystem: change.ecosystem, name: change.name }, version })));
  const response = await osv("querybatch", { queries });
  requireGuard(response && Object.getPrototypeOf(response) === Object.prototype && Array.isArray(response.results) && response.results.length === queries.length, "Incomplete advisory response");
  const fixed = new Set();
  for (let index = 0; index < changes.length; index++) {
    const oldResult = response.results[index * 2];
    const newResult = response.results[index * 2 + 1];
    for (const item of [oldResult, newResult]) {
      requireGuard(item && Object.getPrototypeOf(item) === Object.prototype, "Invalid advisory result object");
      requireGuard(Object.keys(item).every(key => ["vulns", "next_page_token"].includes(key)), "Advisory lookup returned an error or unknown result");
      requireGuard(item.next_page_token === undefined || item.next_page_token === "", "Incomplete advisory pages");
      requireGuard(item.vulns === undefined || Array.isArray(item.vulns), "Invalid advisory result");
    }
    requireGuard(!(newResult.vulns?.length), "A proposed version still has known vulnerabilities");
    requireGuard((oldResult.vulns?.length ?? 0) <= 40, "Advisory inventory exceeds automatic-review budget");
    for (const entry of oldResult.vulns ?? []) {
      requireGuard(typeof entry.id === "string" && /^(GHSA-[a-z0-9-]+|PYSEC-\d+-\d+|CVE-\d{4}-\d+|MAL-\d+-\d+)$/.test(entry.id), "Invalid advisory identifier");
      requireGuard(!entry.id.startsWith("MAL-"), "Known malware needs manual incident response");
      if (fixed.has(entry.id)) continue;
      requireGuard(fixed.size < 40, "Advisory lookup budget exceeded");
      const record = await osv(`vulns/${entry.id}`);
      requireGuard(record.id === entry.id && !record.withdrawn, "Invalid or withdrawn advisory");
      requireGuard(!/^malware in /i.test(record.summary ?? "") && !record.database_specific?.cwe_ids?.includes("CWE-506"), "Malware requires manual incident response");
      requireGuard(record.affected?.some(item => item.package?.ecosystem === changes[index].ecosystem && item.package.name === changes[index].name), "Advisory refers to a different package");
      requireGuard((record.aliases ?? []).some(id => /^CVE-\d{4}-\d+$/.test(id)) || record.database_specific?.github_reviewed === true, "Advisory is not a reviewed vulnerability");
      fixed.add(entry.id);
    }
  }
  requireGuard(fixed.size > 0, "No known security vulnerability is fixed by this PR");
  return [...fixed].sort();
}
