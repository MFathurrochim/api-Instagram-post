
import os
import re
from functools import lru_cache
from typing import Optional

import instaloader
from fastapi import FastAPI, Header, HTTPException, Query
from instaloader import Profile, Post

app = FastAPI(
    title="Instagram Scraper API",
    description="API untuk mengambil metadata post dan jumlah followers Instagram menggunakan Instaloader.",
    version="1.3.0",
)

SESSION_FILE = os.getenv("IG_SESSION_FILE", "ig_session")


@app.get("/")
def home():
    return {
        "success": True,
        "message": "Instagram Scraper API is running",
        "version": app.version,
        "endpoints": [
            "/health",
            "/post",
            "/followers",
            "/docs"
        ],
    }


@app.get("/health")
def health():
    return {"success": True, "status": "healthy"}


def check_api_key(x_api_key: Optional[str]) -> None:
    expected = os.getenv("API_KEY")

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="API_KEY belum dikonfigurasi pada environment Wasmer.",
        )

    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="API key tidak valid."
        )


@lru_cache(maxsize=1)
def get_instaloader() -> instaloader.Instaloader:
    """Buat satu instance Instaloader untuk digunakan selama proses berjalan."""
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

    if username and os.path.exists(SESSION_FILE):
        try:
            loader.load_session_from_file(
                username,
                filename=SESSION_FILE
            )
        except Exception:
            pass

    if username and password and not loader.context.is_logged_in:
        loader.login(username, password)
        loader.save_session_to_file(filename=SESSION_FILE)

    return loader


def validate_username(username: str) -> str:
    clean = username.strip().lstrip("@")

    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", clean):
        raise HTTPException(
            status_code=400,
            detail="Format username tidak valid."
        )

    return clean


@app.get("/post")
def get_post(
    url: str = Query(..., description="URL post atau Reel Instagram"),
):
    """Mengambil metadata dasar dari satu post/Reel Instagram."""

    match = re.search(
        r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)",
        url.strip(),
        re.IGNORECASE,
    )

    if not match:
        raise HTTPException(
            status_code=400,
            detail="URL Instagram tidak valid. Gunakan URL /p/, /reel/, atau /tv/.",
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
    x_api_key: Optional[str] = Header(
        default=None,
        alias="X-API-Key"
    ),
):
    """Mengambil jumlah total followers berdasarkan username Instagram."""

    check_api_key(x_api_key)
    clean_username = validate_username(username)

    try:
        loader = get_instaloader()

        if not loader.context.is_logged_in:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Login Instagram belum tersedia. Atur IG_USERNAME dan "
                    "IG_PASSWORD pada environment Wasmer."
                ),
            )

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
