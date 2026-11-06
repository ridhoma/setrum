# Project Guidelines for AI Agents

## Ports & Local Development
- **Port 8050 is RESERVED for Docker production deployment.**
  - The live, background Docker container runs on port 8050 (`http://localhost:8050` and LAN `http://<mac-name>.local:8050`).
  - Never bind or run local servers on port 8050.
- **Port 8051 is for local development:**
  - Running `uv run python run.py` automatically defaults to port 8051.
  - Test servers and manual probes should always use port 8051 or higher.

## Database & Data Persistence
- Application data lives in `~/.setrum/data/setrum.db`.
- The `data/` directory in the repository is a symlink pointing to `~/.setrum/data/`.
- Do not commit `.db`, `.db-shm`, or `.db-wal` files to git.

## Git & GitHub Best Practices
- **Do not commit or push without explicit user instruction:** Never run `git commit`, `git push`, or destructive operations (`git reset --hard`, `git clean -fd`) autonomously.
- **Stage explicitly:** Avoid `git add .` or `git add -A`; stage individual files explicitly.
- **Zero secrets & data leaks:** Never stage `.env`, credentials, secrets, or `.db` files.
- See [.gemini/rules/github-practices.md](file:///Users/ridho-akbar/Workspace/setrum/.gemini/rules/github-practices.md) for full guidelines.
