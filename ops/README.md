ops/ is owned by Agent B: template.yaml (stack wlew-ops), functions/send_alert, functions/list_alerts, templates/, config/.

# wlew-ops

Official login (Cognito), Telegram alerts and the alert log. Region `ap-south-1`, profile `wlew`, every resource tagged `Project=wlew`.

| Path | What it is |
|---|---|
| `template.yaml` | User pool `wlew-officials` (admin-created users only) + app client `wlew-dashboard` (no secret, `USER_PASSWORD_AUTH`); HTTP API with a Cognito JWT authorizer on every route; `SendAlertFunction`, `ListAlertsFunction`; DynamoDB `AlertsTable`; log groups `/wlew/ops/*` |
| `samconfig.toml` | Stack `wlew-ops`; `CoreApiUrl` points at wlew-core (set it to `fixtures` to use the contract's hotspot fixture instead) |
| `functions/send_alert/app.py` | `POST /alerts`: validate, fetch names from `GET {CoreApiUrl}/hotspots/{id}`, render EN + HI, send to Telegram, log. Same hotspot + run + mode within 30 min returns the earlier alert with `duplicate: true` |
| `functions/list_alerts/app.py` | `GET /alerts?limit=N` (1–200, default 50), newest first |
| `templates/` | `alert_en.txt`, `alert_hi.txt` and `labels.json` (Hindi level words, month names, replay tag, peak phrase) |
| `config/routing.json` | Hotspot → Telegram group keys, with a `default` list |
| `stage.py` | Copies send_alert + templates + config + the hotspot fixture into `build/send_alert/` for `sam build` |
| `tests/` | pytest with in-memory fakes; every response checked against `contract/schemas/` |

Secrets stay in SSM, never in git: `/wlew/telegram/bot_token` (SecureString) and `/wlew/telegram/groups` (JSON of group key → chat ID). The bot token is never logged.

## Deploy

    python ops/stage.py
    cd ops && sam build && sam deploy        # outputs OpsApiUrl, UserPoolId, UserPoolClientId, AlertsTableName

Allow the Amplify domain by CORS: `sam deploy --parameter-overrides CoreApiUrl=<url> AllowedOrigin=https://<amplify-domain>` (repeat `CoreApiUrl`, overrides replace the samconfig list).

## Test

    python -m pytest ops/tests

## Add an official

    aws cognito-idp admin-create-user --profile wlew --region ap-south-1 \
      --user-pool-id <UserPoolId> --username <name> --message-action SUPPRESS --temporary-password '<Temp1234>'

Give them the temporary password out of band; the dashboard asks for a new one on first sign-in. Passwords need 8+ characters with upper case, lower case and a number.
