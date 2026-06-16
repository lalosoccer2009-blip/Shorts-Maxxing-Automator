# YouTube Shorts Upload Automator

A local tool for managing 3 YouTube channels: drop a video into a folder, an AI
drafts the title/description/tags, you review and edit the draft right in
your terminal, then it uploads to the correct channel with a scheduled
publish time. No paid services required.

## How it works

1. You drop a finished Short into `videos/<channel>/`.
2. The script asks Gemini (Google's free AI API) to draft a title,
   description, and tags based on that channel's niche.
3. It prints the draft in your terminal. You can accept it, edit any field,
   regenerate it, or skip the video entirely.
4. You pick a publish time (right now, or scheduled for later).
5. It uploads the video to that channel via the YouTube API, sets the
   metadata and schedule, then moves the file into `videos/<channel>/uploaded/`
   so it won't be processed twice.

The script does **not** need to be running 24/7. Scheduling is handled by
YouTube itself (you set a `publishAt` time and YouTube flips the video public
at that moment) — your script only needs to run when you want to process new
videos, even just once a day.

## Three things to know before you start

**Uploads start out private until your project passes Google's audit.**
Any video uploaded through the API from a new, unaudited project is
restricted to private viewing — regardless of what privacy setting you
choose — until you complete YouTube's compliance audit. Request it early
(see Step 3 below); approval can take anywhere from days to a few weeks.
While you wait, you can still test the whole pipeline — the videos will just
stay private until the audit clears, then future uploads can go public.

**The free Gemini model name changes over time.** Google renames/replaces
free-tier models periodically. The script has a `GEMINI_MODEL` setting near
the top of `ai_writer.py` — if you get a "model not found" error, check
https://ai.google.dev/gemini-api/docs/models for the current free Flash
model name and update that one line.

**Automation covers the busywork, not the content itself.** YouTube's
monetization rules specifically target mass-produced, templated videos
(stock footage + AI voiceover + zero added value, identical formats spammed
out daily). Automating the *upload/scheduling/metadata* is completely fine
and common — just make sure the Shorts themselves still feel like something
a person made, especially once you're going for monetization.

## One-time setup

### 1. Create a Google Cloud project and enable the YouTube Data API

1. Go to https://console.cloud.google.com/ and create a new project (any name).
2. Go to "APIs & Services" → "Library", search for **YouTube Data API v3**,
   and click Enable.

### 2. Set up OAuth so the script can upload on your behalf

1. Go to "APIs & Services" → "OAuth consent screen". Choose **External**,
   fill in an app name (e.g. "My Shorts Uploader") and your email, and leave
   publishing status as **Testing**.
2. Under "Audience" / "Test users", add all 3 of your Google account email
   addresses (the ones that own each channel). This lets each of them
   complete the login flow even though the app isn't publicly verified.
3. Go to "Credentials" → "Create Credentials" → "OAuth client ID". Choose
   **Desktop app** as the application type. Download the resulting JSON file.
4. Rename it `client_secret.json` and put it in the `auth/` folder.

You only need to do this once — the same client_secret.json is shared by all
3 channels. Each channel just authorizes separately in Step 6 below.

### 3. Request the compliance audit (do this now, it takes a while)

Read https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
and submit the audit/quota extension form linked there. Describe your use
case honestly (personal use, uploading your own original Shorts to your own
channels). Do this now so it's progressing in the background while you finish
setup and testing.

### 4. Get a free Gemini API key

1. Go to https://aistudio.google.com/app/apikey and click "Create API key"
   (no credit card needed for the free tier).
2. Set it as an environment variable so the script can read it:
   - Mac/Linux: add `export GEMINI_API_KEY="your_key_here"` to your `~/.zshrc`
     or `~/.bashrc`, then restart your terminal.
   - Windows (PowerShell): `setx GEMINI_API_KEY "your_key_here"`, then open a
     new terminal window.

### 5. Install Python dependencies

```bash
pip install -r requirements.txt
```

(If you're on a Mac and pip complains about "externally managed environment",
use `pip install -r requirements.txt --break-system-packages` or set up a
virtual environment with `python3 -m venv venv && source venv/bin/activate`.)

### 6. Authorize each channel

Run this once per channel, making sure you log into the correct Google
account in the browser window that pops up each time:

```bash
python oauth_setup.py config/channel1.json
python oauth_setup.py config/channel2.json
python oauth_setup.py config/channel3.json
```

Each run saves a `token_channelX.pickle` file into `auth/` — that's what lets
the script upload to that specific channel without you logging in again.

**If two of your channels share the same Google login:** Google is supposed
to show a "which channel?" picker after you log in, but it doesn't always
appear reliably. Before authorizing the second channel on that login, go to
youtube.com, log into that account, and use the profile icon to switch the
active channel to the one you're about to authorize — that gives Google the
best shot at defaulting correctly. Afterward, run
`python check_channel.py config/channelX.json` for each one to confirm the
token actually points to the channel you meant. If it doesn't, delete that
token file and redo the authorization.

### 7. Fill in your channel configs

Open `config/channel1.json`, `channel2.json`, and `channel3.json` and edit
the `niche`, `tone`, `audience`, `category_id`, and `made_for_kids` fields to
match each channel. There's a list of common category IDs in the comments
inside each file.

## Day-to-day usage

1. Drop new Shorts into `videos/channel1/`, `videos/channel2/`, or
   `videos/channel3/`.
2. Run:

```bash
python uploader.py
```

3. For each video found, review the AI-drafted title/description/tags,
   edit anything you want, choose a publish time, and confirm.
4. The video uploads, the file moves to that channel's `uploaded/` subfolder,
   and a line gets added to `upload_log.csv` so you have a record of
   everything you've published and when.

## Troubleshooting

- **"Quota exceeded"** — the free tier allows up to 100 uploads/day per
  channel's Google Cloud project; if you're hitting this, you're uploading
  faster than the free tier supports.
- **Video stuck on private after the scheduled time** — your audit (Step 3)
  probably hasn't been approved yet.
- **"Model not found" from Gemini** — update `GEMINI_MODEL` in
  `ai_writer.py` to a current free model name.
