# Shot list

The rules say AWS must be visible in the video itself, not just named in the writeup. These are the real console shots and the phone shot that [script.md](script.md) cuts to. **Nothing below can be captured yet: the AWS account isn't ready and the stacks aren't deployed.** Every item is marked *to capture later*.

Save every capture to `demo/screenshots/` with the file name given, as a PNG screenshot or a short MP4 screen recording (3 to 5 s). Region for everything: **Asia Pacific (Mumbai) `ap-south-1`**.

## Before you capture: mask these
Blur or crop before saving. Never commit an unmasked capture.
- AWS account ID (top-right account menu, and inside any ARN)
- Telegram bot token and chat IDs (SSM parameters `/wlew/telegram/bot_token`, `/wlew/telegram/groups`)
- Email addresses and usernames of test officials (Cognito users list)
- Any password, and the browser address bar if it shows a sign-in token

## AWS console shots

| ID | Status | Used at | What and where | Must be visible | File |
|---|---|---|---|---|---|
| S1 | ⏳ to capture later | 1:58 | **EventBridge Scheduler.** Console → Amazon EventBridge → Scheduler → Schedules → the `wlew-core` scoring schedule. | Schedule expression `rate(1 hour)`, state **Enabled**, target = the scoring Lambda. | `S1-eventbridge-schedule.png` |
| S2 | ⏳ to capture later | 2:02 | **CloudWatch log line from an hourly run.** Lambda → the scoring function → Monitor → View CloudWatch logs → the latest log stream. | The one structured line A7 logs per run: `run_id`, spots raining, spots at HIGH or above, duration. Timestamps from two consecutive hours, to show it runs on its own. | `S2-cloudwatch-scoring-log.png` |
| S3 | ⏳ to capture later | 2:06 | **DynamoDB items.** DynamoDB → Tables → the snapshots table → Explore table items. | The `LATEST` pointer item and at least one snapshot item with a recent `run_id`. | `S3-dynamodb-items.png` |
| S4 | ⏳ to capture later | 2:10 | **API Gateway routes.** API Gateway → APIs → the `wlew-core` HTTP API → Routes. Then the `wlew-ops` API → Routes → Authorization. | Core: `GET /health`, `/hotspots`, `/hotspots/{id}`, `/scores/latest`, `/pumps`, `/replays`, `/replays/{event_id}`. Ops: `POST /alerts` and `GET /alerts` with the **JWT authorizer** attached. | `S4-apigateway-routes.png` |
| S5 | ⏳ to capture later | 2:13 | **Amplify app.** AWS Amplify → the dashboard app → the branch → Deployments. | A successful deployment and the app's domain (the same URL the video uses). | `S5-amplify-app.png` |
| S6 | ⏳ to capture later | 2:16 | **Cognito user pool.** Amazon Cognito → User pools → the `wlew-ops` pool → Sign-up experience. | Self-registration **disabled** (officials are created by an admin). Mask user emails if the Users tab is shown. | `S6-cognito-pool.png` |
| S7 | ⏳ to capture later | 2:19 | **SAM deploy output.** Terminal: `sam deploy` for `wlew-core` and `wlew-ops`, profile `wlew`, region `ap-south-1`. | "Successfully created/updated stack" and the **Outputs** table (`CoreApiUrl`, `OpsApiUrl`, `UserPoolId`, `UserPoolClientId`). Mask the account ID in ARNs. | `S7-sam-deploy.png` |

## Phone shot

| ID | Status | Used at | What and where | Must be visible | File |
|---|---|---|---|---|---|
| S8 | ⏳ to capture later (needs B3 + B4) | 1:18 | **Telegram alert arriving.** The demo phone, Telegram open on "Traffic police (demo)", screen-recorded while **Send alert** is clicked on the laptop. Optionally a second clip of "RWA (demo)". | The message arriving live, starting with **[Replay · 28 Jun 2024]**, in Hindi and English, with the spot name, risk, peak time, avoid and diversion text. | `S8-telegram-alert.mp4` |

## Other visuals the video needs

| ID | Status | Used at | Owner | Notes |
|---|---|---|---|---|
| V1 | ⏳ to source | 0:00 | Humans | A real photo or news clip of a flooded Delhi road or underpass on the headline date, **28 Jun 2024** (Minto Bridge, ITO or the Pragati Maidan tunnel if available). Record the source URL and licence, and credit it on screen. |
| V2 | ⏳ waiting on Agent C | 1:50 | Agent C (`docs/architecture.svg`) | Architecture diagram naming EventBridge Scheduler, Lambda, DynamoDB, S3, API Gateway, Amplify, Cognito, SAM CLI, Copernicus DEM on AWS Open Data, Open-Meteo and Telegram. |
| V3 | ✅ ready to rehearse | 0:40 – 2:50 | Agent B | The dashboard itself: `?present=1`, which opens the headline replay **28 Jun 2024** on live data. The fixtures have no 28 Jun 2024 replay, so `npm run dev` in fixtures mode falls back to the synthetic 25 Aug 2026 storm, which is fine for practising clicks. **Record the final take on the deployed Amplify URL with live data.** |
