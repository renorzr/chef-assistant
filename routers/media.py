import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, HTTPException, Query, Request, Response

router = APIRouter()

ALLOWED_MEDIA_HOSTS = {
    "xiachufang.com",
    "www.xiachufang.com",
    "s.chuimg.com",
    "i.chuimg.com",
    "i1.chuimg.com",
    "i2.chuimg.com",
    "i3.chuimg.com",
}


def _is_allowed_media_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").lower()
    if host in ALLOWED_MEDIA_HOSTS:
        return True
    return host.endswith(".chuimg.com")


@router.get("/media/proxy")
def proxy_media(request: Request, url: str = Query(..., min_length=1)):
    if not _is_allowed_media_url(url):
        raise HTTPException(status_code=400, detail="Unsupported media host.")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.xiachufang.com/",
    }

    cookie_header = os.getenv("XCF_RECOMMENDED_COOKIE", "").strip()
    if cookie_header:
        headers["Cookie"] = cookie_header

    # Forward browser cache validators so upstream can return 304.
    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        headers["If-None-Match"] = if_none_match

    if_modified_since = request.headers.get("if-modified-since")
    if if_modified_since:
        headers["If-Modified-Since"] = if_modified_since

    req = UrlRequest(url=url, headers=headers, method="GET")

    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            cache_control = resp.headers.get("Cache-Control", "public, max-age=3600")
            etag = resp.headers.get("ETag")
            last_modified = resp.headers.get("Last-Modified")
            expires = resp.headers.get("Expires")
    except HTTPError as exc:
        if exc.code == 304:
            response_headers = {"Cache-Control": "public, max-age=3600"}
            if exc.headers.get("ETag"):
                response_headers["ETag"] = exc.headers["ETag"]
            if exc.headers.get("Last-Modified"):
                response_headers["Last-Modified"] = exc.headers["Last-Modified"]
            if exc.headers.get("Expires"):
                response_headers["Expires"] = exc.headers["Expires"]
            return Response(status_code=304, headers=response_headers)
        raise HTTPException(status_code=exc.code, detail=f"Media upstream error: {exc.code}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"Media fetch failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Media proxy failed: {exc}") from exc

    response_headers = {"Cache-Control": cache_control}
    if etag:
        response_headers["ETag"] = etag
    if last_modified:
        response_headers["Last-Modified"] = last_modified
    if expires:
        response_headers["Expires"] = expires

    return Response(
        content=body,
        media_type=content_type,
        headers=response_headers,
    )
