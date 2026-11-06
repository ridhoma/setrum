from __future__ import annotations

import getpass
import os
import platform
import subprocess
import sys
from dotenv import load_dotenv

load_dotenv()


def get_credential(key: str, service: str = "setrum") -> str | None:
    """Retrieve a credential with precedence:
    1. Environment variable / .env file
    2. macOS Keychain (if on Darwin)
    """
    # 1. Environment variable / .env
    val = os.getenv(key)
    if val:
        return val

    # 2. macOS Keychain
    if platform.system() == "Darwin":
        # Check service="setrum", account=key
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-a", key, "-w"],
                capture_output=True,
                text=True,
                check=True,
            )
            out = result.stdout.strip()
            if out:
                return out
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Fallback: check service=key
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", key, "-w"],
                capture_output=True,
                text=True,
                check=True,
            )
            out = result.stdout.strip()
            if out:
                return out
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    return None


def set_credential(key: str, value: str, service: str = "setrum") -> bool:
    """Save a credential to macOS Keychain."""
    if platform.system() != "Darwin":
        print("macOS Keychain is only supported on macOS.")
        return False
    try:
        subprocess.run(
            ["security", "add-generic-password", "-U", "-s", service, "-a", key, "-w", value],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to save {key} to Keychain: {e.stderr.strip()}")
        return False


def get_octopus_api_key() -> str | None:
    return get_credential("OCTOPUS_API_KEY")


def get_octopus_account_number() -> str | None:
    return get_credential("OCTOPUS_ACCOUNT_NUMBER")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "check":
        api_key = get_octopus_api_key()
        acc = get_octopus_account_number()
        print(f"OCTOPUS_API_KEY: {'✓ Configured' if api_key else '✗ Missing'}")
        print(f"OCTOPUS_ACCOUNT_NUMBER: {'✓ Configured' if acc else '✗ Missing'}")
        sys.exit(0)

    print("Setrum — Secure Keychain Setup")
    print("---------------------------------")
    print("Values entered will be saved directly into your macOS Keychain.")
    print("Typing is hidden.\n")

    key = getpass.getpass("Enter Octopus API Key: ").strip()
    if key:
        if set_credential("OCTOPUS_API_KEY", key):
            print("✓ Saved OCTOPUS_API_KEY to macOS Keychain.")

    acc = getpass.getpass("Enter Octopus Account Number: ").strip()
    if acc:
        if set_credential("OCTOPUS_ACCOUNT_NUMBER", acc):
            print("✓ Saved OCTOPUS_ACCOUNT_NUMBER to macOS Keychain.")

    print("\nVerification:")
    print(f"OCTOPUS_API_KEY: {'✓ Present' if get_octopus_api_key() else '✗ Missing'}")
    print(f"OCTOPUS_ACCOUNT_NUMBER: {'✓ Present' if get_octopus_account_number() else '✗ Missing'}")
