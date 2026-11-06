# Git & GitHub Best Practices

These rules govern all Git and GitHub operations to maximize digital safety, security, and repository integrity without introducing friction to the developer experience.

## 1. Commit & Push Guardrails (Explicit Consent Required)
- **No Autonomous Commits or Pushes:** Never run `git commit`, `git push`, or `git tag` unless the user explicitly asks for it in the current turn.
- **Explicit Target Staging:** Never use blind staging commands like `git add .` or `git add -A`. Always stage specific files (`git add <file1> <file2>`) to prevent untracked artifacts, logs, or scratch files from being included.
- **Pre-Commit Inspection:** Always inspect `git status` and `git diff --staged` before finalizing a commit to verify staged changes.
- **No Unauthorized Force Pushes:** Never execute `git push --force` or `git push --force-with-lease` without explicit confirmation.
- **Branch Protection Awareness:** Avoid pushing directly to `main` without explicit approval; prefer feature/fix branches for significant updates.

## 2. Secrets & Sensitive Data Safety (Zero-Leak Policy)
- **Never Commit Secrets or Credentials:** Never stage `.env`, private keys (`.pem`, `.key`, `.p12`), API keys, access tokens, webhook secrets, or credentials.
- **Never Bypass `.gitignore`:** Do not run `git add -f` / `--force` on ignored files.
- **Data & Telemetry Privacy:** Never commit local databases (`.db`, `.sqlite`, `.db-wal`, `.db-shm`), data dumps, export files, or personal energy/meter data.
- **Immediate Alert on Accidental Exposure:** If a secret is staged, unstage it immediately (`git restore --staged <file>`) and alert the user. If previously pushed, recommend credential rotation immediately.

## 3. Non-Destructive Operations & History Integrity
- **Protect Uncommitted Work:** Never run destructive git commands (`git reset --hard`, `git clean -fd`, `git restore .`, `git checkout -- .`) without explicit user permission.
- **Preserve Published History:** Do not rebase or amend (`git commit --amend`) commits that have already been pushed to a remote branch unless specifically instructed.
- **Safe Stashing:** Before switching branches or pulling when unstaged changes exist, suggest or use `git stash push -m "<description>"`.

## 4. Developer Experience & Ergonomics (Low Friction)
- **Conventional & Meaningful Commits:** Propose clear, descriptive commit messages following standard conventions (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`) summarizing *why* rather than just *what*.
- **Ready-to-Review Summaries:** When asked to commit, provide a quick bullet summary of staged changes and the proposed commit message so the user can approve in one glance.
- **Keep Local Iteration Unhindered:** These safety boundaries apply to git staging, committing, and remote syncing. Local exploration, editing, test runs, and dev builds remain frictionless.
