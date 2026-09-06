#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="makz-snips-${PROJECT_ID}"
BUCKET="gs://${BUCKET_NAME}"
LOCATION="us-central1"

echo "Checking if bucket ${BUCKET} exists..."
if gcloud storage buckets describe "${BUCKET}" &>/dev/null; then
    echo "Bucket ${BUCKET} already exists, proceeding..."
else
    echo "Creating bucket ${BUCKET} in ${LOCATION} (Always Free tier region)..."
    gcloud storage buckets create "${BUCKET}" --location="${LOCATION}"
fi

echo "Disabling public access prevention so the bucket can be made public..."
gcloud storage buckets update "${BUCKET}" --no-public-access-prevention --quiet 2>/dev/null || true

echo "Making bucket publicly readable..."
if ! gcloud storage buckets add-iam-policy-binding "${BUCKET}" \
  --member="allUsers" \
  --role="roles/storage.objectViewer" --quiet 2>/dev/null; then
  echo ""
  echo "⚠️  NOTE: Could not make the bucket public (Organization Policy Restriction)."
  echo "The setup script has completed, but your organization forbids public buckets."
  echo "This is fully expected for corporate Google Cloud projects (e.g., google.com)."
  echo ""
  echo "What's next?"
  echo "  👉 The 'sharing-snips' tool will still work perfectly!"
  echo "  👉 The GCS links copied to your clipboard will just require the recipient to be authenticated to view."
  echo ""
fi

echo "Configuring 90-day auto-delete lifecycle..."
cat <<EOF > /tmp/lifecycle.json
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 90}
    }
  ]
}
EOF

gcloud storage buckets update "${BUCKET}" --lifecycle-file=/tmp/lifecycle.json --quiet
rm -f /tmp/lifecycle.json

echo "Setup complete! Cloud storage bucket ${BUCKET} is ready for Sharing Snips."
