// @vitest-environment node
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Cloudflare Pages applies public/_headers to every static response. Parse it
// the way Pages does (a path line, then indented "Name: value" lines) so an edit
// that drops a protection fails here instead of shipping silently.
function parseHeaders(text) {
  const rules = {};
  let current = null;
  for (const line of text.split("\n")) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    if (!/^\s/.test(line)) {
      current = line.trim();
      rules[current] = {};
    } else if (current) {
      const idx = line.indexOf(":");
      rules[current][line.slice(0, idx).trim().toLowerCase()] = line.slice(idx + 1).trim();
    }
  }
  return rules;
}

const rules = parseHeaders(readFileSync(path.resolve(import.meta.dirname, "../public/_headers"), "utf8"));

describe("public/_headers", () => {
  it("applies a strict content security policy to every page", () => {
    const csp = rules["/*"]["content-security-policy"];
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).not.toMatch(/https?:\/\//);
    expect(csp).not.toMatch(/script-src[^;]*unsafe/);
  });

  it("sets the baseline hardening headers site-wide", () => {
    for (const name of ["x-frame-options", "x-content-type-options", "referrer-policy", "permissions-policy", "strict-transport-security"]) {
      expect(rules["/*"][name], name).toBeTruthy();
    }
  });

  it("keeps the public JSON readable from any site and cached briefly", () => {
    expect(rules["/api/*"]["access-control-allow-origin"]).toBe("*");
    expect(rules["/api/*"]["cache-control"]).toBe("public, max-age=3600");
  });

  it("caches only fingerprinted assets and fonts forever", () => {
    expect(rules["/assets/*"]["cache-control"]).toContain("immutable");
    expect(rules["/fonts/*"]["cache-control"]).toContain("immutable");
    expect(rules["/*"]["cache-control"]).toBeUndefined();
  });
});
