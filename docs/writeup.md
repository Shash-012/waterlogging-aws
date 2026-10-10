# Waterlogging Early Warning System for Delhi

*WeMakeDevs x AWS Environmental Hacks, Heat and Water track.*

## The problem

On 28 June 2024, Safdarjung recorded 228.1 mm of rain in 24 hours, Delhi's highest June total since 1936. The Minto Bridge underpass and the Pragati Maidan tunnel flooded. This happens every monsoon at the same few dozen places: underpasses, low junctions and colonies at the bottom of a drain. The city knows where they are. What it usually lacks is a few hours' notice of which of them will flood tonight, so it can move pumps, close an underpass and divert traffic before vehicles get stuck rather than after.

Forecasts already contain much of that signal. But a rain forecast for "Delhi" doesn't tell a traffic inspector which underpass to close. We wanted to turn the forecast into a ranked, spot-by-spot warning that an official can act on in one click, and to measure honestly how much warning it would have given in real storms.

## What we built

- **A risk score for 69 known hotspots, every hour.** Risk = RainTrigger x Susceptibility.
  - **RainTrigger** comes from the highest forecast rain over the next 6 hours, boosted when the last 24 hours were already wet.
  - **Susceptibility** combines three factors:
    - **History**: how many monsoon seasons from 2019 to 2025 had a sourced flood report at the spot.
    - **LowLying**: how far the spot sits below its surroundings, from the Copernicus 30 m elevation model.
    - **Catchment**: how much land drains towards it, from D8 flow accumulation on the same model.

  Each spot gets a level (LOW, WATCH, HIGH, CRITICAL), and the city gets a status (STANDBY, RAIN_WATCH, ALERT, SEVERE).
- **A dashboard for officials.** It has a map with a different marker shape per level, a ranked list in English or Hindi, a panel explaining why a spot is at risk, and a pump planner that assigns a limited number of pumps by a fixed rule.
- **One-click alerts.** A signed-in official sends a warning in English and Hindi, with avoid and diversion advice, to Telegram groups for the traffic police and resident welfare associations. A repeat within 30 minutes is caught and not sent again, and every alert is logged.
- **Honest replays.** The replay player re-runs past storms hour by hour, using only the forecasts that had been issued by that hour. It shows when each spot would have been flagged and when the first report about it appeared.

## Results

We replayed four storms and one dry control day with the frozen v1 parameters. "First report" is the publication time of the first news article naming the spot, because we found no timestamped official posts. Every lead time is therefore an upper bound.

| Storm | Reported spots | Flagged HIGH before the report | Median lead (upper bound) | Flagged, no report found |
|---|---|---|---|---|
| 28 Jun 2024 | 14 | 3 | 10.6 h | 7 |
| 31 Jul 2024 | 8 | 3 | 23.1 h | 24 |
| 7 Aug 2026 | 8 | 2 | 27.5 h | 27 |
| 25 Aug 2026 | 7 | 0 (miss) | none | 0 |
| 10 Sep 2026 (dry) | 0 | 0 | none | 0 |

- **28 Jun 2024.** The city left STANDBY at 21:30 IST on 27 June, and the first spots turned HIGH at 23:30 IST, about 3.5 hours before the stated 03:00 rain start. Pragati Maidan tunnel, ITO and Tilak Bridge were flagged before their first reports. Minto Bridge, Moolchand, Dhaula Kuan and 8 other reported spots were not.
- **31 Jul 2024 and 7 Aug 2026.** The long leads are inflated by articles published the next day, so read them with care.
- **25 Aug 2026 is a miss.** No issued ECMWF run forecast more than 4.1 mm/h, against about 72 mm reported in under two hours. The city reached ALERT, but no spot went above WATCH. We kept it in the results instead of tuning it away. The forecast model's 9 km resolution limits the system more than the formula does.
- **The dry day** stays all LOW and STANDBY in every frame.

Tuning moved the rain thresholds to I0 = 4 mm/h and I1 = 20 mm/h (from 5 and 30), and the weights to 0.45 / 0.40 / 0.15 for history, low-lying and catchment (from 0.40 / 0.35 / 0.25). With the new weights, 14 of the 37 reports fall on the 10 most susceptible spots, up from 9. The rain parameters were tuned on two storms and held out on two. The weights used all four storms, so they aren't independently tested. Details are in `model/README.md`.

## Where AWS fits

Everything runs serverless in ap-south-1 (Mumbai) as two AWS SAM stacks. There's nothing to patch and nothing that costs money while idle.

- **Amazon EventBridge Scheduler** triggers the scoring every hour.
- **AWS Lambda** (Python 3.12, arm64) runs the scorer, the read API, and the alert sender and log. The risk model ships as a Lambda layer, and the same pure-Python package runs the replays and the unit tests offline.
- **Amazon DynamoDB** stores hotspots, hourly snapshots (with a `LATEST` pointer and a 30-day TTL) and the alert log.
- **Amazon S3** holds the replay files, which are too large for DynamoDB items.
- **Amazon API Gateway HTTP APIs**: one public and GET-only, one where every route needs a Cognito JWT.
- **Amazon Cognito** handles sign-in for officials, with no self sign-up.
- **AWS Systems Manager Parameter Store** keeps the Telegram bot token and chat IDs out of the code and the repo.
- **AWS Amplify Hosting** serves the React dashboard.
- **Amazon CloudWatch Logs** gets one structured line per scoring run, with 30-day retention.
- **AWS Open Data**: the Copernicus GLO-30 elevation tiles come straight from the `copernicus-dem-30m` bucket.
- **AWS Budgets**: a $20 budget alert. There are no EC2, NAT Gateway, RDS or SageMaker resources.

## How we built it: Claude Code with three agents

The code was written with **Claude Code** as the AI coding tool, in three agent sessions with separate jobs:

1. **Agent C** started by writing the shared contract: the risk formulas, every JSON payload, both APIs, the deploy names, JSON Schemas, fixtures that obey the formulas, and a validator. It then froze the contract and created one branch per build agent.
2. **Agent A** (data, model, core backend) and **Agent B** (dashboard, sign-in, alerts, hosting, demo kit) worked in parallel. Each owned its own folders and coded only against the contract. When one needed something the contract didn't give, it wrote a change request in `handoff/` and kept going. Agent B built the whole dashboard against fixtures before Agent A's API existed.
3. **Agent C** came back to integrate. It settled the change requests as contract v1.1, merged both branches with no conflicts, and regenerated the fixtures from real API responses. It confirmed the deployed stacks match the code, ran the end-to-end checklist and wrote these docs.

The people on the team did what agents can't or shouldn't do alone: creating the AWS and Telegram accounts, holding secrets and test passwords, approving every AWS change set before it ran, and making the calls the data forced. The biggest was switching the headline replay to 28 Jun 2024 after the 25 Aug 2026 replay turned out to be a miss.

## What's next

- Higher-resolution or nowcast rain (radar, or a convection-permitting model) to catch bursts like 25 Aug 2026.
- Timestamped ground truth from official posts, so lead times are measured against flooding rather than news publication.
- A post-rain flood log where officials mark which spots actually flooded. It would feed next season's History factor.
- Per-ward alert routing to real department groups, and token refresh so officials stay signed in through a long night.

Data: Copernicus GLO-30 DEM (ESA / European Union, via AWS Open Data), © OpenStreetMap contributors, Open-Meteo (ECMWF IFS).
