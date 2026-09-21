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


def _load_bw_key_file() -> None:
    """Auto-loads ~/.local/bw_key.zsh into os.environ if present."""
    if "BWS_ACCESS_TOKEN" in os.environ:
        return
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


def resolve_from_pass(secret_name: str, prefix: str = "ai-agents") -> str | None:
    """Retrieves a secret from the standard Unix password manager (pass).

    Supports folder trees ('ai-agents/slack/bot_token', 'slack.bot_token',
    'slack/bot_token', or 'bot_token').

    Args:
        secret_name: Secret path, key name, or dot-path.
        prefix: Root folder prefix in password-store (default: 'ai-agents').

    Returns:
        Decrypted secret string if found, otherwise None.
    """
    if not shutil.which("pass"):
        return None

    candidates: list[str] = []
    clean_name = secret_name.replace(".", "/")

    if clean_name.startswith(f"{prefix}/"):
        candidates.append(clean_name)
    else:
        candidates.append(f"{prefix}/{clean_name}")
        candidates.append(clean_name)

    parent_key = None
    sub_key = None
    if "." in secret_name:
        parent_key, _, sub_key = secret_name.partition(".")

    for cand in candidates:
        try:
            res = subprocess.run(
                ["pass", "show", cand],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                lines = res.stdout.splitlines()
                if lines:
                    val = lines[0].strip()
                    if val.startswith("{") or "\n" in res.stdout:
                        try:
                            full_json = json.loads(res.stdout)
                            if isinstance(full_json, dict) and sub_key:
                                for k, v in full_json.items():
                                    if k.lower() == sub_key.lower():
                                        return str(v)
                        except json.JSONDecodeError:
                            pass
                    return val
        except (subprocess.SubprocessError, OSError):
            pass

    if parent_key and sub_key:
        parent_cand = f"{prefix}/{parent_key}"
        try:
            res = subprocess.run(
                ["pass", "show", parent_cand],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                try:
                    parsed = json.loads(res.stdout.strip())
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            if k.lower() == sub_key.lower():
                                return str(v)
                except json.JSONDecodeError:
                    pass
        except (subprocess.SubprocessError, OSError):
            pass

    return None


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
    _load_bw_key_file()

    # Support dot-notation (e.g., "gws_auth.client_id" or "slack_agents.bot_token")
    secret_key = secret_name
    field_path: list[str] = []

    if "." in secret_name and not item_name:
        parts = secret_name.split(".")
        secret_key = parts[0]
        field_path = parts[1:]
    elif item_name:
        secret_key = item_name
        field_path = [secret_name]

    # Check Bitwarden Secrets Manager (bws)
    if shutil.which("bws") and os.environ.get("BWS_ACCESS_TOKEN"):
        try:
            proj_id = os.environ.get("BWS_PROJECT_ID")
            list_cmd = ["bws", "secret", "list"] + ([proj_id] if proj_id else [])
            list_res = subprocess.run(
                list_cmd, capture_output=True, text=True, check=False
            )
            if list_res.returncode == 0 and list_res.stdout.strip():
                try:
                    parsed_output = json.loads(list_res.stdout)
                except json.JSONDecodeError:
                    parsed_output = []

                if isinstance(parsed_output, dict):
                    secrets_list = [parsed_output]
                elif isinstance(parsed_output, list):
                    secrets_list = [s for s in parsed_output if isinstance(s, dict)]
                else:
                    secrets_list = []

                # 1. Match secret by key name (case-insensitive)
                for sec in secrets_list:
                    if sec.get("key", "").lower() == secret_key.lower():
                        raw_val = str(sec.get("value", ""))
                        if field_path:
                            try:
                                curr = json.loads(raw_val)
                                for segment in field_path:
                                    if isinstance(curr, dict):
                                        matched = next(
                                            (
                                                v
                                                for k, v in curr.items()
                                                if k.lower() == segment.lower()
                                            ),
                                            None,
                                        )
                                        curr = matched
                                    else:
                                        curr = None
                                        break
                                if curr is not None:
                                    return str(curr)
                            except json.JSONDecodeError:
                                pass
                        else:
                            return raw_val

                # 2. If not found by secret key name, scan all JSON payloads for the field
                for sec in secrets_list:
                    sec_val = sec.get("value", "")
                    try:
                        val_json = json.loads(sec_val)
                        if isinstance(val_json, dict):
                            for k, v in val_json.items():
                                if k.lower() == secret_name.lower():
                                    return str(v)
                    except json.JSONDecodeError:
                        pass
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

    Supports dot-path notation for structured JSON payloads (e.g., 'gws_auth.client_id').

    Args:
        secret_name: The name of the secret in GCP Secret Manager (or dot-path).
        project_id: Optional GCP Project ID.

    Returns:
        Secret string if found, otherwise None.
    """
    if not shutil.which("gcloud"):
        return None

    secret_key = secret_name
    field_path: list[str] = []
    if "." in secret_name:
        parts = secret_name.split(".")
        secret_key = parts[0]
        field_path = parts[1:]

    cmd = [
        "gcloud",
        "secrets",
        "versions",
        "access",
        "latest",
        f"--secret={secret_key}",
    ]
    if project_id:
        cmd.append(f"--project={project_id}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            raw_val = res.stdout.strip()
            if field_path:
                try:
                    curr = json.loads(raw_val)
                    for segment in field_path:
                        if isinstance(curr, dict):
                            matched = next(
                                (
                                    v
                                    for k, v in curr.items()
                                    if k.lower() == segment.lower()
                                ),
                                None,
                            )
                            curr = matched
                        else:
                            curr = None
                            break
                    if curr is not None:
                        return str(curr)
                except json.JSONDecodeError:
                    pass
            else:
                return raw_val
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
    if provider == "pass":
        return resolve_from_pass(secret_name)
    if provider == "bitwarden":
        return resolve_from_bitwarden(secret_name, item_name=item_name)
    if provider == "gcp":
        return resolve_from_gcp(secret_name, project_id=project_id)
    if provider == "doppler":
        return resolve_from_doppler(secret_name, project=project_id)

    # 2. Automatic resolution hierarchy
    if secret_name in os.environ:
        return os.environ[secret_name]

    pass_val = resolve_from_pass(secret_name)
    if pass_val:
        return pass_val

    bw_val = resolve_from_bitwarden(secret_name, item_name=item_name)
    if bw_val:
        return bw_val

    gcp_val = resolve_from_gcp(secret_name, project_id=project_id)
    if gcp_val:
        return gcp_val

    dop_val = resolve_from_doppler(secret_name, project=project_id)
    if dop_val:
        return dop_val


# Known tool-specific environment variable aliases
KNOWN_ENV_ALIASES: Mapping[str, Sequence[str]] = {
    "GWS_CLIENT_ID": ("GOOGLE_WORKSPACE_CLI_CLIENT_ID",),
    "GWS_CLIENT_SECRET": ("GOOGLE_WORKSPACE_CLI_CLIENT_SECRET",),
    "GWS_PROJECT_ID": ("GOOGLE_WORKSPACE_PROJECT_ID",),
}


def normalize_service_name(name: str) -> str:
    """Strips common secret naming suffixes to produce clean service directory names.

    E.g. 'slack_agents' -> 'slack', 'gws_auth' -> 'gws', 'stripe_creds' -> 'stripe'.
    """
    clean = name.lower()
    for suffix in ("_agents", "_auth", "_creds", "_secrets", "_keys", "_token"):
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]
            break
    return clean


def resolve_all_secrets(
    provider: str = "pass",
    prefix: str = "ai-agents",
    project_id: str | None = None,
) -> Mapping[str, str]:
    """Resolves and flattens all secrets from a vault into environment variables.

    Args:
        provider: Target vault provider ('pass', 'bitwarden', 'gcp', 'doppler').
        prefix: Path prefix for pass store (default: 'ai-agents').
        project_id: Optional project identifier.

    Returns:
        Mapping of environment variable names to secret values.
    """
    injected: dict[str, str] = {}
    if provider == "pass":
        if not shutil.which("pass"):
            return injected
        store_dir = os.path.expanduser("~/.password-store")
        target_root = os.path.join(store_dir, prefix)
        if not os.path.exists(target_root):
            target_root = store_dir

        if os.path.exists(target_root):
            for root, _, files in os.walk(target_root):
                for file in files:
                    if file.endswith(".gpg") and not file.startswith("."):
                        rel_dir = os.path.relpath(root, store_dir)
                        base_name = file[:-4]
                        if rel_dir == ".":
                            entry_path = base_name
                        else:
                            entry_path = f"{rel_dir}/{base_name}"

                        res = subprocess.run(
                            ["pass", "show", entry_path],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if res.returncode == 0 and res.stdout.strip():
                            val = res.stdout.strip().splitlines()[0]
                            clean_rel = entry_path
                            if clean_rel.startswith(f"{prefix}/"):
                                clean_rel = clean_rel[len(prefix) + 1 :]

                            parts = clean_rel.split("/")
                            var_name = clean_rel.replace("/", "_").upper()
                            injected[var_name] = val

                            if len(parts) >= 2:
                                service = parts[0].upper()
                                field = "_".join(parts[1:]).upper()
                                standard_key = f"{service}_{field}"
                                injected[standard_key] = val

                                for alias in KNOWN_ENV_ALIASES.get(standard_key, ()):
                                    injected[alias] = val
        return injected

    if provider == "bitwarden":
        _load_bw_key_file()
        if not shutil.which("bws") or not os.environ.get("BWS_ACCESS_TOKEN"):
            return injected
        proj = project_id or os.environ.get("BWS_PROJECT_ID")
        if not proj:
            return injected

        list_res = subprocess.run(
            ["bws", "secret", "list", proj],
            capture_output=True,
            text=True,
            check=False,
        )
        if list_res.returncode != 0 or not list_res.stdout.strip():
            return injected

        try:
            secrets_list = json.loads(list_res.stdout)
            if not isinstance(secrets_list, list):
                return injected
            for s in secrets_list:
                if not isinstance(s, dict) or "id" not in s:
                    continue
                sec_id = s["id"]
                sec_key = s.get("key", "")
                get_res = subprocess.run(
                    ["bws", "secret", "get", sec_id],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if get_res.returncode == 0 and get_res.stdout.strip():
                    item_data = json.loads(get_res.stdout)
                    val = item_data.get("value", "")
                    if not val:
                        continue
                    try:
                        parsed_json = json.loads(val)
                        if isinstance(parsed_json, dict):
                            # Map standard integrations to well-known env vars
                            service = parsed_json.get("service", "").lower()
                            if service == "slack" or "bot_token" in parsed_json:
                                if "bot_token" in parsed_json:
                                    injected["SLACK_BOT_TOKEN"] = str(
                                        parsed_json["bot_token"]
                                    )
                                if "team_id" in parsed_json:
                                    injected["SLACK_TEAM_ID"] = str(
                                        parsed_json["team_id"]
                                    )
                            elif (
                                service == "google_workspace"
                                or "client_secret" in parsed_json
                            ):
                                if "project_id" in parsed_json:
                                    injected["GOOGLE_WORKSPACE_PROJECT_ID"] = str(
                                        parsed_json["project_id"]
                                    )
                                if "client_id" in parsed_json:
                                    injected["GOOGLE_WORKSPACE_CLI_CLIENT_ID"] = str(
                                        parsed_json["client_id"]
                                    )
                                if "client_secret" in parsed_json:
                                    injected["GOOGLE_WORKSPACE_CLI_CLIENT_SECRET"] = (
                                        str(parsed_json["client_secret"])
                                    )

                            # General prefix exports
                            prefix = f"{sec_key.upper()}_"
                            for k, v in parsed_json.items():
                                injected[f"{prefix}{k.upper()}"] = str(v)
                                if k.upper() not in injected:
                                    injected[k.upper()] = str(v)
                        else:
                            injected[sec_key.upper()] = str(val)
                    except json.JSONDecodeError:
                        injected[sec_key.upper()] = str(val)
        except json.JSONDecodeError:
            pass

    return injected


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


def save_to_pass(
    secret_name: str,
    value: str | None = None,
    from_file: str | None = None,
    delete_after: bool = False,
    prefix: str = "ai-agents",
) -> bool:
    """Saves a secret or structured payload to the password store (pass).

    Args:
        secret_name: Target path or service name (e.g. 'slack/bot_token' or 'gws').
        value: Plaintext secret value or JSON string.
        from_file: Optional file path to ingest.
        delete_after: If True, deletes source file upon successful save.
        prefix: Password store folder prefix.

    Returns:
        True if successfully saved, False otherwise.
    """
    if not shutil.which("pass"):
        print("Error: 'pass' CLI executable not found.", file=sys.stderr)
        return False

    entries_to_write: dict[str, str] = {}

    if from_file:
        resolved_path = os.path.expanduser(from_file)
        if not os.path.exists(resolved_path):
            print(f"Error: File not found: {from_file}", file=sys.stderr)
            return False
        try:
            with open(resolved_path, encoding="utf-8") as f:
                content = f.read()

            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    wrapper = parsed.get("installed") or parsed.get("web")
                    if isinstance(wrapper, dict):
                        parsed = wrapper

                    clean_base = secret_name.replace(".", "/")
                    if not clean_base.startswith(f"{prefix}/"):
                        clean_base = f"{prefix}/{clean_base}"

                    for k, v in parsed.items():
                        entries_to_write[f"{clean_base}/{k.lower()}"] = str(v)
                else:
                    target_path = secret_name.replace(".", "/")
                    if not target_path.startswith(f"{prefix}/"):
                        target_path = f"{prefix}/{target_path}"
                    entries_to_write[target_path] = content.strip()
            except json.JSONDecodeError:
                clean_base = secret_name.replace(".", "/")
                if not clean_base.startswith(f"{prefix}/"):
                    clean_base = f"{prefix}/{clean_base}"
                has_env_lines = False
                for line in content.splitlines():
                    clean_line = line.strip()
                    if (
                        clean_line
                        and not clean_line.startswith("#")
                        and "=" in clean_line
                    ):
                        if clean_line.startswith("export "):
                            clean_line = clean_line[7:].strip()
                        k, _, v = clean_line.partition("=")
                        entries_to_write[f"{clean_base}/{k.strip().lower()}"] = (
                            v.strip().strip("'\"")
                        )
                        has_env_lines = True
                if not has_env_lines:
                    entries_to_write[clean_base] = content.strip()

        except OSError as e:
            print(f"Error reading file {from_file}: {e}", file=sys.stderr)
            return False
    elif value is not None:
        clean_base = secret_name.replace(".", "/")
        if not clean_base.startswith(f"{prefix}/"):
            clean_base = f"{prefix}/{clean_base}"
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    entries_to_write[f"{clean_base}/{k.lower()}"] = str(v)
            else:
                entries_to_write[clean_base] = value
        except json.JSONDecodeError:
            entries_to_write[clean_base] = value
    else:
        print(
            "Error: Either value or --from-file must be provided.",
            file=sys.stderr,
        )
        return False

    success = True
    for path, val in entries_to_write.items():
        proc = subprocess.run(
            ["pass", "insert", "-m", "-f", path],
            input=val,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            print(
                f"Error saving '{path}' to pass: {proc.stderr}",
                file=sys.stderr,
            )
            success = False

    if success and from_file and delete_after:
        resolved_path = os.path.expanduser(from_file)
        try:
            os.remove(resolved_path)
        except OSError:
            pass

    return success


def save_secret(
    secret_name: str,
    value: str | None = None,
    provider: str = "pass",
    project_id: str | None = None,
    note: str | None = None,
    from_file: str | None = None,
    delete_after: bool = False,
    prefix: str = "ai-agents",
) -> bool:
    """Saves or updates a secret across vaults with structured JSON support.

    Supports dot-path updates (e.g. 'slack_agents.bot_token'), local file
    ingestion (OAuth client JSON, .env), and automatic post-ingestion purging.

    Args:
        secret_name: Name of the secret or dot-path.
        value: Plaintext or JSON value to store.
        provider: Target vault provider ('pass', 'bitwarden', 'gcp', 'doppler').
        project_id: Optional project UUID or project name.
        note: Optional note / description for the secret.
        from_file: Optional file path to ingest secret data from.
        delete_after: Whether to delete the source file after ingestion.
        prefix: Pass store prefix (default: 'ai-agents').

    Returns:
        True if successfully saved, otherwise False.
    """
    if provider == "pass":
        return save_to_pass(
            secret_name,
            value=value,
            from_file=from_file,
            delete_after=delete_after,
            prefix=prefix,
        )

    if from_file:
        resolved_path = os.path.expanduser(from_file)
        if not os.path.exists(resolved_path):
            print(f"Error: File not found: {from_file}", file=sys.stderr)
            return False
        try:
            with open(resolved_path, encoding="utf-8") as f:
                content = f.read().strip()
            # Try JSON parsing
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    wrapper = parsed.get("installed") or parsed.get("web")
                    if isinstance(wrapper, dict):
                        data = {
                            "service": "google_workspace",
                            "project_id": wrapper.get("project_id", ""),
                            "client_id": wrapper.get("client_id", ""),
                            "client_secret": wrapper.get("client_secret", ""),
                            "owner": os.environ.get("USER", "kmassada"),
                            "environment": "dev",
                        }
                        value = json.dumps(data, indent=2)
                    else:
                        value = json.dumps(parsed, indent=2)
                else:
                    value = content
            except json.JSONDecodeError:
                # Parse .env / .zsh key=value lines
                parsed_env: dict[str, str] = {}
                for line in content.splitlines():
                    clean_line = line.strip()
                    if clean_line.startswith("export "):
                        clean_line = clean_line[7:].strip()
                    if "=" in clean_line:
                        k, _, v = clean_line.partition("=")
                        parsed_env[k.strip()] = v.strip().strip("'\"")
                if parsed_env:
                    value = json.dumps(parsed_env, indent=2)
                else:
                    value = content

            if delete_after:
                try:
                    os.remove(resolved_path)
                except OSError as exc:
                    print(
                        f"Warning: Could not delete {from_file}: {exc}",
                        file=sys.stderr,
                    )
        except OSError as exc:
            print(f"Error reading file {from_file}: {exc}", file=sys.stderr)
            return False

    if value is None:
        print(
            "Error: No value provided (provide value argument or --from-file).",
            file=sys.stderr,
        )
        return False

    # Handle dot-path updates (e.g., "slack_agents.bot_token")
    if "." in secret_name:
        parts = secret_name.split(".", 1)
        secret_key = parts[0]
        field_name = parts[1]

        existing_val = resolve_secret(
            secret_key, provider=provider, project_id=project_id
        )
        if existing_val:
            try:
                existing_dict = json.loads(existing_val)
                if isinstance(existing_dict, dict):
                    existing_dict[field_name] = value
                    value = json.dumps(existing_dict, indent=2)
                else:
                    value = json.dumps({field_name: value}, indent=2)
            except json.JSONDecodeError:
                value = json.dumps({field_name: value}, indent=2)
        else:
            value = json.dumps({field_name: value}, indent=2)
        target_key = secret_key
    else:
        target_key = secret_name

    if provider == "bitwarden":
        if not shutil.which("bws"):
            print("Error: bws CLI is not installed.", file=sys.stderr)
            return False
        _load_bw_key_file()
        if not os.environ.get("BWS_ACCESS_TOKEN"):
            print("Error: BWS_ACCESS_TOKEN not set.", file=sys.stderr)
            return False

        proj = project_id or os.environ.get("BWS_PROJECT_ID")
        if not proj:
            print("Error: BWS_PROJECT_ID not set.", file=sys.stderr)
            return False

        list_res = subprocess.run(
            ["bws", "secret", "list", proj],
            capture_output=True,
            text=True,
            check=False,
        )
        existing_id = None
        if list_res.returncode == 0 and list_res.stdout.strip():
            try:
                secrets_list = json.loads(list_res.stdout)
                if isinstance(secrets_list, list):
                    for s in secrets_list:
                        if (
                            isinstance(s, dict)
                            and s.get("key", "").lower() == target_key.lower()
                        ):
                            existing_id = s.get("id")
                            break
            except json.JSONDecodeError:
                pass

        if existing_id:
            cmd = ["bws", "secret", "edit", existing_id, "--value", value]
            if note:
                cmd.extend(["--note", note])
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode == 0
        else:
            cmd = ["bws", "secret", "create", target_key, value, proj]
            if note:
                cmd.extend(["--note", note])
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode == 0

    if provider == "gcp":
        if not shutil.which("gcloud"):
            print("Error: gcloud CLI is not installed.", file=sys.stderr)
            return False
        desc_cmd = ["gcloud", "secrets", "describe", target_key]
        if project_id:
            desc_cmd.append(f"--project={project_id}")
        desc_res = subprocess.run(desc_cmd, capture_output=True, text=True, check=False)
        if desc_res.returncode != 0:
            create_cmd = [
                "gcloud",
                "secrets",
                "create",
                target_key,
                "--replication-policy=automatic",
            ]
            if project_id:
                create_cmd.append(f"--project={project_id}")
            create_res = subprocess.run(
                create_cmd, capture_output=True, text=True, check=False
            )
            if create_res.returncode != 0:
                return False
        add_cmd = ["gcloud", "secrets", "versions", "add", target_key, "--data-file=-"]
        if project_id:
            add_cmd.append(f"--project={project_id}")
        add_res = subprocess.run(
            add_cmd, input=value, text=True, capture_output=True, check=False
        )
        return add_res.returncode == 0

    if provider == "doppler":
        if not shutil.which("doppler"):
            print("Error: doppler CLI is not installed.", file=sys.stderr)
            return False

        # If value is JSON dict, unpack all fields into Doppler
        secrets_to_set: dict[str, str] = {}
        try:
            val_json = json.loads(value)
            if isinstance(val_json, dict):
                for k, v in val_json.items():
                    secrets_to_set[f"{target_key.upper()}_{k.upper()}"] = str(v)
            else:
                secrets_to_set[target_key] = value
        except json.JSONDecodeError:
            secrets_to_set[target_key] = value

        return sync_to_doppler(secrets_to_set, project=project_id)

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


def list_secrets(
    provider: str = "pass",
    prefix: str = "ai-agents",
    project_id: str | None = None,
) -> int:
    """Safely lists secrets metadata without revealing secret values."""
    if provider == "pass":
        if not shutil.which("pass"):
            print("Error: 'pass' CLI executable not found.", file=sys.stderr)
            return 1
        print(f"Password Store Tree ({prefix}):")
        proc = subprocess.run(["pass", "ls", prefix], check=False)
        return proc.returncode

    if provider == "bitwarden":
        _load_bw_key_file()
        if not shutil.which("bws") or not os.environ.get("BWS_ACCESS_TOKEN"):
            print(
                "Error: BWS_ACCESS_TOKEN not set or bws CLI missing.",
                file=sys.stderr,
            )
            return 1
        proj = project_id or os.environ.get("BWS_PROJECT_ID")
        if not proj:
            print("Error: BWS_PROJECT_ID not set.", file=sys.stderr)
            return 1
        res = subprocess.run(
            ["bws", "secret", "list", proj],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            try:
                items = json.loads(res.stdout)
                if isinstance(items, list):
                    print("Bitwarden Secrets (Metadata only):")
                    for it in items:
                        if isinstance(it, dict):
                            print(f"  * {it.get('key')} (ID: {it.get('id')})")
                    return 0
            except json.JSONDecodeError:
                pass
        return 1

    print(
        f"List command not supported for provider '{provider}'.",
        file=sys.stderr,
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for get_credential."""
    parser = argparse.ArgumentParser(
        description="Multi-backend credential resolver and runtime injector."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # set subcommand
    set_parser = subparsers.add_parser("set", help="Save or update a secret in a vault")
    set_parser.add_argument("secret_name", help="Name of the secret or dot-path")
    set_parser.add_argument(
        "value", nargs="?", default=None, help="Secret value or JSON payload"
    )
    set_parser.add_argument(
        "--provider",
        choices=["pass", "bitwarden", "gcp", "doppler"],
        default="pass",
        help="Target vault provider (default: pass)",
    )
    set_parser.add_argument("--project", help="Project ID or UUID")
    set_parser.add_argument("--prefix", default="ai-agents", help="Pass store prefix")
    set_parser.add_argument("--note", help="Optional description/note for secret")
    set_parser.add_argument("--from-file", help="Ingest secret from JSON or .env file")
    set_parser.add_argument(
        "--delete-after",
        action="store_true",
        help="Securely delete source file after ingestion",
    )

    # get subcommand
    get_parser = subparsers.add_parser("get", help="Retrieve a secret")
    get_parser.add_argument("secret_name", help="Name of the secret key")
    get_parser.add_argument(
        "--provider",
        choices=["pass", "bitwarden", "gcp", "doppler", "env"],
        help="Explicit secret provider",
    )
    get_parser.add_argument("--project", help="GCP or Doppler Project ID")
    get_parser.add_argument("--prefix", default="ai-agents", help="Pass store prefix")
    get_parser.add_argument("--item", help="Bitwarden item name")
    get_parser.add_argument(
        "--format",
        choices=["plain", "json", "export"],
        default="plain",
        help="Output format",
    )

    # list subcommand
    list_parser = subparsers.add_parser(
        "list", help="Safely list secret names without revealing secret values"
    )
    list_parser.add_argument(
        "--provider",
        choices=["pass", "bitwarden", "gcp"],
        default="pass",
        help="Secret provider to inspect (default: pass)",
    )
    list_parser.add_argument("--prefix", default="ai-agents", help="Pass store prefix")
    list_parser.add_argument("--project", help="Project ID or UUID")

    # run subcommand
    run_parser = subparsers.add_parser(
        "run", help="Run a command with injected secrets"
    )
    run_parser.add_argument(
        "--keys",
        help="Optional comma-separated secret keys (default: all project secrets)",
    )
    run_parser.add_argument(
        "--provider",
        choices=["pass", "bitwarden", "gcp", "doppler", "env"],
        help="Explicit secret provider",
    )
    run_parser.add_argument("--prefix", default="ai-agents", help="Pass store prefix")
    run_parser.add_argument("--project", help="GCP or Doppler Project ID")
    run_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run")

    # sync subcommand
    sync_parser = subparsers.add_parser(
        "sync", help="Sync upstream secrets into pass or Doppler"
    )
    sync_parser.add_argument(
        "--keys",
        help="Optional comma-separated list of keys (defaults to all project secrets)",
    )
    sync_parser.add_argument(
        "--upstream",
        required=True,
        choices=["bitwarden", "gcp"],
        help="Upstream source vault",
    )
    sync_parser.add_argument(
        "--dest",
        choices=["pass", "doppler"],
        default="pass",
        help="Destination vault to populate (default: pass)",
    )
    sync_parser.add_argument("--prefix", default="ai-agents", help="Pass store prefix")
    sync_parser.add_argument("--project", help="GCP or Doppler Project ID")

    args = parser.parse_args(argv)

    if args.command == "list":
        return list_secrets(
            provider=args.provider,
            prefix=args.prefix,
            project_id=args.project,
        )

    if args.command == "set":
        ok = save_secret(
            args.secret_name,
            value=args.value,
            provider=args.provider,
            project_id=args.project,
            note=args.note,
            from_file=args.from_file,
            delete_after=args.delete_after,
            prefix=args.prefix,
        )
        if ok:
            print(f"Successfully saved secret '{args.secret_name}' to {args.provider}.")
            return 0
        print(
            f"Error: Failed to save secret '{args.secret_name}' to {args.provider}.",
            file=sys.stderr,
        )
        return 1

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

        chosen_provider = args.provider
        if not chosen_provider:
            # Auto-detect: if password-store has entries, use pass; else bitwarden
            pass_dir = os.path.expanduser("~/.password-store")
            if os.path.exists(os.path.join(pass_dir, args.prefix)):
                chosen_provider = "pass"
            else:
                chosen_provider = "bitwarden"

        if args.keys:
            keys = [k.strip() for k in args.keys.split(",") if k.strip()]
            resolved: dict[str, str] = {}
            for key in keys:
                target_var = key
                source_key = key
                if ":" in key:
                    target_var, _, source_key = key.partition(":")
                val = resolve_secret(
                    source_key,
                    provider=chosen_provider,
                    project_id=args.project,
                )
                if val is not None:
                    resolved[target_var] = val
                else:
                    print(
                        f"Warning: Could not resolve '{source_key}'.",
                        file=sys.stderr,
                    )
        else:
            resolved = dict(
                resolve_all_secrets(
                    provider=chosen_provider,
                    prefix=args.prefix,
                    project_id=args.project,
                )
            )

        return run_command_with_injected_secrets(target_cmd, resolved)

    if args.command == "sync":
        if args.keys:
            keys = [k.strip() for k in args.keys.split(",") if k.strip()]
        elif args.upstream == "bitwarden":
            _load_bw_key_file()
            proj = args.project or os.environ.get("BWS_PROJECT_ID")
            if not proj:
                print(
                    "Error: BWS_PROJECT_ID required to auto-discover keys.",
                    file=sys.stderr,
                )
                return 1
            res = subprocess.run(
                ["bws", "secret", "list", proj],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                print(
                    "Error: Failed to list secrets from Bitwarden.",
                    file=sys.stderr,
                )
                return 1
            items = json.loads(res.stdout)
            keys = [it["key"] for it in items if "key" in it]
        else:
            print(
                "Error: --keys is required for the specified upstream provider.",
                file=sys.stderr,
            )
            return 1

        doppler_payload: dict[str, str] = {}
        for key in keys:
            target_var = key
            source_key = key
            if ":" in key:
                target_var, _, source_key = key.partition(":")
            val = resolve_secret(
                source_key, provider=args.upstream, project_id=args.project
            )
            if val is None:
                print(
                    f"Error: Upstream '{args.upstream}' failed to resolve "
                    f"'{source_key}'.",
                    file=sys.stderr,
                )
                return 1

            val_dict: dict[str, str] | None = None
            if ":" not in key and "." not in key:
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        wrapper = parsed.get("installed") or parsed.get("web")
                        if isinstance(wrapper, dict):
                            parsed = wrapper
                        val_dict = {str(k): str(v) for k, v in parsed.items()}
                except json.JSONDecodeError:
                    pass

            if args.dest == "pass":
                if val_dict is not None:
                    service_folder = normalize_service_name(source_key)
                    for sub_k, sub_v in val_dict.items():
                        save_to_pass(
                            f"{service_folder}/{sub_k.lower()}",
                            value=sub_v,
                            prefix=args.prefix,
                        )
                else:
                    save_to_pass(target_var.lower(), value=val, prefix=args.prefix)
            elif args.dest == "doppler":
                if val_dict is not None:
                    prefix_name = f"{source_key.upper()}_"
                    for sub_k, sub_v in val_dict.items():
                        doppler_payload[f"{prefix_name}{sub_k.upper()}"] = sub_v
                else:
                    doppler_payload[target_var] = val

        if args.dest == "doppler" and doppler_payload:
            sync_to_doppler(doppler_payload, project=args.project)

        print(f"Successfully synced secrets from {args.upstream} into {args.dest}.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
