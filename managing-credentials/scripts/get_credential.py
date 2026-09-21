#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Multi-backend credential resolver and runtime injector.

Resolves credentials across upstream vaults (Bitwarden, Google Cloud Secret
Manager, Doppler) and injects them directly into memory for agents and tools
without writing unencrypted plaintext files to disk.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence


class CredentialError(Exception):
    """Base exception for credential retrieval failures."""


def resolve_from_bitwarden(
    secret_name: str, item_name: str | None = None
) -> str | None:
    """Retrieves a secret from Bitwarden CLI (bw) or Bitwarden Secrets Manager (bws).

    Args:
        secret_name: The key/field or secret name to fetch.
        item_name: Optional vault item name (defaults to secret_name or service).

    Returns:
        Secret string if found, otherwise None.
    """
    target = item_name or secret_name

    # Auto-load ~/.local/bw_key.zsh if BWS_ACCESS_TOKEN not in env
    if "BWS_ACCESS_TOKEN" not in os.environ:
        bw_key_file = os.path.expanduser("~/.local/bw_key.zsh")
        if os.path.exists(bw_key_file):
            try:
                with open(bw_key_file, encoding="utf-8") as f:
                    for raw_line in f:
                        clean_line = raw_line.strip()
                        if clean_line.startswith("export "):
                            clean_line = clean_line[7:].strip()
                        if "=" in clean_line:
                            k, _, v = clean_line.partition("=")
                            os.environ[k.strip()] = v.strip().strip("'\"")
            except OSError:
                pass

    # Check Bitwarden Secrets Manager (bws)
    if shutil.which("bws") and os.environ.get("BWS_ACCESS_TOKEN"):
        try:
            # 1. Try direct secret get
            res = subprocess.run(
                ["bws", "secret", "get", target],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                val_raw = str(data.get("value", ""))
                try:
                    val_json = json.loads(val_raw)
                    if isinstance(val_json, dict):
                        for k, v in val_json.items():
                            if k.upper() in (
                                secret_name.upper(),
                                secret_name.upper().replace("SLACK_", "").lower(),
                            ):
                                return str(v)
                except json.JSONDecodeError:
                    return val_raw

            # 2. Check candidate service secrets if target is a subfield
            candidates = [target]
            if "SLACK" in secret_name.upper():
                candidates.extend(["slack_agents", "slack"])
            if any(k in secret_name.upper() for k in ("WORKSPACE", "GWS", "GOOGLE")):
                candidates.extend(["gws_auth", "google_workspace", "gws"])
            if item_name:
                candidates.insert(0, item_name)

            proj_id = os.environ.get("BWS_PROJECT_ID")
            list_cmd = ["bws", "secret", "list"] + ([proj_id] if proj_id else [])
            list_res = subprocess.run(
                list_cmd, capture_output=True, text=True, check=False
            )
            if list_res.returncode == 0 and list_res.stdout.strip():
                secrets_list = json.loads(list_res.stdout)
                for sec in secrets_list:
                    sec_key = sec.get("key", "").lower()
                    if any(cand.lower() == sec_key for cand in candidates):
                        sec_val = sec.get("value", "")
                        try:
                            val_json = json.loads(sec_val)
                            if isinstance(val_json, dict):
                                # Check exact or normalized keys
                                clean_name = (
                                    secret_name.lower()
                                    .replace("slack_", "")
                                    .replace("google_workspace_", "")
                                    .replace("cli_", "")
                                )
                                norm_keys = [
                                    secret_name.upper(),
                                    secret_name.lower(),
                                    clean_name.upper(),
                                    clean_name.lower(),
                                ]
                                for k, v in val_json.items():
                                    if k.upper() in norm_keys or k.lower() in norm_keys:
                                        return str(v)
                        except json.JSONDecodeError:
                            if sec_key == secret_name.lower():
                                return str(sec_val)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass

    # Check standard Bitwarden CLI (bw)
    if shutil.which("bw"):
        try:
            # 1. Try bw get password/notes directly
            res = subprocess.run(
                ["bw", "get", "password", target],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()

            # 2. Try raw item JSON
            res_item = subprocess.run(
                ["bw", "get", "item", target, "--raw"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res_item.returncode == 0 and res_item.stdout.strip():
                data = json.loads(res_item.stdout)
                # Check login password
                login = data.get("login", {})
                if login.get("password") and target == secret_name:
                    return str(login["password"])

                # Check custom fields
                for field in data.get("fields", []):
                    if field.get("name", "").upper() == secret_name.upper():
                        return str(field.get("value", ""))

                # Check notes (JSON, KEY=VALUE pairs, or raw string)
                notes = data.get("notes")
                if notes:
                    notes_str = str(notes).strip()
                    # A. Check if notes is valid JSON
                    try:
                        notes_json = json.loads(notes_str)
                        if isinstance(notes_json, dict):
                            for k, v in notes_json.items():
                                if k.upper() == secret_name.upper():
                                    return str(v)
                    except json.JSONDecodeError:
                        pass

                    # B. Check if notes has KEY=VALUE or export KEY=VALUE lines
                    for line in notes_str.splitlines():
                        clean_line = line.strip()
                        if clean_line.startswith("export "):
                            clean_line = clean_line[7:].strip()
                        if "=" in clean_line:
                            k, _, v = clean_line.partition("=")
                            if k.strip().upper() == secret_name.upper():
                                return v.strip().strip("'\"")

                    # C. If item name was exact secret name, return raw notes
                    if target == secret_name:
                        return notes_str
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass

    return None


def resolve_from_gcp(secret_name: str, project_id: str | None = None) -> str | None:
    """Retrieves a secret from Google Cloud Secret Manager via gcloud CLI.

    Args:
        secret_name: The name of the secret in GCP Secret Manager.
        project_id: Optional GCP Project ID.

    Returns:
        Secret string if found, otherwise None.
    """
    if not shutil.which("gcloud"):
        return None

    cmd = [
        "gcloud",
        "secrets",
        "versions",
        "access",
        "latest",
        f"--secret={secret_name}",
    ]
    if project_id:
        cmd.append(f"--project={project_id}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass

    return None


def resolve_from_doppler(
    secret_name: str,
    project: str | None = None,
    config: str | None = None,
) -> str | None:
    """Retrieves a secret from Doppler CLI.

    Args:
        secret_name: The name of the secret key.
        project: Optional Doppler project.
        config: Optional Doppler config environment.

    Returns:
        Secret string if found, otherwise None.
    """
    if not shutil.which("doppler"):
        return None

    cmd = ["doppler", "secrets", "get", secret_name, "--plain"]
    if project:
        cmd.extend(["--project", project])
    if config:
        cmd.extend(["--config", config])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass

    return None


def resolve_secret(
    secret_name: str,
    provider: str | None = None,
    project_id: str | None = None,
    item_name: str | None = None,
) -> str | None:
    """Resolves a secret across available backends or an explicit provider.

    Hierarchy when provider is None:
        1. Process Environment ($VAR)
        2. Bitwarden (bw / bws)
        3. GCP Secret Manager (gcloud)
        4. Doppler CLI (doppler)

    Args:
        secret_name: Name of the credential/key.
        provider: Optional explicit provider ('bitwarden', 'gcp', 'doppler', 'env').
        project_id: Optional project identifier for GCP or Doppler.
        item_name: Optional item name for Bitwarden.

    Returns:
        Resolved secret value or None.
    """
    # 1. Explicit provider routing
    if provider == "env":
        return os.environ.get(secret_name)
    if provider == "bitwarden":
        return resolve_from_bitwarden(secret_name, item_name=item_name)
    if provider == "gcp":
        return resolve_from_gcp(secret_name, project_id=project_id)
    if provider == "doppler":
        return resolve_from_doppler(secret_name, project=project_id)

    # 2. Automatic resolution hierarchy
    if secret_name in os.environ:
        return os.environ[secret_name]

    bw_val = resolve_from_bitwarden(secret_name, item_name=item_name)
    if bw_val:
        return bw_val

    gcp_val = resolve_from_gcp(secret_name, project_id=project_id)
    if gcp_val:
        return gcp_val

    dop_val = resolve_from_doppler(secret_name, project=project_id)
    if dop_val:
        return dop_val

    return None


def sync_to_doppler(
    secrets: Mapping[str, str],
    project: str | None = None,
    config: str | None = None,
) -> bool:
    """Pushes a mapping of secrets into a local/remote Doppler project.

    Args:
        secrets: Mapping of key to secret string.
        project: Optional Doppler project name.
        config: Optional Doppler config name.

    Returns:
        True if successful, False otherwise.
    """
    if not shutil.which("doppler") or not secrets:
        return False

    cmd = ["doppler", "secrets", "set", "--silent"]
    if project:
        cmd.extend(["--project", project])
    if config:
        cmd.extend(["--config", config])

    for k, v in secrets.items():
        cmd.append(f"{k}={v}")

    try:
        res = subprocess.run(cmd, capture_output=True, check=False)
        return res.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def run_command_with_injected_secrets(
    cmd: Sequence[str], secrets: Mapping[str, str]
) -> int:
    """Executes a command with secrets injected into its process memory.

    Args:
        cmd: Command and arguments sequence.
        secrets: Secrets to inject into the process environment.

    Returns:
        Exit code of the executed command.
    """
    env = os.environ.copy()
    env.update(secrets)
    try:
        res = subprocess.run(list(cmd), env=env, check=False)
        return res.returncode
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"Error launching command: {exc}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for get_credential."""
    parser = argparse.ArgumentParser(
        description="Multi-backend credential resolver and runtime injector."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # get subcommand
    get_parser = subparsers.add_parser("get", help="Retrieve a secret")
    get_parser.add_argument("secret_name", help="Name of the secret key")
    get_parser.add_argument(
        "--provider",
        choices=["bitwarden", "gcp", "doppler", "env"],
        help="Explicit secret provider",
    )
    get_parser.add_argument("--project", help="GCP or Doppler Project ID")
    get_parser.add_argument("--item", help="Bitwarden item name")
    get_parser.add_argument(
        "--format",
        choices=["plain", "json", "export"],
        default="plain",
        help="Output format",
    )

    # run subcommand
    run_parser = subparsers.add_parser(
        "run", help="Run a command with injected secrets"
    )
    run_parser.add_argument(
        "--keys",
        required=True,
        help="Comma-separated list of secret keys to resolve",
    )
    run_parser.add_argument(
        "--provider",
        choices=["bitwarden", "gcp", "doppler", "env"],
        help="Explicit secret provider",
    )
    run_parser.add_argument("--project", help="GCP or Doppler Project ID")
    run_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run")

    # sync subcommand
    sync_parser = subparsers.add_parser(
        "sync", help="Sync upstream secrets into Doppler"
    )
    sync_parser.add_argument(
        "--keys",
        required=True,
        help="Comma-separated list of secret keys to fetch and sync",
    )
    sync_parser.add_argument(
        "--upstream",
        required=True,
        choices=["bitwarden", "gcp"],
        help="Upstream source vault",
    )
    sync_parser.add_argument("--project", help="GCP or Doppler Project ID")

    args = parser.parse_args(argv)

    if args.command == "get":
        val = resolve_secret(
            args.secret_name,
            provider=args.provider,
            project_id=args.project,
            item_name=args.item,
        )
        if val is None:
            print(
                f"Error: Secret '{args.secret_name}' could not be resolved.",
                file=sys.stderr,
            )
            return 1

        if args.format == "plain":
            print(val)
        elif args.format == "json":
            print(json.dumps({args.secret_name: val}))
        elif args.format == "export":
            print(f'export {args.secret_name}="{val}"')
        return 0

    if args.command == "run":
        target_cmd = args.cmd
        if target_cmd and target_cmd[0] == "--":
            target_cmd = target_cmd[1:]
        if not target_cmd:
            print("Error: No command specified to run.", file=sys.stderr)
            return 1

        keys = [k.strip() for k in args.keys.split(",") if k.strip()]
        resolved: dict[str, str] = {}
        for key in keys:
            val = resolve_secret(key, provider=args.provider, project_id=args.project)
            if val is not None:
                resolved[key] = val
            else:
                print(
                    f"Warning: Could not resolve '{key}'.",
                    file=sys.stderr,
                )

        return run_command_with_injected_secrets(target_cmd, resolved)

    if args.command == "sync":
        keys = [k.strip() for k in args.keys.split(",") if k.strip()]
        resolved: dict[str, str] = {}
        for key in keys:
            val = resolve_secret(key, provider=args.upstream, project_id=args.project)
            if val is not None:
                resolved[key] = val
            else:
                print(
                    f"Error: Upstream '{args.upstream}' failed to resolve '{key}'.",
                    file=sys.stderr,
                )
                return 1

        ok = sync_to_doppler(resolved, project=args.project)
        if ok:
            print(
                f"Successfully synced {len(resolved)} secrets from "
                f"{args.upstream} into Doppler."
            )
            return 0
        print("Failed to sync secrets into Doppler.", file=sys.stderr)
        return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
