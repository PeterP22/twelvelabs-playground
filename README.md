# twelvelabs-playground

A tiny CLI for trying out [TwelveLabs](https://www.twelvelabs.io) video understanding from the terminal. Index a video once, then search it semantically (Marengo) or ask it questions in plain English (Pegasus).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# paste your API key into .env (from https://playground.twelvelabs.io, Settings > API Key)
```

The free tier includes 10 hours of video indexing, no credit card needed.

## Usage

```bash
# one-time: create an index, then put its id in .env as TWELVELABS_INDEX_ID
python tl.py create-index my-videos

# upload a local file or a public URL (indexing takes a few minutes)
python tl.py upload path/to/video.mp4
python tl.py upload --url https://example.com/video.mp4

# see what's indexed
python tl.py videos

# semantic search across everything in the index
python tl.py search "someone whiteboards an architecture diagram"

# summaries, chapters, highlights
python tl.py summarize VIDEO_ID
python tl.py summarize VIDEO_ID --type chapter
python tl.py summarize VIDEO_ID --type highlight

# ask anything about a specific indexed video
python tl.py analyze VIDEO_ID "List the key technical claims made, with timestamps"

# Pegasus 1.5: analyze directly with NO indexing (URL up to 2h, or local file <36MB)
python tl.py quick "Summarize this and list the 3 strongest moments with timestamps" --url https://example.com/video.mp4
python tl.py quick "Describe the squat form on each rep" --file clip.mp4
```

## Ideas to try

- Index a long conference talk, then `summarize --type chapter` to get a table of contents
- `search` for a visual moment you remember but can't find ("the demo where the terminal turns red")
- `analyze` a screen recording: "extract the strongest 30 second segment for a short clip, with timestamps"
- Film a workout set and ask about form on a specific rep

## Notes

- Videos and `.env` are gitignored; nothing sensitive or heavy goes to the repo.
- Indexing cost is the main driver at scale (free tier: 600 minutes), so index selectively.
