
import os
import re
from functools import lru_cache

import instaloader
from fastapi import FastAPI, HTTPException, Query
from instaloader import Profile, Post

app = FastAPI(
    title="Instagram Scraper API",
    description="API untuk mengambil metadata post dan jumlah followers Instagram menggunakan Instaloader.",
    version="1.4.0",
)

SESSION_FILE = os.getenv("IG_SESSION_FILE", "ig_session")


@app.get("/")
def home():
    return {
        "success": True,
        "message": "Instagram Scraper API is running",
        "version": app.version,
        "endpoints": ["/health", "/post", "/followers", "/docs"],
    }


@app.get("/health")
def health():
    return {"success": True, "status": "healthy"}


@lru_cache(maxsize=1)
def get_instaloader() -> instaloader.Instaloader:
    """Membuat satu instance Instaloader dengan login opsional."""

    loader = instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
    )

    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")

    # Gunakan session jika tersedia.
    if username and os.path.exists(SESSION_FILE):
        try:
            loader.load_session_from_file(
                username,
                filename=SESSION_FILE
            )
        except Exception:
            pass

    # Login hanya jika username dan password dikonfigurasi.
    # Jika tidak ada, Instaloader berjalan tanpa login.
    if username and password and not loader.context.is_logged_in:
        loader.login(username, password)
        loader.save_session_to_file(filename=SESSION_FILE)

    return loader


def validate_username(username: str) -> str:
    clean = username.strip().lstrip("@")

    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", clean):
        raise HTTPException(
            status_code=400,
            detail="Format username Instagram tidak valid."
        )

    return clean


@app.get("/post")
def get_post(
    url: str = Query(
        ...,
        description="URL post atau Reel Instagram"
    ),
):
    """Mengambil metadata dasar dari satu post atau Reel Instagram."""

    match = re.search(
        r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)",
        url.strip(),
        re.IGNORECASE,
    )

    if not match:
        raise HTTPException(
            status_code=400,
            detail="URL tidak valid. Gunakan URL /p/, /reel/, atau /tv/."
        )

    shortcode = match.group(1)

    try:
        loader = get_instaloader()
        post = Post.from_shortcode(loader.context, shortcode)

        video_url = None

        if post.is_video:
            try:
                video_url = post.video_url
            except Exception:
                video_url = None

        view_count = getattr(post, "video_view_count", None)

        return {
            "success": True,
            "data": {
                "shortcode": post.shortcode,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "owner_username": post.owner_username,
                "caption": post.caption,
                "likes": post.likes,
                "comments": post.comments,
                "date_utc": (
                    post.date_utc.isoformat()
                    if post.date_utc else None
                ),
                "is_video": post.is_video,
                "video_url": video_url,
                "views": view_count,
                "video_view_count": view_count,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gagal mengambil data post: {type(exc).__name__}",
        )


@app.get("/followers")
def get_followers_count(
    username: str = Query(
        ...,
        min_length=1,
        max_length=30,
        description="Username Instagram yang ingin diperiksa jumlah followers-nya"
    ),
):
    """Mengambil jumlah total followers berdasarkan username Instagram."""

    clean_username = validate_username(username)

    try:
        loader = get_instaloader()

        profile = Profile.from_username(
            loader.context,
            clean_username
        )

        return {
            "success": True,
            "data": {
                "username": profile.username,
                "full_name": profile.full_name,
                "followers_count": profile.followers,
                "is_private": profile.is_private,
                "is_verified": profile.is_verified,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gagal mengambil jumlah followers: {type(exc).__name__}",
        )
