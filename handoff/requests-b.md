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
