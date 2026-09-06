---
trigger: model_decision
description: "Guidelines and safety protocols for interacting with Google Workspace (Gmail, Calendar, Drive, Docs) via the gws CLI"
---

# Google Workspace Tools (workspace-tools)

When interacting with Google Workspace services (Gmail, Calendar, Drive, Docs),
use the Google Workspace CLI (`gws`, Homebrew formula `googleworkspace-cli`).
Operate according to the following protocols, helper workflows, and safety
invariants:

## Core Domains

The CLI exposes dedicated subcommands for core Google Workspace domains:

* **Calendar (`gws calendar`)**: Manage events, query availability, and inspect
  schedules.
* **Gmail (`gws gmail`)**: Search threads, read messages, draft responses, and
  triage mailboxes.
* **Drive (`gws drive`)**: Search files, organize folder structures, upload
  assets, and manage permissions.
* **Docs (`gws docs`)**: Retrieve, create, and manipulate document content and
  revisions.

## Common Helper Workflows

Use high-level helper commands (`+<command>`) for streamlined operations:

* **Calendar**:
  * `gws calendar +agenda`: View upcoming meetings and schedule overviews.
  * `gws calendar +insert`: Schedule new calendar events.
* **Gmail**:
  * `gws gmail +triage`: List and triage unread or pending emails.
  * `gws gmail +read <id>`: Fetch and render full email thread contents.
  * `gws gmail +send`: Compose and dispatch new messages.
  * `gws gmail +reply`: Send contextual responses to existing threads.

## Safety Invariants & Execution Boundaries

Agents must respect strict boundaries between autonomous inspection and
user-confirmed mutation:

* **Autonomous Read Actions**: Non-destructive operations such as reading
  threads (`+triage`, `+read`), viewing schedules (`+agenda`), and querying
  metadata (`files list`) are safe to execute autonomously.
* **Mandatory Confirmation on Mutation**: External or mutating actions MUST
  prompt the user for explicit confirmation before execution. This includes
  sending emails (`+send`, `+reply`), creating, updating, or deleting calendar
  events, deleting files, and modifying sharing permissions.
* **Draft Verification**: Always present a complete draft or parameter preview
  to the user when requesting confirmation for any mutating action.
* **Structured Output & Dry Runs**: Prefer `--format json` for reliable agent
  consumption and programmatic parsing. Use `--dry-run` to preview API
  mutations safely without applying changes.

## References

* Companion skill: `gws-shared`
* Upstream repository: [`googleworkspace/cli`][gws-cli-repo]

[gws-cli-repo]: https://github.com/googleworkspace/cli
