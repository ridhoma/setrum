# Port Usage & Development Rules

- **Port 8050 is RESERVED for Docker production deployment.**
  - The live, background Docker container runs on port 8050 (`http://localhost:8050` and LAN `http://<mac-name>.local:8050`).
  - Do NOT start local dev servers, test servers, or background processes on port 8050.
- **Use Port 8051 for local development:**
  - Running `uv run python run.py` automatically defaults to port 8051.
  - If specifying manually: `uv run python run.py --port 8051`.
