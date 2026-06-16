"""
Run this once per channel to authorize it.

Usage:
    python oauth_setup.py config/channel1.json

A browser window will open. Log into the Google account that owns the
channel this config file is for, approve access, and a token file will be
saved so the uploader script can use that channel without you logging in
again.
"""

import json
import pickle
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def main():
    if len(sys.argv) != 2:
        print("Usage: python oauth_setup.py config/channelX.json")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"Could not find config file: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    client_secret_file = Path(config["client_secret_file"])
    token_file = Path(config["token_file"])

    if not client_secret_file.exists():
        print(f"Could not find {client_secret_file}.")
        print("Did you download the OAuth client JSON from Google Cloud "
              "Console and save it there as client_secret.json? See "
              "README.md Step 2.")
        sys.exit(1)

    print(f"Authorizing channel: {config.get('channel_name', config_path.stem)}")
    print("A browser window will open. Log into the Google account that "
          "owns THIS specific channel.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
    credentials = flow.run_local_server(port=0)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    with open(token_file, "wb") as f:
        pickle.dump(credentials, f)

    print(f"\nDone. Saved authorization to {token_file}.")
    print("You can now run uploader.py and it will use this for "
          f"{config.get('channel_name', config_path.stem)}.")


if __name__ == "__main__":
    main()
