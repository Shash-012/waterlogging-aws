# Agent B handoff: dashboard, login, alerts, hosting and demo kit

Branch `agent-b/ops`. Everything below was run on Windows 11 with the `wlew` AWS profile (ap-south-1). The branch only touches `ops/`, `frontend/`, `demo/`, `handoff/b.md` and `handoff/requests-b.md`, so it should merge without conflicts.

## What's live

| What | Value |
|---|---|
| **Dashboard (Amplify)** | **https://main.d3so27hxydwx7o.amplifyapp.com** (app `wlew-dashboard`, id `d3so27hxydwx7o`, branch `main`, manual zip deploys, no Git connection) |
| **OpsApiUrl** | **`https://6bic7eaatl.execute-api.ap-south-1.amazonaws.com`** (stack output of `wlew-ops`) |
| UserPoolId | `ap-south-1_0XtsfOki1` (pool `wlew-officials`) |
| UserPoolClientId | `gn2o6ub84ipm7dnd1kr4m6cua` (client `wlew-dashboard`) |
| AlertsTableName | `wlew-ops-AlertsTable-L4TFM7VX0F2W` |
| CoreApiUrl used | `https://x6klvfqev1.execute-api.ap-south-1.amazonaws.com` (Agent A's `wlew-core`) |

These IDs and URLs aren't secrets: they're built into the public JavaScript bundle. The only secrets are in SSM (below).

### Ops API (`wlew-ops`, Cognito JWT on every route)

| Route | Notes |
|---|---|
| `POST /alerts` | Body is the contract's `AlertRequest`. It looks up names and diversion text via `GET {CoreApiUrl}/hotspots/{id}`, renders English and Hindi from `ops/templates/`, and sends to the Telegram groups in `ops/config/routing.json` (default: `traffic-police-demo`, `rwa-demo`). The same hotspot + run + mode within 30 min returns the earlier alert with `duplicate: true` and sends nothing. Replay alerts start with `[Replay · <date of event_id>]`. A bad body gives 400, an unknown hotspot 404, and no or a bad token 401. |
| `GET /alerts?limit=N` | Alert log, newest first, N from 1 to 200 (default 50). |

CORS allows `http://localhost:5173` and the Amplify URL.

Secrets live only in SSM: `/wlew/telegram/bot_token` (SecureString) and `/wlew/telegram/groups` (String, JSON of group key → chat ID). Both exist. The Lambda reads them at runtime and never logs the token.

## Test users (no passwords in git)

`test-official` exists and is CONFIRMED. A human set its password, which is not in git or in any file. Ask the team for it, or reset it.

Create an official. They get a temporary password and choose their own on first sign-in, and the dashboard handles that step:

```bash
read -rs PW   # type the temporary password; keeps it out of shell history
aws cognito-idp admin-create-user --profile wlew --region ap-south-1 \
  --user-pool-id ap-south-1_0XtsfOki1 --username <name> \
  --message-action SUPPRESS --temporary-password "$PW"
unset PW
```

Reset a password: `--permanent` sets a final password, and without it the user must choose a new one at next sign-in.

```bash
read -rs PW
aws cognito-idp admin-set-user-password --profile wlew --region ap-south-1 \
  --user-pool-id ap-south-1_0XtsfOki1 --username test-official --password "$PW" --permanent
unset PW
```

Or use the console: Cognito → User pools → `wlew-officials` → Users → the user → Actions. Passwords need 8+ characters with upper case, lower case and a number. There's no self sign-up.

## Frontend: fixtures/live switch and `.env.local`

The build reads five `VITE_*` settings, normally from `frontend/.env.local`. That file is ignored by git (`*.local` in `frontend/.gitignore`) and must never be committed. Each machine needs its own copy. To deploy against the current stacks, create it with:

```
VITE_DATA_SOURCE=live
VITE_CORE_API_URL=https://x6klvfqev1.execute-api.ap-south-1.amazonaws.com
VITE_OPS_API_URL=https://6bic7eaatl.execute-api.ap-south-1.amazonaws.com
VITE_COGNITO_USER_POOL_ID=ap-south-1_0XtsfOki1
VITE_COGNITO_CLIENT_ID=gn2o6ub84ipm7dnd1kr4m6cua
```

| Setting | Effect |
|---|---|
| `VITE_DATA_SOURCE=fixtures` (the default when unset) | Reads `contract/fixtures/`, with a Rainy/Dry sample switch. `POST /alerts` is faked in the browser (same 30-min dedupe, nothing sent). |
| `VITE_DATA_SOURCE=live` | Calls `VITE_CORE_API_URL` for data and `VITE_OPS_API_URL` for alerts. |
| Both Cognito IDs set | Real Cognito sign-in (`USER_PASSWORD_AUTH`, plain `fetch`, no Amplify library). The ID token is sent as `Authorization: Bearer` on ops calls, and a 401 sends the user back to sign-in. |
| Either Cognito ID missing | Demo sign-in: any username and password, with a yellow "Demo sign-in" note. A username starting with `new` shows the choose-a-new-password step. |

Vite bakes these values in at **build time**. After changing `.env.local`, restart `npm run dev` or redeploy.

**Tests ignore `.env.local`.** `frontend/vite.config.ts` pins `test.env` to fixtures and the demo login, so `npm test` never calls live APIs or Cognito, whatever is in `.env.local`.

`?present=1` is the video mode: large type, no dev controls, and the headline replay preloaded. `?present=1&event=<event_id>` picks another replay.

## Deploy on Windows

Prerequisites: AWS CLI v2, SAM CLI, Node 20+, a Python 3.12 venv at `.venv` with `boto3 jsonschema pytest`, and Git for Windows (Git Bash). Profile `wlew`, region ap-south-1.

**Windows problems we hit, and how they're handled:**

| Problem | Effect | Handling |
|---|---|---|
| SAM CLI isn't on Git Bash's PATH; `sam.cmd` won't run from Git Bash | `sam: command not found` | Run `sam` from **PowerShell**, after adding `C:\Program Files\Amazon\AWSSAMCLI\bin` to PATH (below). |
| AWS CLI isn't on Git Bash's PATH | `aws: command not found` | `export PATH="$PATH:/c/Program Files/Amazon/AWSCLIV2"`. `deploy_amplify.sh` does this itself. |
| `python3` is the Microsoft Store stub | "Python was not found" | Use `.venv/Scripts/python`. `deploy_amplify.sh` uses the first Python that actually runs. |
| The Windows AWS CLI ends `--output text` with `\r\n` | IDs and URLs carry an invisible `\r`; `curl` rejected the upload URL and left PENDING jobs | `deploy_amplify.sh` strips `\r` from every AWS answer (`awsc` helper). Do the same (`\| tr -d '\r'`) in any new script. |
| Git converts LF to CRLF on checkout (`core.autocrlf`) | A `.sh` file with CRLF fails in bash (`$'\r': command not found`) | **Suggestion for Agent C:** add a root `.gitattributes` with `*.sh text eol=lf`. There's no `.gitattributes` yet, and I didn't add one because the repo root isn't mine. |

### Ops stack (`wlew-ops`)

`ops/samconfig.toml` already holds both parameters (`CoreApiUrl` = the core URL, `AllowedOrigin` = the Amplify URL), so a plain deploy keeps them. Always preview with a change set:

```powershell
$env:Path += ";C:\Program Files\Amazon\AWSSAMCLI\bin;C:\Program Files\Amazon\AWSCLIV2"
.venv\Scripts\python ops\stage.py      # packs send_alert + templates + routing + hotspot fixture into ops\build\
cd ops
sam build
sam deploy --no-execute-changeset      # prints the change set; read it
aws cloudformation execute-change-set --profile wlew --region ap-south-1 --change-set-name <arn printed above>
```

Test: `.venv\Scripts\python -m pytest ops\tests` → **23 passed** (in-memory fakes, no AWS).

### Frontend (Amplify)

From **Git Bash**, in the repo root, with `frontend/.env.local` in place:

```bash
cd frontend && npm ci && npm test && cd ..   # 23 tests
frontend/scripts/deploy_amplify.sh --plan    # shows create vs reuse; changes nothing
frontend/scripts/deploy_amplify.sh           # build, zip dist/, create app+branch once, upload, deploy, wait
```

The script reuses the app named `wlew-dashboard` if it exists. It reapplies the SPA rewrite (every non-file path → `/index.html`, 200) and prints the URL. Overrides: `AWS_PROFILE`, `AWS_REGION`, `AMPLIFY_APP_NAME`, `AMPLIFY_BRANCH`. A redeploy keeps the same URL.

### From scratch, in order

1. `wlew-core` (see `handoff/a.md`). Note its `CoreApiUrl`.
2. SSM parameters, if missing: `aws ssm put-parameter --name /wlew/telegram/bot_token --type SecureString --value <token>` and `--name /wlew/telegram/groups --type String --value '{"traffic-police-demo":"<chat id>","rwa-demo":"<chat id>"}'`. Values come from the team, never git.
3. `wlew-ops` with `CoreApiUrl` set (above). Note the four outputs.
4. Write `frontend/.env.local` from those outputs, then run `deploy_amplify.sh`.
5. **A new Amplify app gets a new URL.** Set it as `AllowedOrigin` on **both** `wlew-ops` (`ops/samconfig.toml`) and `wlew-core`, and redeploy both. Without that, the browser blocks the APIs.

## wlew-core CORS change (request #3, done)

On 2026-10-11, after Agent A finished and with the user's approval, I updated `wlew-core` so the hosted dashboard can read it:

- **What changed:** only the `AllowedOrigin` parameter: `http://localhost:5173` → `https://main.d3so27hxydwx7o.amplifyapp.com`. The change set had one change: `HttpApi` (`AWS::ApiGatewayV2::Api`), Modify, no replacement, and the only difference was CORS `allowOrigins` `[http://localhost:5173]` → `[http://localhost:5173, https://main.d3so27hxydwx7o.amplifyapp.com]`. No local code was deployed. The change set reused the template exactly as CloudFormation had stored it.
- **Checked:** from both origins, `/health`, `/hotspots`, `/scores/latest`, `/pumps`, `/replays` and the preflight checks return the allow header. An unlisted origin gets none.
- **Don't use `--use-previous-template` to change a parameter on these SAM stacks.** Its change set filled `AllowedOrigin` with the *old* value (`[localhost, localhost]`). That change set was deleted unrun.

**`AllowedOrigin` on `wlew-core` must stay `https://main.d3so27hxydwx7o.amplifyapp.com` on every future deploy.** The template default is `http://localhost:5173`, and **`core/samconfig.toml` on `agent-a/core` has no `parameter_overrides`**, so `cd core && sam deploy` from `handoff/a.md` doesn't state it. SAM CLI should keep an existing stack's previous value when a parameter isn't overridden, but a new stack gets localhost. Either way, the hosted dashboard would silently stop loading data. **Suggestion for Agent C at merge:** add this to `core/samconfig.toml` under `[default.deploy.parameters]`:

```toml
parameter_overrides = "AllowedOrigin=\"https://main.d3so27hxydwx7o.amplifyapp.com\""
```

Then check any core deploy's change set for `allowOrigins` before executing it.

## Tests

| Suite | Command | Result at handoff |
|---|---|---|
| Frontend (Vitest + Testing Library) | `cd frontend && npm test` | 23 passed |
| Ops (pytest, fakes for Telegram/DynamoDB/SSM; every response checked against `contract/schemas/`) | `.venv/Scripts/python -m pytest ops/tests` | 23 passed |

Live checks done in B3/B4: an unauthenticated `POST`/`GET /alerts` → 401. An authenticated replay alert reached both Telegram groups in both languages, a resend returned `duplicate: true` with nothing sent, and `GET /alerts` listed it (schema-valid). The Amplify site serves `/` and deep links (200), and a missing asset gives 404.

## Known gaps

1. **No token refresh.** Sign-in lasts about 1 hour (ID token lifetime), then the user signs in again. The refresh token is allowed on the app client but not used yet.
2. **Hosted sign-in not checked by Agent B in a browser.** `test-official`'s password was set by a human after the CORS checks, so the final "sign in on the Amplify URL and see 69 live hotspots" check is theirs. Every request the page makes was checked from its origin with `curl`.
3. **Headline replay is `2024-06-28`, and fixtures have no replay for it.** The team picked 28 Jun 2024 (`requests-a.md` #4), because the real 25 Aug 2026 replay is a miss. `?present=1` opens it (`HEADLINE_EVENT` in `frontend/src/lib/present.ts`), and `demo/script.md` follows the real replay: 25 frames, 10 spots HIGH at 23:30 IST, Pragati Maidan tunnel as the click. The contract fixtures still only have the synthetic 25 Aug storm, so fixtures mode falls back to it. Record the video on live data. If Agent C regenerates the fixture from `handoff/samples-a/`, no frontend change is needed.
4. **Fixtures have no dry replay** (`requests-b.md` #1). The live API has one (`2026-09-10`, dry control), so the dry-replay check works in live mode only.
5. **Pump plan during a replay is computed in the browser** (`requests-b.md` #2): `frontend/src/lib/pumps.ts` applies the contract's rule to the current frame. If the rule changes, that file must change with it.
6. **Video assets still to capture:** V1 (credited flooded-underpass photo, humans), V2 (`docs/architecture.svg`, Agent C), S8 (Telegram alert arriving on the phone). See `demo/shots.md`. The Cognito, SAM-deploy, Amplify and ops shots can be captured now.
7. **Amplify uses manual deploys** with the default `amplifyapp.com` domain: no Git-connected builds and no custom domain.
8. **Routing:** every hotspot goes to both demo groups (`default` in `ops/config/routing.json`). There are no per-spot routes yet.
