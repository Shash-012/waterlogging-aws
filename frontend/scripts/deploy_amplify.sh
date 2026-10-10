#!/usr/bin/env bash
# Builds the dashboard and deploys dist/ to Amplify Hosting as a manual (zip) deploy.
# The first run creates the Amplify app and branch; later runs reuse them.
#
#   frontend/scripts/deploy_amplify.sh          build, upload, deploy
#   frontend/scripts/deploy_amplify.sh --plan   show what would be created or reused, change nothing
#
# The build reads frontend/.env.local (never committed) for the VITE_* settings,
# or the same names from the environment. Overrides: AWS_PROFILE, AWS_REGION,
# AMPLIFY_APP_NAME, AMPLIFY_BRANCH.
set -euo pipefail

PROFILE="${AWS_PROFILE:-wlew}"
REGION="${AWS_REGION:-ap-south-1}"
APP_NAME="${AMPLIFY_APP_NAME:-wlew-dashboard}"
BRANCH="${AMPLIFY_BRANCH:-main}"
PLAN=0
[[ "${1:-}" == "--plan" ]] && PLAN=1

FRONTEND="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$FRONTEND"

# The AWS CLI installer on Windows doesn't add itself to Git Bash's PATH.
command -v aws >/dev/null || PATH="$PATH:/c/Program Files/Amazon/AWSCLIV2"
# Windows ships a python3 stub that only opens the Store, so take the first one that runs.
for PY in python3 python; do "$PY" -c "" >/dev/null 2>&1 && break; done
# The Windows AWS CLI ends text output with \r\n; strip the \r so IDs and URLs come through clean.
awsc() { aws --profile "$PROFILE" --region "$REGION" "$@" | tr -d '\r'; }

# Serve index.html for every path that isn't a static file, so the SPA handles routing.
RULES='[{"source":"</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>","target":"/index.html","status":"200"}]'

# Warn about missing build settings; with none set, the app falls back to fixtures and the demo login.
for key in VITE_DATA_SOURCE VITE_CORE_API_URL VITE_OPS_API_URL VITE_COGNITO_USER_POOL_ID VITE_COGNITO_CLIENT_ID; do
  if [[ -z "${!key:-}" ]] && ! grep -qs "^$key=." .env.local; then
    echo "warning: $key is not set in the environment or frontend/.env.local" >&2
  fi
done

APP_ID="$(awsc amplify list-apps --query "apps[?name=='$APP_NAME'].appId | [0]" --output text)"
[[ "$APP_ID" == "None" ]] && APP_ID=""
HAS_BRANCH=0
[[ -n "$APP_ID" ]] && awsc amplify get-branch --app-id "$APP_ID" --branch-name "$BRANCH" >/dev/null 2>&1 && HAS_BRANCH=1

if [[ $PLAN == 1 ]]; then
  echo "Profile $PROFILE, region $REGION"
  if [[ -n "$APP_ID" ]]; then echo "App:    reuse $APP_NAME ($APP_ID), reapply the SPA rewrite rule"
  else echo "App:    CREATE $APP_NAME (platform WEB, no repository, SPA rewrite to /index.html)"; fi
  if [[ $HAS_BRANCH == 1 ]]; then echo "Branch: reuse $BRANCH"
  else echo "Branch: CREATE $BRANCH"; fi
  echo "Deploy: npm run build, zip dist/, upload, start a deployment on $BRANCH"
  exit 0
fi

echo "==> Building"
npm run build

echo "==> Zipping dist/"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
ZIP="$WORK/dist.zip"
# Python's zipfile always writes forward-slash paths, which Amplify needs (Compress-Archive on Windows may not).
"$PY" - "$FRONTEND/dist" "$ZIP" <<'PYEOF'
import os, sys, zipfile
src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(src):
        for f in files:
            full = os.path.join(root, f)
            z.write(full, os.path.relpath(full, src).replace(os.sep, "/"))
PYEOF

if [[ -z "$APP_ID" ]]; then
  echo "==> Creating Amplify app $APP_NAME"
  APP_ID="$(awsc amplify create-app --name "$APP_NAME" --platform WEB \
    --custom-rules "$RULES" --tags Project=wlew --query app.appId --output text)"
else
  awsc amplify update-app --app-id "$APP_ID" --custom-rules "$RULES" >/dev/null
fi
if [[ $HAS_BRANCH == 0 ]]; then
  echo "==> Creating branch $BRANCH"
  awsc amplify create-branch --app-id "$APP_ID" --branch-name "$BRANCH" >/dev/null
fi

echo "==> Uploading"
read -r JOB_ID UPLOAD_URL < <(awsc amplify create-deployment --app-id "$APP_ID" --branch-name "$BRANCH" \
  --query "[jobId, zipUploadUrl]" --output text)
curl -fsS -X PUT -H "Content-Type: application/zip" --upload-file "$ZIP" "$UPLOAD_URL"

echo "==> Deploying (job $JOB_ID)"
awsc amplify start-deployment --app-id "$APP_ID" --branch-name "$BRANCH" --job-id "$JOB_ID" >/dev/null
while :; do
  STATUS="$(awsc amplify get-job --app-id "$APP_ID" --branch-name "$BRANCH" --job-id "$JOB_ID" \
    --query job.summary.status --output text)"
  case "$STATUS" in
    SUCCEED) break ;;
    FAILED|CANCELLED) echo "Deployment $STATUS" >&2; exit 1 ;;
    *) sleep 5 ;;
  esac
done

DOMAIN="$(awsc amplify get-app --app-id "$APP_ID" --query app.defaultDomain --output text)"
echo "Live at https://$BRANCH.$DOMAIN"
