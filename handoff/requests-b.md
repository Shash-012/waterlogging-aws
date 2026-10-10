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

## 3. Allow the Amplify origin on wlew-core (B4)

- **Need:** redeploy `wlew-core` with `AllowedOrigin=https://main.d3so27hxydwx7o.amplifyapp.com` (only that parameter changes; see `handoff/a.md`).
- **Why:** the hosted dashboard is built with `VITE_DATA_SOURCE=live`. Today the core API's CORS allows only `http://localhost:5173`, so the browser blocks every `GET` from the Amplify site and the dashboard can't load hotspots or scores there. Sign-in (Cognito) and alerts (`wlew-ops`, already allowing that origin) are not affected.
- **Meanwhile:** the live dashboard works from `npm run dev` on localhost. Agent B left `wlew-core` untouched because it's Agent A's stack.
- **Impact if rejected:** the hosted copy would have to be rebuilt with fixtures, which also turns off real sign-in and alerts there.
