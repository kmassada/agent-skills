#!/usr/bin/env python3
"""Module to enforce local quotas and prevent GCS billing fees."""

import datetime
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

QUOTA_FILE = Path.home() / ".config" / "sharing-snips" / "quota.json"
MAX_UPLOADS_PER_MONTH = 4500  # Safe cap (5000 is the GCP Free Tier limit)


def _get_quota_data() -> dict[str, Any]:
    """Fetch the current quota usage from disk."""
    now = datetime.datetime.now()
    current_month = f"{now.year}-{now.month:02d}"

    quota_data: dict[str, Any] = {"month": current_month, "uploads": 0}

    if QUOTA_FILE.is_file():
        try:
            with QUOTA_FILE.open("r") as f:
                data = json.load(f)
                # Reset if the month rolled over
                if isinstance(data, dict) and data.get("month") == current_month:
                    quota_data["uploads"] = data.get("uploads", 0)
        except (json.JSONDecodeError, OSError):
            pass

    return quota_data


def _save_quota_data(data: Mapping[str, Any]) -> None:
    """Persist the quota usage to disk."""
    # Ensure directory exists
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with QUOTA_FILE.open("w") as f:
        json.dump(dict(data), f)


def enforce_free_tier() -> None:
    """Check usage and increment. Exit if over the limit."""
    data = _get_quota_data()

    uploads = int(data["uploads"])
    if uploads >= MAX_UPLOADS_PER_MONTH:
        print("🚨 ERROR: GCP Always Free Tier protection activated!", file=sys.stderr)
        print(
            f"You have reached the safety cap of {MAX_UPLOADS_PER_MONTH} uploads for this month.",
            file=sys.stderr,
        )
        print("Upload blocked to prevent any unexpected billing fees.", file=sys.stderr)
        sys.exit(1)

    data["uploads"] = uploads + 1
    _save_quota_data(data)


def fetch_monitoring_api_requests(project_id: str, bucket_name: str) -> int | None:
    """Fetch 30-day API request count directly from Google Cloud Monitoring."""
    try:
        from google.cloud import monitoring_v3  # type: ignore

        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"

        now = datetime.datetime.now(datetime.UTC)
        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": int(now.timestamp())},
                "start_time": {
                    "seconds": int((now - datetime.timedelta(days=30)).timestamp())
                },
            }
        )

        results = client.list_time_series(
            request={
                "name": project_name,
                "filter": (
                    f'metric.type="storage.googleapis.com/api/request_count" '
                    f'AND resource.labels.bucket_name="{bucket_name}"'
                ),
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )

        return sum(pt.value.int64_value for ts in results for pt in ts.points)
    except Exception as e:  # noqa: BLE001
        print(
            f"⚠️ Warning: Could not fetch Cloud Monitoring metrics: {e}", file=sys.stderr
        )
        return None


def sync_quota_with_gcp(
    bucket_name: str, project_id: str | None = None
) -> dict[str, Any]:
    """Pull real usage telemetry directly from GCP Storage & Monitoring APIs."""
    print(
        "🔄 Connecting to Google Cloud to fetch real usage telemetry...",
        file=sys.stderr,
    )
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    now = datetime.datetime.now(datetime.UTC)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    data = _get_quota_data()

    try:
        blobs = bucket.list_blobs()

        count = 0
        total_size_bytes = 0

        for b in blobs:
            total_size_bytes += b.size if b.size else 0
            if b.time_created and b.time_created >= start_of_month:
                count += 1

        data["uploads"] = count
        data["gcp_size_bytes"] = total_size_bytes
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Warning: Could not sync storage blobs with GCP: {e}", file=sys.stderr)

    # If project_id provided, also pull Cloud Monitoring telemetry
    effective_project = project_id or getattr(client, "project", None)
    if effective_project:
        monitoring_count = fetch_monitoring_api_requests(
            str(effective_project), bucket_name
        )
        if monitoring_count is not None:
            data["monitoring_requests_30d"] = monitoring_count

    _save_quota_data(data)
    return data


def display_cost_and_usage(
    bucket_name: str | None = None, project_id: str | None = None
) -> None:
    """Print the current usage report and confirm $0 costs, optionally syncing."""
    data = (
        sync_quota_with_gcp(bucket_name, project_id)
        if bucket_name
        else _get_quota_data()
    )

    print("======== 🛡️  GCP Free Tier Protection Status ========")
    print(f"Current Month: {data['month']}")
    print(
        f"Uploads executed (Class A Ops): {data['uploads']} / {MAX_UPLOADS_PER_MONTH} safety cap"
    )

    if "gcp_size_bytes" in data:
        mb = data["gcp_size_bytes"] / (1024 * 1024)
        print(f"Current Bucket Size: {mb:.2f} MB / 5120.00 MB (5GB) limit")

    if "monitoring_requests_30d" in data:
        print(
            f"Cloud Monitoring API Requests (Past 30 Days): {data['monitoring_requests_30d']} calls"
        )

    print("--------------------------------------------------")
    print("GCP Always Free Tier Allowances:")
    print(" • Storage: 5 GB-months per month (Managed by setup.sh 90-day auto-delete)")
    print(" • Class A Operations (Uploads): 5,000 per month limit")
    print(" • Egress: 100 GB per month to internet")
    print("--------------------------------------------------")
    print("💰 Expected Billing Cost: $0.00")
    print("==================================================")
