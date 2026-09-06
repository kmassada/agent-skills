---
trigger: always_on
description: "Git version control hygiene, conventional commits, secret safety, and linear history"
---

# Git Version Control & Repository Hygiene

Whenever operating in Git repositories, adhere to these non-negotiable hygiene
and version control principles:

* **Atomic, Purposeful Commits**: Keep commits focused on a single logical change.
  Never combine unrelated refactoring, feature work, and formatting fixes into a
  single commit.
* **Conventional Commit Format**: Structure commit messages using conventional
  types:
  * `feat`: A new user-facing feature or capability.
  * `fix`: A bug fix or defect correction.
  * `docs`: Documentation updates or additions only.
  * `refactor`: Code changes that neither fix bugs nor add features.
  * `test`: Adding or correcting tests with no production code changes.
  * `chore`: Maintenance, dependency updates, or build tooling changes.
  Format the subject as `<type>(<scope>): <imperative summary>` (maximum 72
  characters, all lowercase subject, no trailing period).
* **Secret & Sensitive Data Hygiene**: NEVER stage or commit secrets, credentials,
  API tokens, private keys (`id_rsa`, `*.pem`), or `.env` files. Verify that
  transient or local files are listed in `.gitignore` before committing.
* **Pre-Commit Verification Gate**: Never commit broken code, failing tests, or
  unformatted files. Always inspect `git status` and review `git diff` before
  running `git commit`.
* **Linear, Clean History**: Rebase feature branches on the upstream main branch
  (`git pull --rebase`) to prevent noisy, unnecessary merge commits.
* **Safe Remote Invariants**: Never force-push (`--force`) to `main` or any shared
  branch. Always confirm with the user before publishing commits to remote
  repositories.
