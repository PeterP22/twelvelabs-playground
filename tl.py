#!/usr/bin/env python3
"""Minimal TwelveLabs CLI for indexing, searching, and analyzing videos.

Usage:
    python tl.py create-index my-videos
    python tl.py indexes
    python tl.py upload path/to/video.mp4 [--index-id ID]
    python tl.py upload --url https://example.com/video.mp4
    python tl.py videos [--index-id ID]
    python tl.py search "someone opens a laptop" [--index-id ID]
    python tl.py summarize VIDEO_ID [--type summary|chapter|highlight]
    python tl.py analyze VIDEO_ID "What are the 3 strongest moments for a short clip? Give timestamps."

Requires TWELVELABS_API_KEY in your environment or a .env file.
"""

import argparse
import base64
import os
import sys
import time

import requests
from dotenv import load_dotenv
from twelvelabs import TwelveLabs
from twelvelabs.indexes import IndexesCreateRequestModelsItem

load_dotenv()


def get_client() -> TwelveLabs:
    api_key = os.environ.get("TWELVELABS_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        sys.exit("Set TWELVELABS_API_KEY in .env (copy .env.example) or your environment.")
    return TwelveLabs(api_key=api_key)


def get_index_id(args) -> str:
    index_id = getattr(args, "index_id", None) or os.environ.get("TWELVELABS_INDEX_ID")
    if not index_id:
        sys.exit("No index id. Pass --index-id or set TWELVELABS_INDEX_ID in .env "
                 "(create one with: python tl.py create-index my-videos)")
    return index_id


def cmd_create_index(args):
    client = get_client()
    index = client.indexes.create(
        index_name=args.name,
        models=[
            IndexesCreateRequestModelsItem(model_name="marengo3.0", model_options=["visual", "audio"]),
            IndexesCreateRequestModelsItem(model_name="pegasus1.2", model_options=["visual", "audio"]),
        ],
        addons=["thumbnail"],
    )
    print(f"Created index: {index.id}  ({args.name})")
    print(f"Tip: add TWELVELABS_INDEX_ID={index.id} to your .env to make it the default.")


def cmd_indexes(args):
    client = get_client()
    for idx in client.indexes.list():
        print(f"{idx.id}  {idx.index_name}  created={idx.created_at}")


def cmd_upload(args):
    client = get_client()
    index_id = get_index_id(args)
    if args.url:
        task = client.tasks.create(index_id=index_id, video_url=args.url)
        print(f"Uploading from URL, task {task.id}")
    else:
        if not args.file or not os.path.exists(args.file):
            sys.exit(f"File not found: {args.file}")
        print(f"Uploading {args.file} ...")
        with open(args.file, "rb") as f:
            task = client.tasks.create(index_id=index_id, video_file=f)
        print(f"Task {task.id} created, indexing (this can take a few minutes)...")

    task.wait_for_done(sleep_interval=10, callback=lambda t: print(f"  status: {t.status}"))
    if task.status != "ready":
        sys.exit(f"Indexing failed with status: {task.status}")
    print(f"Done. Video ID: {task.video_id}")


def cmd_videos(args):
    client = get_client()
    index_id = get_index_id(args)
    for video in client.indexes.videos.list(index_id=index_id):
        name = getattr(getattr(video, "system_metadata", None), "filename", "") or ""
        duration = getattr(getattr(video, "system_metadata", None), "duration", "") or ""
        print(f"{video.id}  {name}  {duration}s")


def cmd_search(args):
    client = get_client()
    index_id = get_index_id(args)
    results = client.search.query(
        index_id=index_id,
        query_text=args.query,
        search_options=["visual", "audio"],
    )
    found = False
    for clip in results:
        found = True
        print(f"video={clip.video_id}  {clip.start:8.1f}s - {clip.end:8.1f}s  "
              f"score={clip.score:.2f}  confidence={clip.confidence}")
    if not found:
        print("No results.")


def cmd_summarize(args):
    client = get_client()
    res = client.summarize(video_id=args.video_id, type=args.type)
    if args.type == "summary":
        print(res.summary)
    elif args.type == "chapter":
        for ch in res.chapters:
            print(f"[{ch.start:.0f}s - {ch.end:.0f}s] {ch.chapter_title}")
            print(f"  {ch.chapter_summary}")
    else:
        for hl in res.highlights:
            print(f"[{hl.start:.0f}s - {hl.end:.0f}s] {hl.highlight}")


def cmd_quick(args):
    """Pegasus 1.5 direct analysis: no indexing, straight from a URL or small local file."""
    api_key = os.environ.get("TWELVELABS_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        sys.exit("Set TWELVELABS_API_KEY in .env (copy .env.example) or your environment.")

    if args.url:
        video = {"type": "url", "url": args.url}
    else:
        if not args.file or not os.path.exists(args.file):
            sys.exit(f"File not found: {args.file}")
        size_mb = os.path.getsize(args.file) / 1024 / 1024
        if size_mb > 36:
            sys.exit(f"File is {size_mb:.0f}MB; base64 upload is limited to 36MB. "
                     "Use --url with a hosted copy, or `upload` + `analyze` via an index instead.")
        with open(args.file, "rb") as f:
            video = {"type": "base64", "data": base64.b64encode(f.read()).decode()}

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "model_name": "pegasus1.5",
        "video": video,
        "prompt": args.prompt,
        "temperature": 0.2,
    }
    resp = requests.post("https://api.twelvelabs.io/v1.3/analyze/tasks", json=payload, headers=headers)
    if resp.status_code >= 400:
        sys.exit(f"Request failed ({resp.status_code}): {resp.text}")
    task_id = resp.json().get("_id") or resp.json().get("id")
    print(f"Analysis task {task_id} created, waiting...")

    while True:
        time.sleep(10)
        r = requests.get(f"https://api.twelvelabs.io/v1.3/analyze/tasks/{task_id}", headers=headers)
        body = r.json()
        status = body.get("status")
        print(f"  status: {status}")
        if status in ("ready", "completed", "done"):
            data = body.get("data") or body.get("result") or body
            print()
            print(data if isinstance(data, str) else __import__("json").dumps(data, indent=2))
            return
        if status in ("failed", "error"):
            sys.exit(f"Analysis failed: {body}")


def cmd_analyze(args):
    client = get_client()
    res = client.analyze(video_id=args.video_id, prompt=args.prompt, temperature=0.2)
    print(res.data)


def main():
    parser = argparse.ArgumentParser(description="TwelveLabs playground CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-index", help="Create an index with Marengo + Pegasus")
    p.add_argument("name")
    p.set_defaults(func=cmd_create_index)

    p = sub.add_parser("indexes", help="List your indexes")
    p.set_defaults(func=cmd_indexes)

    p = sub.add_parser("upload", help="Upload and index a video (file or --url)")
    p.add_argument("file", nargs="?", help="Path to a local video file")
    p.add_argument("--url", help="Public video URL instead of a local file")
    p.add_argument("--index-id")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("videos", help="List videos in an index")
    p.add_argument("--index-id")
    p.set_defaults(func=cmd_videos)

    p = sub.add_parser("search", help="Semantic search across an index (Marengo)")
    p.add_argument("query")
    p.add_argument("--index-id")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("summarize", help="Summary, chapters, or highlights (Pegasus)")
    p.add_argument("video_id")
    p.add_argument("--type", choices=["summary", "chapter", "highlight"], default="summary")
    p.set_defaults(func=cmd_summarize)

    p = sub.add_parser("quick", help="Pegasus 1.5: analyze a video directly, no indexing")
    p.add_argument("prompt")
    p.add_argument("--file", help="Local video file (max 36MB)")
    p.add_argument("--url", help="Public video URL (up to 2 hours)")
    p.set_defaults(func=cmd_quick)

    p = sub.add_parser("analyze", help="Open-ended prompt over an indexed video (Pegasus)")
    p.add_argument("video_id")
    p.add_argument("prompt")
    p.set_defaults(func=cmd_analyze)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
