
import re
import instaloader
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(
    title="SIARCOM Instagram API",
    description="Testing metadata Instagram publik menggunakan Instaloader",
    version="1.0.0",
)

loader = instaloader.Instaloader(
    quiet=True,
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
)


def extract_shortcode(url: str) -> str:
    pattern = r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)"
    match = re.search(pattern, url)

    if not match:
        raise HTTPException(
            status_code=400,
            detail="URL Instagram tidak valid atau jenis URL belum didukung.",
        )

    return match.group(1)


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "SIARCOM Instagram API",
        "docs": "/docs",
        "message": "API siap untuk pengujian.",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/post")
def get_post(url: str = Query(..., description="URL publik Instagram Feed atau Reels")):
    shortcode = extract_shortcode(url)

    try:
        post = instaloader.Post.from_shortcode(
            loader.context, shortcode
        )

        is_video = post.is_video

        return {
            "success": True,
            "shortcode": post.shortcode,
            "url": f"https://www.instagram.com/p/{post.shortcode}/",
            "type": "reel_or_video" if is_video else "image_or_carousel",
            "caption": post.caption,
            "taken_at": post.date_utc.isoformat() if post.date_utc else None,
            "likes": post.likes,
            "comments": post.comments,
            "views": (
                post.video_view_count
                if is_video
                else None
            ),
            "video_play_count": (
                post.video_play_count
                if is_video
                else None
            ),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Instagram gagal memberikan data. "
                "Postingan mungkin privat, tidak tersedia, "
                "atau permintaan sedang dibatasi. "
                f"Detail: {type(exc).__name__}: {str(exc)[:250]}"
            ),
        )
