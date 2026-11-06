"""Quick standalone probe of the Octopus consumption endpoint.

NOT used by the app — kept around as a manual debugging template.
Reads everything from env vars so no personal identifiers leak into
git. Set these in your local `.env` (which is gitignored):

    OCTOPUS_API_KEY=sk_live_…
    OCTOPUS_MPAN=2200000000000
    OCTOPUS_METER_SERIAL=Sxxxxxxxxx
"""

import os
import sys

import requests
from dotenv import load_dotenv

from core.credentials import get_credential

load_dotenv()

api_key = get_credential("OCTOPUS_API_KEY")
mpan = get_credential("OCTOPUS_MPAN")
serial = get_credential("OCTOPUS_METER_SERIAL")

if not api_key or not mpan or not serial:
    sys.exit(
        "Missing credentials. Set OCTOPUS_API_KEY, OCTOPUS_MPAN, "
        "OCTOPUS_METER_SERIAL in your .env or macOS Keychain."
    )

period_from = os.getenv("OCTOPUS_PROBE_FROM", "2026-02-01T00:00:00Z")
period_to   = os.getenv("OCTOPUS_PROBE_TO",   "2026-02-08T00:00:00Z")

url = (
    f"https://api.octopus.energy/v1/electricity-meter-points/{mpan}"
    f"/meters/{serial}/consumption/"
    f"?period_from={period_from}&period_to={period_to}"
)

res = requests.get(url, auth=(api_key, ""))
print(res.status_code)
print(res.json())
