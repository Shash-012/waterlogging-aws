# Contract requests from Agent B

Agent B codes to the contract as written; these are for Agent C to settle before the merge.

## 1. Add a dry replay fixture (B2)

- **Need:** `contract/fixtures/replay_<date>.json` with `kind: "dry"`, plus its entry in `replay_index.json`.
- **Why:** B2's done-check says "the dry replay stays grey throughout", and Gate 2's end-to-end checklist has the same item. The fixtures only include the 25 Aug 2026 storm, so the dry case can't be shown or tested in fixtures mode.
- **Meanwhile:** the replay player lists whatever `GET /replays` returns, so a dry event shows up with no frontend change once it exists. The dry *snapshot* (`snapshot_dry.json`) is already covered by the Rainy/Dry sample switch and its test.
- **Impact if rejected:** none on the code; the dry-replay check moves to the live API after Agent A's A5.

## 2. Optional: pump plan for a replay hour (B5)

- **Need (optional):** a way to get the pump plan for a replay frame, e.g. `GET /pumps?count=N&event_id=<id>&frame=<index>`.
- **Why:** the demo video (proposal plan, 0:45 to 1:55) shows pumps being ranked during the replay, but `GET /pumps` only covers the latest live run.
- **Meanwhile:** during a replay the frontend applies the contract's pump-plan rule to the current frame (`frontend/src/lib/pumps.ts`). It uses only the levels, risks and importance the API returns, with no thresholds of its own. In "Now" view it always uses `GET /pumps`. A unit test checks the rule reproduces `contract/fixtures/pump_plan.json`.
- **Impact if rejected:** none; the frontend keeps its copy of the rule for replays. If Agent A changes the rule, `frontend/src/lib/pumps.ts` must change with it.

## 3. Allow the Amplify origin on wlew-core (B4) · DONE 2026-10-11

- **Need:** redeploy `wlew-core` with `AllowedOrigin=https://main.d3so27hxydwx7o.amplifyapp.com` (only that parameter changes; see `handoff/a.md`).
- **Why:** the hosted dashboard is built with `VITE_DATA_SOURCE=live`. The core API's CORS allowed only `http://localhost:5173`, so the browser blocked every `GET` from the Amplify site and the dashboard couldn't load hotspots or scores there.
- **Done:** applied with the user's approval after Agent A finished, as a CloudFormation change set built from the deployed template (not local code), with only `AllowedOrigin` changed. The only change was `HttpApi` CORS `allowOrigins`: `[http://localhost:5173]` → `[http://localhost:5173, https://main.d3so27hxydwx7o.amplifyapp.com]`, with no replacement. Checked: both origins get `Access-Control-Allow-Origin` on every dashboard route and on preflight; an unlisted origin gets none.
- **Note:** `--use-previous-template` doesn't work for this on a SAM stack. Its change set filled `AllowedOrigin` with the old value (`[localhost, localhost]`), so it was deleted unrun.
- **Keep it set:** every future `wlew-core` deploy must pass `AllowedOrigin=https://main.d3so27hxydwx7o.amplifyapp.com`. The template's default is `http://localhost:5173`, so a deploy without it (for example `sam deploy` without that override) silently drops the Amplify origin and the hosted dashboard stops loading data. `wlew-ops` already keeps it in `ops/samconfig.toml`.
