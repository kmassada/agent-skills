#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-cloud-storage",
#     "google-cloud-monitoring",
# ]
# ///
"""Command-line utility to capture and upload screen snips to Google Cloud Storage."""

import argparse
import datetime
import os
import subprocess
import sys

import quota_guard  # type: ignore


def main():
    """Capture a screenshot (or use an existing file), upload to GCS, and copy URL."""
    parser = argparse.ArgumentParser(
        description="Upload images to GCS sharing-snips bucket."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Optional path to an existing image file (skips screencapture)",
    )
    parser.add_argument(
        "--usage",
        action="store_true",
        help="Display Free Tier quota status and expected costs",
    )
    args = parser.parse_args()

    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        bucket_name = f"makz-snips-{client.project}"
    except Exception as e:  # noqa: BLE001
        print(f"Error determining bucket name: {e}")
        sys.exit(1)

    if args.usage:
        quota_guard.display_cost_and_usage(
            bucket_name=bucket_name, project_id=client.project
        )
        sys.exit(0)

    # 🚨 Block upload immediately if we are past the safe quota limits
    quota_guard.enforce_free_tier()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.file:
        if not os.path.isfile(args.file):
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
        temp_file = args.file
        # Extract extension from provided file, defaulting to png if missing
        _, ext = os.path.splitext(args.file)
        if not ext:
            ext = ".png"
        filename = f"snip_{timestamp}{ext}"
    else:
        filename = f"snip_{timestamp}.png"
        temp_file = f"/tmp/{filename}"

        # 1. Interactive screen capture (drag crosshairs)
        try:
            subprocess.run(["screencapture", "-i", temp_file], check=True)
        except subprocess.CalledProcessError:
            print("Error: screencapture failed.")
            sys.exit(1)
        except FileNotFoundError:
            print("Error: screencapture utility not found. This script requires macOS.")
            sys.exit(1)

        # If user pressed Escape to cancel, exit quietly
        if not os.path.isfile(temp_file):
            sys.exit(0)

    # 2. Upload to GCS using the GCP Python API
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)

        blob.upload_from_filename(temp_file)
    except Exception as e:  # noqa: BLE001
        print(f"Error uploading to Google Cloud Storage: {e}")
        sys.exit(1)
    finally:
        # Clean up the temporary file only if we generated it
        if not args.file and os.path.exists(temp_file):
            os.remove(temp_file)

    # 3. Copy URL to macOS clipboard
    # Using storage.cloud.google.com instead of storage.googleapis.com
    # so that the browser utilizes your active Google login cookies for private buckets.
    url = f"https://storage.cloud.google.com/{bucket_name}/{filename}"

    try:
        ps = subprocess.Popen(("echo", "-n", url), stdout=subprocess.PIPE)
        subprocess.check_output(("pbcopy",), stdin=ps.stdout)
        ps.wait()
    except Exception as e:  # noqa: BLE001
        print(f"Error copying to clipboard: {e}")
        print(f"URL: {url}")
        sys.exit(1)

    print(f"Uploaded: {url}")
    print("Copied to clipboard!")


if __name__ == "__main__":
    main()
