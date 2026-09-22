# G10 frontend dependency-audit triage

**Triage date:** 2026-08-10

**Release tree:** `2b10135b212ded8fef61ae6a5f6dcb5ad0cbc86c`

## Result

The pre-public dependency triage is complete. No blanket `npm audit fix` was run and
the lockfile was not changed.

```text
npm audit --omit=dev --json
```

The current registry report contains 15 package-level vulnerability records:

- 10 high;
- 3 moderate;
- 2 low;
- 0 critical.

All report a fix path. This count is higher than the Phase 0 baseline because the
registry advisory set changed during the project; it is a dated observation, not a
stable project metric.

## Runtime-versus-tooling classification

The deployed frontend is a static Vite build served by CloudFront/S3. It does not
deploy Node.js, the Vite development server, Hono, Express, the shadcn CLI, PostCSS,
Babel, YAML parsing or MCP server code. The built `dist/` inventory contains only
static HTML, JavaScript, CSS, fonts and the licensed fixture assets. A bounded bundle
scan found no Hono server, `serveStatic`, body-parser, express-rate-limit or PostCSS
markers.

Those build/CLI dependency advisories therefore do not expose the affected server or
filesystem APIs in the deployed browser application. They remain supply-chain and
developer-workstation upgrade debt rather than ignored findings.

`react-router-dom`/`react-router` is the one reported family that is included in the
browser runtime. The high-severity reports primarily concern framework server,
RSC/SSR, data-action, single-fetch and manifest-endpoint features that this static SPA
does not use. The application also does not construct external navigation targets
from user input: route targets are fixed application paths or API-validated project
identifiers. A crafted browser URL can still affect its own client-side route
processing, so the dependency is not declared risk-free.

## Decision

No currently deployed server-side vulnerable surface was identified, no critical
advisory was reported and safe upgrades are available. The bounded v0.1 evidence gate
therefore remains accepted with an explicit residual:

- update React Router and the build/CLI dependency chain in a reviewed follow-up;
- rerun all 194 frontend tests, lint, TypeScript and production/cloud/demo builds;
- redeploy and repeat browser smoke before describing the audit as clean;
- keep `npm audit` nonzero visible in the release limitations until that happens.

This triage is not a security certification. It records why the current static
deployment was not subjected to an indiscriminate dependency rewrite during the
release-evidence gate.
