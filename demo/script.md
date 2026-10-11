# Demo video script (2:50)

The video is the only thing judges see, so it has to prove the system works. This script follows the proposal's five-part video plan, squeezed from 3:00 to 2:50 so there are 10 seconds of slack. Every click is written out. AWS console shots are listed in [shots.md](shots.md) by ID (`S1`, `S2`, …).

| Part | Time | Proposal plan |
|---|---|---|
| 1 · Problem | 0:00 – 0:20 | A flooded underpass on a real past date |
| 2 · Who it's for | 0:20 – 0:40 | The flood control room and how it works today |
| 3 · Proof | 0:40 – 1:50 | Replay of that date: map turns red hours early, pumps ranked, alert arrives on a phone |
| 4 · Where AWS fits | 1:50 – 2:25 | Architecture, naming each AWS service, with real console shots |
| 5 · Impact | 2:25 – 2:50 | How much warning each hotspot had, and what comes next |

## Before recording

### Fill in the blanks
Every number in the video must match `model/README.md` (Agent A's A5 results) and the headline replay as the deployed API serves it. **Don't use the numbers in `contract/fixtures/`: that replay is synthetic.**

The headline replay is **`2024-06-28`** (Delhi record downpour, 28 Jun 2024). The "Value on 11 Oct 2026" column is what the live API served that day. Re-check each one just before recording, from `GET /replays/2024-06-28` and `model/README.md`.

| Blank | Where it comes from | Value on 11 Oct 2026 |
|---|---|---|
| `⟨SPOTS⟩` | Number of hotspots: `GET /hotspots` length, also in `handoff/a.md` | 69 |
| `⟨REPORTED⟩` | Headline replay `metrics.spots_reported` | 14 |
| `⟨FLAGGED⟩` | Headline replay `metrics.flagged_before_report` | 3 (Pragati Maidan tunnel, ITO crossing, Tilak Bridge (W-Point) underpass) |
| `⟨MEDIAN⟩` | Headline replay `metrics.median_lead_hours` | 10.6 |
| `⟨UNCONFIRMED⟩` | Headline replay `metrics.unconfirmed_flags` | 7 |
| `⟨MISS⟩` | One honest miss from `model/README.md`, or cut that sentence if there's none | The 25 Aug 2026 storm: the forecasts never showed the burst, so no spot went above WATCH. Suggested line: "On 25 August 2026 the forecasts missed a short cloudburst entirely, and so did we." |
| `⟨RAINFALL⟩` | The replay's `title_en`; re-check against the source A cites | 228 mm at Safdarjung |

**The spot to click is Pragati Maidan tunnel.** It's rank 1 when the first spots turn HIGH (hour 11, 27 Jun 23:30 IST), and it was reported closed the next morning (10.6 h later). If a re-check shows a different rank-1 spot at hour 11, use that one and change the clicks below.

### Set up
- [ ] B3 and B4 are deployed: the Amplify URL loads, a test official can sign in, and alerts reach both Telegram test groups.
- [ ] Headline replay is `2024-06-28`, and `?present=1` opens it. To record another storm, open `?present=1&event=<event_id>` and update every date and click below.
- [ ] Record on the Amplify URL (live data). The fixtures have no 28 Jun 2024 replay, so `npm run dev` in fixtures mode falls back to the synthetic 25 Aug storm, which is fine for practising clicks but not for the real take.
- [ ] Laptop: Chrome, window maximised at 1920 × 1080, browser zoom 100%, bookmarks bar hidden, notifications off (Windows: Focus assist on).
- [ ] Open `<AMPLIFY_URL>/?present=1` and **sign in before recording**. Present mode starts on the headline replay at hour 1 with large type and no dev controls.
- [ ] Set **Pumps available** to `6`.
- [ ] Phone: Telegram open on the "Traffic police (demo)" group, Do Not Disturb off for Telegram only, screen recording ready. Clear old test alerts from the group so the new one is obvious.
- [ ] Alerts are de-duplicated for 30 minutes per spot, run and mode. Between takes, wait 30 minutes or pick a different replay hour for the alert, or the second take shows "Already sent".
- [ ] Have [shots.md](shots.md) captures `S1` to `S7` and the architecture diagram (`docs/architecture.svg`) ready in the editor.
- [ ] Have the problem photo or footage for Part 1 with its source and licence noted. Credit it on screen.

### Recording tips
- Record the screen and the phone separately, then cut them together. Record the voice-over last, reading the lines below at an even pace (about 150 words a minute).
- Move the mouse slowly and pause half a second before each click.
- If a take goes wrong, reload `<AMPLIFY_URL>/?present=1` to get back to hour 1.

---

## Part 1 · Problem (0:00 – 0:20)

**On screen:** the real photo or news clip of a flooded Delhi road or underpass on 28 Jun 2024 (Minto Bridge, ITO or the Pragati Maidan tunnel if available). Caption: *"Delhi, 28 Jun 2024 · ⟨RAINFALL⟩ in a day"* plus the source credit.

**Voice-over (~45 words):**
> On the 28th of June 2024, Delhi got ⟨RAINFALL⟩ of rain. Minto Bridge and ITO went under water, and the Pragati Maidan tunnel was shut. The city already knows these spots flood every monsoon. What it doesn't get is a warning in time to act.

## Part 2 · Who it's for (0:20 – 0:40)

**On screen:** a simple title card: *"Flood control room · today: pumps move after the complaints arrive"*. Then cut to the dashboard (already open in present mode) so the transition into Part 3 is seamless.

**Voice-over (~50 words):**
> This is for the flood control room and ward engineers. Today they watch the sky and the complaint line, and send pumps once a road is already flooded. Our tool gives them a ranked list of which hotspots will flood in the next six hours, and where to send pumps first.

## Part 3 · Proof: the replay (0:40 – 1:50)

**On screen:** the dashboard at `<AMPLIFY_URL>/?present=1`. The dark strip at the top reads **"Replay of 28 Jun 2024"** and stays there the whole time.

**What the replay does** (25 hourly frames, 27 Jun 13:30 IST to 28 Jun 13:30 IST; at **1×** each hour lasts 1 second):

| Hour | Time (IST) | What happens |
|---|---|---|
| 1–8 | 27 Jun 13:30 – 20:30 | **Standby**, every marker grey |
| 9–10 | 21:30 – 22:30 | **Rain watch**, amber WATCH triangles appear |
| 11–13 | 23:30 – 01:30 | **Alert**: **10 spots HIGH** at once (the peak), led by Pragati Maidan tunnel. No spot reaches CRITICAL in this storm |
| 14 | 28 Jun 02:30 | Alert, 8 spots HIGH |
| 15 onwards | 03:30 → | The forecast peak passes, and spots drop back to WATCH/LOW |
| 20 | 08:30 | First dashed report rings appear (published 07:49 IST), including Tilak Bridge |
| 22 | 10:30 | All 14 report rings shown (the rest published 10:05 IST), including Pragati Maidan tunnel and ITO |

| Time | Click / action | What viewers should see |
|---|---|---|
| 0:40 | Hover over the replay strip for one second, then over the banner. | Banner says **Standby**. Every marker is a grey circle. Slider at **Hour 1 of 25 · 27 Jun, 13:30 IST**. |
| 0:45 | Click **Play** (leave the speed at **1×**). | The hour counter moves one hour per second. |
| 0:53 | As soon as the banner changes to **Rain watch** (hour 9, 21:30 IST), click **Pause**. | Banner: **Rain watch**. Amber triangles appear. |
| 0:56 | Point the mouse at the time under the slider ("Hour 9 of 25 · 27 Jun, 21:30 IST"). | Viewers see the clock time: evening, before the storm. |
| 1:00 | Click **Play**. When the orange **squares** appear (hour 11, 23:30 IST), click **Pause**. | Banner: **Alert**. Ten spots turn HIGH at once, and no flood has been reported yet (no dashed blue rings). |
| 1:05 | In the ranked list on the right, click **Pragati Maidan tunnel** (rank 1). | The detail panel opens: level chip **HIGH**, risk, peak time. |
| 1:08 | Move the mouse slowly down the four bars: **Rain trigger**, **Flood history**, **Low-lying**, **Catchment**. | "Why this level?": rain forecast × how flood-prone the spot is. |
| 1:15 | In the detail panel, click **Send alert**. | Status line: "Sent: [Replay · 28 Jun 2024] HIGH waterlogging risk at Pragati Maidan tunnel …" |
| 1:18 | **Cut to the phone** (shot `S8`). | The Telegram message arrives in "Traffic police (demo)" in Hindi and English, starting with **[Replay · 28 Jun 2024]**. Hold 4 seconds. |
| 1:23 | **Cut back to the dashboard.** Click **Close** on the detail panel. Stay on hour 11: this is the peak. | Ten HIGH orange squares across the city. |
| 1:27 | Point at the **Pumps** card ("For the replay hour shown"): "**6 of 6 pumps assigned to 6 spots**". | Blue glow on the map around the six spots that get pumps. |
| 1:31 | Point at the red box under it: "**4 HIGH-or-above spots without a pump**". | Jangpura, Tilak Bridge (W-Point) underpass, Ring Road opposite WHO building and Bhairon Marg railway underbridge. The tool says what's left uncovered. |
| 1:36 | Click **Play**. When the first dashed blue rings appear (hour 20, 08:30 IST), click **Pause**. Hover the Tilak Bridge ring. | Ring tooltip: "Reported flooded at 28 Jun, 07:49 IST". Callout: "**Tilak Bridge (W-Point) underpass: Flagged HIGH 8.3 h before the first report**". |
| 1:46 | Drag the slider to the far right (hour 25). | All 14 rings. Callouts for **Pragati Maidan tunnel** and **ITO crossing: Flagged HIGH 10.6 h before the first report**. The banner is back to Standby. |

**Voice-over (~150 words), starting at 0:40:**
> Here's that same day, replayed hour by hour using only the forecasts that existed at the time, not rain that fell later. In the afternoon, Delhi is on standby. In the evening, as forecast rain arrives, the city moves to rain watch. Then at half past eleven at night, before the heavy rain began and hours before any flood was reported, ten hotspots turn high. Click one and it explains itself: the rain forecast, multiplied by how flood-prone this spot is, from its flood history, how low it sits, and how much water drains into it. One click, after an official confirms, sends the alert, in Hindi and English, to the traffic police and residents' groups they already use. With six pumps, the tool says where each one goes first, and which four high-risk spots are left uncovered. By morning the reports come in, and each dashed ring shows how early we flagged that spot.

## Part 4 · Where AWS fits (1:50 – 2:25)

**On screen:** `docs/architecture.svg` full screen for 10 seconds, then quick cuts of the console shots (about 3 to 4 seconds each). Highlight each service on the diagram as it's named.

| Time | Shot | Voice-over line it sits under |
|---|---|---|
| 1:50 | Architecture diagram | "Everything runs serverless on AWS, deployed with the open-source SAM CLI." |
| 1:58 | `S1` EventBridge schedule | "Every hour, EventBridge Scheduler…" |
| 2:02 | `S2` CloudWatch log line | "…runs a Lambda that pulls the Open-Meteo forecast and scores every hotspot…" |
| 2:06 | `S3` DynamoDB items | "…and stores the results in DynamoDB." |
| 2:10 | `S4` API Gateway routes | "API Gateway serves the dashboard,…" |
| 2:13 | `S5` Amplify app | "…hosted on Amplify,…" |
| 2:16 | `S6` Cognito user pool | "…with Cognito so only officials can sign in and send alerts." |
| 2:19 | `S7` CloudFormation stack outputs | "Elevation comes from the Copernicus DEM on AWS Open Data." |

**Voice-over (~75 words):**
> Everything runs serverless on AWS, deployed with the open-source SAM CLI. Every hour, EventBridge Scheduler runs a Lambda that pulls the Open-Meteo forecast and scores every hotspot, and stores the results in DynamoDB. API Gateway serves the dashboard, hosted on Amplify, with Cognito so only officials can sign in and send alerts. Elevation comes from the Copernicus DEM on AWS Open Data. Idle, it costs almost nothing.

## Part 5 · Impact (2:25 – 2:50)

**On screen:** back on the dashboard at the last replay hour. Slowly move the mouse over the four cards in the **Replay** results grid.

| Time | Click / action | What viewers should see |
|---|---|---|
| 2:25 | Hover **Spots reported flooded**, then **Flagged HIGH before report**. | `⟨REPORTED⟩` and `⟨FLAGGED⟩` |
| 2:31 | Hover **Median warning**. | `⟨MEDIAN⟩` |
| 2:35 | Hover **Flags with no report found**. | `⟨UNCONFIRMED⟩` |
| 2:40 | Fade to an end card: project name, repo URL, "Built on AWS · Data: Open-Meteo, Copernicus DEM, OpenStreetMap". | Hold to 2:50. |

**Voice-over (~60 words):**
> On this day, ⟨FLAGGED⟩ of the ⟨REPORTED⟩ spots that flooded were flagged high before the first report, with a median of ⟨MEDIAN⟩ hours of warning. ⟨UNCONFIRMED⟩ flags had no report we could find, which isn't proof of a false alarm. ⟨MISS⟩. Next: a post-rain flood log so the scores improve every season. Pumps and diversions, before the road floods.

---

## After recording
- [ ] Total length is under 3:00 (target 2:50).
- [ ] Every number spoken or shown matches `model/README.md`.
- [ ] The "Replay of …" strip is visible in every dashboard frame, and the Telegram message shows "[Replay · …]".
- [ ] No token, chat ID, password, email or AWS account ID is visible anywhere (see the masking notes in [shots.md](shots.md)).
- [ ] The photo/footage credit is on screen in Part 1.
- [ ] Upload to YouTube as public or unlisted.
