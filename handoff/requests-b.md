# Contract requests from Agent B

Agent B codes to the contract as written; these are for Agent C to settle before the merge.

## 1. Add a dry replay fixture (B2)

- **Need:** `contract/fixtures/replay_<date>.json` with `kind: "dry"`, plus its entry in `replay_index.json`.
- **Why:** B2's done-check says "the dry replay stays grey throughout", and Gate 2's end-to-end checklist has the same item. The fixtures only include the 25 Aug 2026 storm, so the dry case can't be shown or tested in fixtures mode.
- **Meanwhile:** the replay player lists whatever `GET /replays` returns, so a dry event shows up with no frontend change once it exists. The dry *snapshot* (`snapshot_dry.json`) is already covered by the Rainy/Dry sample switch and its test.
- **Impact if rejected:** none on the code; the dry-replay check moves to the live API after Agent A's A5.
