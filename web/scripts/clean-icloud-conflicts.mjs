#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const webRoot = path.resolve(path.dirname(__filename), "..");
const apply = process.argv.includes("--apply");
const conflictPattern = /^(.*) ([0-9]+)(\.[^/.]+)?$/;
const quarantineRoot = path.join(webRoot, ".icloud-conflicts.nosync");
const quarantineRun = path.join(quarantineRoot, new Date().toISOString().replace(/[:.]/g, "-"));

const ignoredDirs = new Set([
  ".git",
  ".icloud-conflicts.nosync",
  "coverage",
  "node_modules",
  "node_modules.nosync",
]);

let identicalCount = 0;
let emptyDirCount = 0;
let quarantinedCount = 0;
let unresolvedCount = 0;

function hashFile(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function typeOf(stats) {
  if (stats.isSymbolicLink()) return "symlink";
  if (stats.isDirectory()) return "directory";
  if (stats.isFile()) return "file";
  return "other";
}

function isEmptyDirectory(dirPath) {
  return fs.lstatSync(dirPath).isDirectory() && fs.readdirSync(dirPath).length === 0;
}

function removePath(targetPath) {
  if (!apply) return;
  fs.rmSync(targetPath, { force: true, recursive: true });
}

function quarantinePath(targetPath) {
  quarantinedCount += 1;

  if (!apply) {
    console.log(`[clean-icloud] would quarantine ${path.relative(webRoot, targetPath)}`);
    return;
  }

  const relative = path.relative(webRoot, targetPath);
  const destination = path.join(quarantineRun, relative);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.renameSync(targetPath, destination);
  console.log(`[clean-icloud] quarantined ${relative} -> ${path.relative(webRoot, destination)}`);
}

function cleanDuplicate(entryPath, canonicalPath, entryStats, canonicalStats) {
  const relative = path.relative(webRoot, entryPath);

  if (!canonicalStats) {
    unresolvedCount += 1;
    console.warn(`[clean-icloud] no canonical file for ${relative}`);
    return;
  }

  if (entryStats.isSymbolicLink() && canonicalStats.isSymbolicLink()) {
    if (fs.readlinkSync(entryPath) === fs.readlinkSync(canonicalPath)) {
      identicalCount += 1;
      removePath(entryPath);
      console.log(`[clean-icloud] ${apply ? "removed" : "would remove"} duplicate symlink ${relative}`);
    } else {
      quarantinePath(entryPath);
    }
    return;
  }

  if (entryStats.isFile() && canonicalStats.isFile()) {
    if (hashFile(entryPath) === hashFile(canonicalPath)) {
      identicalCount += 1;
      removePath(entryPath);
      console.log(`[clean-icloud] ${apply ? "removed" : "would remove"} duplicate file ${relative}`);
    } else {
      quarantinePath(entryPath);
    }
    return;
  }

  if (entryStats.isDirectory() && isEmptyDirectory(entryPath)) {
    emptyDirCount += 1;
    removePath(entryPath);
    console.log(`[clean-icloud] ${apply ? "removed" : "would remove"} empty duplicate directory ${relative}`);
    return;
  }

  if (entryStats.isDirectory() && canonicalStats.isDirectory()) {
    quarantinePath(entryPath);
    return;
  }

  unresolvedCount += 1;
  console.warn(
    `[clean-icloud] unresolved ${relative}: duplicate is ${typeOf(entryStats)}, canonical is ${typeOf(
      canonicalStats,
    )}`,
  );
}

function walk(dirPath) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });

  for (const entry of entries) {
    const entryPath = path.join(dirPath, entry.name);
    const stats = fs.lstatSync(entryPath);
    const match = entry.name.match(conflictPattern);

    if (match) {
      const canonicalName = `${match[1]}${match[3] ?? ""}`;
      const canonicalPath = path.join(dirPath, canonicalName);
      cleanDuplicate(
        entryPath,
        canonicalPath,
        stats,
        fs.existsSync(canonicalPath) ? fs.lstatSync(canonicalPath) : null,
      );
      continue;
    }

    if (stats.isDirectory() && !stats.isSymbolicLink() && !ignoredDirs.has(entry.name)) {
      walk(entryPath);
    }
  }
}

walk(webRoot);

const summary = [
  `${identicalCount} duplicate${identicalCount === 1 ? "" : "s"}`,
  `${emptyDirCount} empty duplicate dir${emptyDirCount === 1 ? "" : "s"}`,
  `${quarantinedCount} quarantined`,
  `${unresolvedCount} unresolved`,
].join(", ");

console.log(`[clean-icloud] ${apply ? "cleaned" : "dry run"}: ${summary}`);

if (unresolvedCount > 0) {
  process.exitCode = 1;
}
