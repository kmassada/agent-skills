---
name: sharing-snips
description: >-
  Provides a workflow and script to capture screenshots, automatically upload
  them to a Google Cloud Storage bucket using the Python client library, and
  copy the public URL to the macOS clipboard. Use when needing to securely and
  quickly share visual snippets in chats or documents. Don't use for general
  file uploads or for non-macOS environments.
---

# Sharing Snips

This skill helps you capture screen snips and instantly share them using
Google Cloud Storage (GCS). It replaces `gcloud`-dependent CLI bash scripts
by utilizing the fundamental GCP Python Client library (`google-cloud-storage`).

## Prerequisites

1. **Google Cloud Storage Bucket**: You need a previously created GCS bucket
    (e.g., `makz-snips`), configured with `roles/storage.objectViewer` provided
    to `allUsers` for public fetching.
2. **Authentication**: Handled automatically if Application Default Credentials
    (ADC) are configured. Run `gcloud auth application-default login` if
    necessary.
3. **Dependencies**: The Python environment must include the
    `google-cloud-storage` package (managed automatically via `uv run` in the script).

## One-Time Bucket Setup

If you have not already created and configured your `makz-snips` GCP bucket,
use the provided setup script. It utilizes your GCP Free Storage Tier
(5 GB of standard storage for free).

```bash
bash scripts/setup.sh
```

This script will:

* Create the `makz-snips` bucket in `us-central1`.
* Make the bucket publicly readable so your snippet URLs work anywhere.
* Add an auto-delete lifecycle rule to permanently delete snippets older than
  90 days, guaranteeing you stay within the free tier.

## Execution

Invoke the command-line application directly from your shell or terminal. It is
safe to alias this command in your `~/.bashrc` or `~/.zshrc`:

```bash
uv run /Users/makz/src/agent-skills/sharing-snips/scripts/snip.py
```

Optional arguments:

* `[file]`: Pass a local file path to skip the screenshot and upload the
  existing file directly (e.g., `uv run .../snip.py ~/Desktop/image.png`).
* `--usage`: Prints your current month's GCS upload tally against the Free
  Tier safety limits and aborts.

### Flow

1. The macOS `screencapture -i` utility enables interactive region selection
   (unless a file is provided).
2. The user selects a region (or presses Escape to cancel quietly).
3. The Python script securely fetches GCP parameters and verifies local quotas.
4. The file uploads to your dynamically named GCS bucket via the GCP Python API.
5. An authenticated `https://storage.cloud.google.com/...` URL is copied
   immediately to your macOS clipboard using `pbcopy`.
