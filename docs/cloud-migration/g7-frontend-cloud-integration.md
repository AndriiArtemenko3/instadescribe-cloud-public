# G7 — Frontend cloud integration (G7.3 correction evidence)

Date: 2026-08-07. Implementation commit: `8f52be7`. Accepted history through
`dfadacd` remains unamended. Scope is FABLE5 G6.3, G7, G7.1, G7.2, and the
bounded G7.3 correctness/evidence correction; G8 has not started.

All cloud-core execution reported here used local PostgreSQL and LocalStack.
Nothing was pushed, merged, tagged, released, deployed, provisioned, sent to
public `origin`, or exercised against real AWS.

## Corrected product contracts

### Newest scene intent is authoritative

Draft-backed reconstruction is now local session draft → acknowledged server
override → generated pipeline value for both description text and `active`.
One editor-owned `CloudSceneSaveCoordinator` serializes PATCHes independently
per `(jobId, sceneKey)`, so unrelated scenes remain concurrent while a newer
same-scene write can never reach the server before its predecessor and then be
overwritten by it.

The coordinator persists draft-backed values at enqueue, lets a failed older
write release the lane, compare-clears only the values acknowledged by their
own success, and leaves a failed newest value retryable. A successful PATCH is
committed into an editor acknowledgement fence before its draft is cleared.
An overrides GET that captured server A before PATCH B therefore merges the
acknowledged B when it resolves. Disposing an editor while a PATCH is pending
prevents that old instance from clearing the remount draft or mutating its
cache. Only the latest request may display the three-second “Changes applied”
state. Error copy is sanitized and distinguishes draft-backed fields from
settings that are not locally retained.

When the final draft field is cleared, its `:edits` key is removed rather than
persisting `{"scenes":{}}`. Settings counts only actual typed scene edits and
ignores malformed or stale empty keys.

### Reconciliation is fenced by exact access session and local mutation

Portfolio session identity is opaque, referential, contains no token bytes,
and changes on token set/restore/clear. Jobs-list requests are coalesced only
inside that exact identity. A response applies only if authentication, session
identity, and the same-session project-mutation fence still match. Thus:

- logout invalidates old responses before any Zustand/sessionStorage write;
- a replacement token starts an independent request while the old request is
  unresolved;
- failed or stale requests preserve the intended current-session view;
- a slow AWAITING snapshot cannot hide or regress a project after same-job
  completion succeeds.

The token remains only in the already-approved module memory/sessionStorage
mechanism and protected request header. It is not added to Zustand, query keys,
URLs, logs, or evidence fixtures.

### Never-uploaded and completion-pending AWAITING jobs are distinct

The job summary now requires `sourceUploaded: boolean`, independent of lifecycle
state. Upload completion verifies the exact S3 object identity, then commits the
existing ETag/version/optional-checksum/verification-time marker while the job
is still slot-free `AWAITING_UPLOAD`. Only the subsequent conditional transition
tries to acquire the one-compute-active slot. Capacity conflict therefore keeps
the verified source marker and same job without falsely claiming the slot.

A partial verification tuple, including a checksum-only row, is rejected rather
than completed from later evidence. The first-writer update is conditional on
the whole tuple being empty. Marker persistence outages roll back best-effort,
log only a stable category, and return sanitized `persistence_unavailable`.

The frontend treats AWAITING jobs as follows:

- no server marker and no same-tab S3-success evidence: hidden abandoned
  reservation;
- server `sourceUploaded=true`: visible `confirmation_pending` recovery card;
- same valid tab observed a successful S3 POST but completion has no response
  yet: the ordinary IDs plus `completionPending` survive session rehydration
  and keep the same recovery card visible;
- logout clears client-only evidence; a later session reconstructs only what
  the server marker proves.

The mounted recovery action calls only `upload-complete` for the stored
`jobId`. It has no create, presign, upload-contract, or S3 path, so recovery
cannot create a second job or upload the bytes again.

No migration or ORM metadata change was needed: G7.3 reuses the existing G4
source identity columns. Alembic drift remained clean.

### Complete jobs-map validation

Candidate-token admission and authenticated reconciliation share one exact
runtime validator. It requires the complete closed job-summary field set,
rejects extra fields, validates UUID-shaped distinct project/job identities,
entry ID/map-key agreement, canonical/legacy status agreement, booleans,
integer progress 0–100, metadata/error nullability, positive numeric domains,
and real calendar-valid ISO timestamps. Project-name length is counted as
Unicode code points, matching the Python/PostgreSQL 200-character contract.

Multiple processing-job versions may belong to one durable project; that is a
supported data-model case and is not rejected. Migration 0002 intentionally
created equal project/job UUIDs for populated pre-G3 rows. Those synthetic rows
lack G3+ cloud provenance and cannot satisfy the distinct cloud identity
contract, so `/api/v1/jobs` omits them rather than allowing one historic row to
break token admission for the whole portfolio. This is an explicit v0.1 cloud
listing compatibility boundary; the accepted migration history is unchanged.

## Executing proof map

| Defect / boundary | Executing proof |
|---|---|
| server A + local B reconstruction | mounted real `EditorPage.reconstruction.test.tsx` renders B on mount/remount |
| text A→B wire authority | coordinator deferred tests plus mounted Apply test assert serialized wire A,B, final key removal, and server-B remount |
| active true→false authority | coordinator and mounted toggle tests assert serialized true,false, retained pending false, final key removal, and inactive remount |
| failed A / failed B / unrelated scenes | `cloudDraftSave.test.ts` executes lane release, retry-draft retention, and independent scene lanes |
| stale overrides GET after PATCH | mounted test resolves PATCH B before a mount-time GET A and proves B remains before and after remount |
| unmount during PATCH | unit and mounted cross-remount tests keep draft B while the next mount's stale GET A resolves |
| older success UI | mounted deferred A/B test proves A never displays success for pending B |
| exact token generation | `cloudProjects.test.ts` defers logout, replacement-token, independent-new-token, and same-session coalescing cases |
| stale jobs list after completion | mounted `CloudCompletionButton.dom.test.tsx` accepts completion, then resolves old AWAITING and retains processing |
| never-uploaded vs uploaded AWAITING | API marker/capacity tests plus reconciliation tests hide fresh reservations and retain server/local upload evidence |
| first-response transport recovery | API interruption test preserves the server marker; mounted hook test exhausts completion transport, rehydrates the same job, and retains the action |
| same-job retry without re-upload | mounted hook and recovery-button tests assert one create, one S3 POST, and completion-only retry for the exact job |
| expired first reservation | mounted hook test keeps the expired first job hidden and publishes only the uploaded replacement |
| full jobs-map contract | `cloudApi.test.ts` removes/corrupts every mandatory field through both paths and covers hostile shapes, every canonical state, duplicate job versions, Unicode names, and valid empty map |
| pre-G3 equal-ID compatibility | `test_g3_integration.py` inserts the accepted backfill shape and proves cloud list omission |
| real route boundary | mounted production browser router uses real LoginPage, guards, session store, and real EditorPage/query lifecycle for the logout cache case |
| real hook lifecycle | mounted `useUploadFlow.dom.test.tsx` executes file replacement, cancel, unmount, pending create/S3, late callbacks, retry, and recreation |
| empty edit storage | coordinator and `persistenceMode.test.ts` prove final-key removal and real-entry-only Settings counts |

## Evidence categories

### API / integration tested

- Final focused marker/state/summary/list run: **33 passed**, one pre-existing
  Starlette/httpx deprecation warning.
- Full `make cloud-test`: **286 passed**, one pre-existing warning.
- `make isolation-proof`: the same **286 passed**; Alembic head, tables, exact
  database sentinel, development-queue message, and queue attributes remained
  unchanged; `ISOLATION PROOF OK`.
- Root pipeline pytest through the pinned Python environment: **56 passed**.
- `make g2-verify`: `No new upgrade operations detected`.
- Ruff check clean; Ruff format check: **146 files already formatted**.

### Mounted DOM / hook / router tested

- Final focused G7.3 frontend run: **123 passed in 8 files**.
- The four mounted suites execute **22 tests**: real EditorPage (5), real
  `useUploadFlow` (9), mounted recovery component/page (3), and production
  browser router/session boundary (5).
- Full frontend Vitest: **189 passed in 19 files**.
- ESLint: 0 errors, one pre-existing `EditorTour.tsx` warning.
- Forced TypeScript (`npx tsc -b --force`): clean.
- Production, cloud, and demo builds: green; each transformed 2,141 modules.
- Demo preview smoke: `/` 200 `text/html`; `/tutorials` 200 `text/html`;
  `scenes.json` 200 `application/json` (8,655 bytes); primary video 200
  `video/mp4` (8,940,006 bytes).

### Live browser status (completed after `e0eb003`; recorded forward at G8 Part A)

The G7.3 implementation worker had no Browser runtime, so `e0eb003` honestly
recorded the live-browser gate as pending. The orchestrating Codex review
subsequently executed and accepted the gate on the exact `e0eb003` tree.
Environment: local PostgreSQL + LocalStack + SQS, the API image rebuilt from
`e0eb003`, the existing compatible G5 production worker image, the fake
provider, and the existing rights-cleared Sintel fixture. The API rebuild
corrected a stale local container/tree mismatch observed during the review; it
was an environment refresh, not a source defect.

Accepted journey — Login → Upload → Projects/Editor → Help → Settings →
logout:

- an invalid token remained on Login with the safe access error; the
  documented local token reached the dashboard after the API image was
  rebuilt from the current tree;
- the browser direct upload completed and the worker reached terminal
  `Ready!` at `100%`;
- the editor loaded the pinned video and all required artifacts with
  `60/60` scenes;
- one scene edit persisted after a browser refresh;
- the Apply status existed immediately and at 1.5 s, and was gone at 3.3 s,
  proving the intended approximately three-second confirmation;
- corrected cloud Help and Settings rendered with `/api/*`/FastAPI cloud
  guidance, the actual loopback development base, and truthful v0.2 fences;
- Projects contained the completed project and no never-uploaded/filename
  ghost card;
- logout stayed on Login after a delayed check, with no project or session
  repopulation;
- the worker and the frontend dev server were stopped afterwards; the
  support services remained healthy.

No token, signed URL, raw request capture, paid call, real-AWS claim, or
customer-like data was added by that review. Older G7.1 captures are not
relabelled as G7.3 evidence, and no screenshot or request trace that was not
saved is claimed here.

### v0.1 limitations / unchanged next gate

- Pre-G3 equal-ID backfill rows are omitted from the cloud portfolio listing;
  accepted migration history and the legacy application branch are unchanged.
- Abandoned never-uploaded rows may remain server-side until retention cleanup;
  they remain slot-free and invisible in the cloud product.
- Same-tab S3-success evidence is session-scoped. After logout, only the server
  verification marker may reconstruct a completion-pending card.
- The live-browser journey was completed by the orchestrating review on the
  exact `e0eb003` tree (see above); all evidence remains local/fake-provider —
  no real AWS or real-provider behaviour is claimed.
- Production S3 signed-host pinning remains a pre-G9/G11 item. Smart Fill, TTS
  preview, export, character rename, project rename/star/delete, and provider
  selection retain their existing v0.2 fences.
- G8 prerequisites are unchanged: worker `fullmatch` + rebuild + five-minute
  memory test; deployed reader `s3:GetObjectVersion`; lifecycle protection for
  pinned noncurrent versions; and `pipeline_revision` binding alignment.
