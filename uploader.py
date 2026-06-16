"""
Main script you run day-to-day.

Usage:
    python uploader.py

Scans videos/channel1, videos/channel2, videos/channel3 for new video
files, drafts metadata with AI for each one, lets you review/edit it,
asks when to publish, then uploads it to that channel.
"""

import csv
import datetime as dt
import json
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import ai_writer

CONFIG_DIR = Path("config")
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
LOG_FILE = Path("upload_log.csv")


def load_channel_configs():
    configs = []
    for path in sorted(CONFIG_DIR.glob("*.json")):
        with open(path) as f:
            cfg = json.load(f)
        cfg["_config_path"] = str(path)
        configs.append(cfg)
    return configs


def find_new_videos(channel_cfg):
    folder = Path(channel_cfg["video_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    uploaded_folder = folder / "uploaded"
    uploaded_folder.mkdir(parents=True, exist_ok=True)

    videos = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return sorted(videos)


def get_authenticated_service(channel_cfg):
    token_file = Path(channel_cfg["token_file"])
    if not token_file.exists():
        raise RuntimeError(
            f"No authorization found for {channel_cfg.get('channel_name')}. "
            f"Run: python oauth_setup.py {channel_cfg['_config_path']}"
        )

    with open(token_file, "rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def prompt_for_extra_notes():
    print("\nAny quick context for the AI before it drafts metadata? "
          "(optional, press Enter to skip)")
    return input("> ").strip()


def review_loop(channel_cfg, video_path):
    extra_notes = prompt_for_extra_notes()
    metadata = ai_writer.generate_metadata(channel_cfg, video_path.name, extra_notes)

    while True:
        print("\n--- Draft metadata ---")
        print(f"Title:       {metadata['title']}")
        print(f"Description: {metadata['description']}")
        print(f"Tags:        {', '.join(metadata['tags'])}")
        print("----------------------")
        print("[a] accept   [t] edit title   [d] edit description")
        print("[g] edit tags   [r] regenerate   [s] skip this video")
        choice = input("> ").strip().lower()

        if choice == "a":
            return metadata
        elif choice == "t":
            new_title = input("New title: ").strip()
            if new_title:
                metadata["title"] = new_title[:100]
        elif choice == "d":
            print("New description (single line):")
            new_desc = input("> ").strip()
            if new_desc:
                metadata["description"] = new_desc
        elif choice == "g":
            new_tags = input("New tags, comma-separated: ").strip()
            if new_tags:
                metadata["tags"] = [t.strip() for t in new_tags.split(",") if t.strip()]
        elif choice == "r":
            extra_notes = prompt_for_extra_notes()
            metadata = ai_writer.generate_metadata(channel_cfg, video_path.name, extra_notes)
        elif choice == "s":
            return None
        else:
            print("Didn't recognize that option, try again.")


def prompt_for_schedule():
    print("\nWhen should this go live?")
    print("[1] Right now (public immediately)")
    print("[2] Schedule for a specific date/time")
    print("[3] Save as private for now (don't schedule)")
    choice = input("> ").strip()

    if choice == "2":
        while True:
            raw = input("Enter date/time as YYYY-MM-DD HH:MM (your local time): ").strip()
            try:
                local_dt = dt.datetime.strptime(raw, "%Y-%m-%d %H:%M")
                utc_dt = local_dt.astimezone(dt.timezone.utc)
                publish_at = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                return "private", publish_at
            except ValueError:
                print("Couldn't parse that, format is YYYY-MM-DD HH:MM, try again.")
    elif choice == "3":
        return "private", None
    else:
        return "public", None


def upload_video(youtube, channel_cfg, video_path, metadata, privacy_status, publish_at):
    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": str(channel_cfg.get("category_id", "22")),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": bool(channel_cfg.get("made_for_kids", False)),
        },
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print("Uploading...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}% uploaded")

    return response


def log_upload(channel_cfg, video_path, metadata, privacy_status, publish_at, video_id):
    is_new = not LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow([
                "timestamp", "channel", "video_file", "video_id",
                "title", "privacy_status", "publish_at",
                "url",
            ])
        writer.writerow([
            dt.datetime.now().isoformat(timespec="seconds"),
            channel_cfg.get("channel_name", ""),
            video_path.name,
            video_id,
            metadata["title"],
            privacy_status,
            publish_at or "",
            f"https://youtube.com/watch?v={video_id}",
        ])


def process_channel(channel_cfg):
    videos = find_new_videos(channel_cfg)
    if not videos:
        return

    print(f"\n=== {channel_cfg.get('channel_name', channel_cfg['_config_path'])} ===")
    print(f"Found {len(videos)} video(s) to process.")

    youtube = None  # only authenticate if we actually have something to upload

    for video_path in videos:
        print(f"\n>>> {video_path.name}")
        metadata = review_loop(channel_cfg, video_path)
        if metadata is None:
            print("Skipped.")
            continue

        privacy_status, publish_at = prompt_for_schedule()

        if youtube is None:
            youtube = get_authenticated_service(channel_cfg)

        response = upload_video(
            youtube, channel_cfg, video_path, metadata, privacy_status, publish_at
        )
        video_id = response["id"]
        log_upload(channel_cfg, video_path, metadata, privacy_status, publish_at, video_id)

        uploaded_folder = Path(channel_cfg["video_folder"]) / "uploaded"
        video_path.rename(uploaded_folder / video_path.name)

        print(f"Done: https://youtube.com/watch?v={video_id}")
        if privacy_status == "private" and publish_at:
            print(f"(Scheduled for {publish_at} UTC, will be public then "
                  "once your channel's compliance audit is approved.)")
        elif privacy_status == "private":
            print("(Saved as private. Change it to public/scheduled in "
                  "YouTube Studio whenever you're ready.)")


def main():
    channel_configs = load_channel_configs()
    if not channel_configs:
        print("No channel config files found in config/. See README.md.")
        return

    for channel_cfg in channel_configs:
        process_channel(channel_cfg)

    print("\nAll channels processed.")


if __name__ == "__main__":
    main()
