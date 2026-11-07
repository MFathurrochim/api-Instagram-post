


    
  
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="API_KEY belum dikonfigurasi pada environment Wasmer.",
        )
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="API key tidak valid.")


@lru_cache(maxsize=1)
def get_instagram_client() -> Client:
    """Login sekali per proses; gunakan session file bila tersedia."""
    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")

    if not username or not password:
        raise RuntimeError("IG_USERNAME dan IG_PASSWORD belum dikonfigurasi.")

    client = Client()
    client.delay_range = [2, 5]

    if os.path.exists(SESSION_FILE):
        client.load_settings(SESSION_FILE)

    client.login(username, password)
    # Simpan session untuk mengurangi login ulang selama file masih tersedia.
    client.dump_settings(SESSION_FILE)
    return client


@app.get("/followers")
def get_followers(
    username: str = Query(..., min_length=1, max_length=30),
    limit: int = Query(50, ge=1, le=200),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Mengambil sebagian daftar followers akun Instagram.
    Maksimum 200 akun per request untuk membatasi beban dan risiko rate limit.
    """
    check_api_key(x_api_key)

    clean_username = username.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", clean_username):
        raise HTTPException(status_code=400, detail="Format username tidak valid.")

    try:
        client = get_instagram_client()
        profile = client.user_info_by_username(clean_username)
        followers = client.user_followers(profile.pk, amount=limit)

        items = []
        for follower in followers.values():
            picture = getattr(follower, "profile_pic_url", None)
            items.append(
                {
                    "id": str(getattr(follower, "pk", "")),
                    "username": getattr(follower, "username", None),
                    "full_name": getattr(follower, "full_name", None),
                    "is_private": getattr(follower, "is_private", None),
                    "is_verified": getattr(follower, "is_verified", None),
                    "profile_pic_url": str(picture) if picture else None,
                }
            )

        return {
            "success": True,
            "target": {
                "username": profile.username,
                "full_name": profile.full_name,
                "follower_count": profile.follower_count,
                "is_private": profile.is_private,
                "is_verified": profile.is_verified,
            },
            "requested": limit,
            "returned": len(items),
            "followers": items,
            "note": (
                "Hasil dapat lebih sedikit dari jumlah yang diminta. "
                "Instagram dapat membatasi akses atau daftar akun."
            ),
        }

    except HTTPException:
        raise
    except (ChallengeRequired, TwoFactorRequired):
        raise HTTPException(
            status_code=503,
            detail=(
                "Instagram meminta verifikasi login (challenge/2FA). "
                "Selesaikan verifikasi akun lalu perbarui session."
            ),
        )
    except (LoginRequired, PleaseWaitFewMinutes):
        raise HTTPException(
            status_code=503,
            detail=(
                "Sesi Instagram tidak valid atau permintaan sedang dibatasi. "
                "Coba lagi nanti dan periksa kredensial/session."
            ),
        )
    except Exception as exc:
        # Jangan mengirim password, cookies, atau isi session ke respons API.
        raise HTTPException(
            status_code=502,
            detail=f"Gagal mengambil followers: {type(exc).__name__}",
        )
