#!/bin/sh
# Deploy AlarmOps (SIMULATION) to Google Cloud Run as a public, read-only web page.
#
# Needs, in your environment (NEVER commit these):
#   GCP_PROJECT_ID   your Google Cloud project id
#   GCP_REGION       e.g. europe-west1   (default: europe-west1)
#   and an authenticated gcloud:  gcloud auth login   (locally)
#                                 or a service account in CI (see README, "Google Cloud")
# One-time: gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
set -eu

: "${GCP_PROJECT_ID:?set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-europe-west1}"
SERVICE="${CLOUD_RUN_SERVICE:-alarmops}"

# Builds the Dockerfile in the repo root with Cloud Build, then deploys it.
gcloud run deploy "$SERVICE" \
  --project "$GCP_PROJECT_ID" \
  --region "$REGION" \
  --source . \
  --port 8080 \
  --allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2 \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --project "$GCP_PROJECT_ID" --region "$REGION" --format 'value(status.url)')"
echo "Deployed: $URL"

# Post-deploy check, the same idea as the validate stage. Cloud Run reserves some paths ending
# in "z" (so /healthz is not reachable on run.app), so check the root path.
curl -fsS -o /dev/null "$URL/" && echo "OK: $URL/ responded"
