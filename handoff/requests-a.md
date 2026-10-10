# Agent A contract requests

None of these blocked the build. I coded to the contract as written.

1. **Say what kind of report time a ground-truth entry has.** Add an optional `time_kind` (`"post" | "stated" | "published"`) to replay `ground_truth` items. Every report time we could source is an article publication time, so lead times are upper bounds. A field would let the UI say "before the first news report" correctly. Today this is only written at the end of each `note` as `[time: published]`.
2. **Define `city.spots_raining`.** The contract doesn't define it. I count spots with forecast intensity I > 0, where I is the maximum over the current hour and the next 6, matching Agent C's fixtures. Suggested wording: "spots where I > 0".
3. **Allow replay ids that aren't calendar dates.** The `event_id` pattern `YYYY-MM-DD` forces a multi-day storm under one date. I used `2024-07-31` for the 31 Jul–1 Aug 2024 storm and `2026-08-25` for 24–25 Aug 2026 (the 25 Aug id is kept to match the fixture). Fine as is; just flagging it.
4. **Headline replay (not a contract change).** The fixture's 25 Aug 2026 replay shows a success, but the real one is a miss (see `handoff/a.md`). Agent C may want to regenerate the replay fixture from `handoff/samples-a/replay_2026-08-25.json`, or switch the demo's headline to `2024-06-28`.
