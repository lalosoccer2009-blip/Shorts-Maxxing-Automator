"""
Confirms which YouTube channel a saved token is actually authorized for.

This matters most if two of your channels share the same Google login --
run this after oauth_setup.py for each config to make sure the token
points to the channel you actually meant, not just whichever one was
"active" on that account at the time.

Usage:
    python check_channel.py config/channel1.json
"""

import json
import pickle
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def main():
    if len(sys.argv) != 2:
        print("Usage: python check_channel.py config/channelX.json")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    with open(config_path) as f:
        config = json.load(f)

    token_file = Path(config["token_file"])
    if not token_file.exists():
        print(f"No token found at {token_file}. Run oauth_setup.py first:")
        print(f"  python oauth_setup.py {config_path}")
        sys.exit(1)

    with open(token_file, "rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    youtube = build("youtube", "v3", credentials=creds)
    response = youtube.channels().list(part="snippet,statistics", mine=True).execute()

    items = response.get("items", [])
    if not items:
        print("This token isn't tied to any channel at all -- something's wrong.")
        return

    channel = items[0]
    print(f"\nToken file: {token_file}")
    print(f"Is authorized for channel: {channel['snippet']['title']}")
    print(f"Subscribers: {channel['statistics'].get('subscriberCount', 'hidden')}")
    print(f"Channel ID: {channel['id']}")
    print(f"\nDoes this match what you set as '{config.get('channel_name')}' "
          f"in {config_path}?")
    print("If NOT: delete this token file, then redo:")
    print(f"  python oauth_setup.py {config_path}")
    print("and pick the correct channel when Google asks (or switch the "
          "active channel on youtube.com for that login before re-running it).")


if __name__ == "__main__":
    main()
