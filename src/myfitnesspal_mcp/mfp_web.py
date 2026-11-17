from datetime import date
from urllib import parse

from lxml import html as lh

ORIGIN = "https://www.myfitnesspal.com"
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded; charset=UTF-8"


def api_url(client, path: str, *, fields: tuple[str, ...] = ()) -> str:
    url = parse.urljoin(client.BASE_API_URL, f"v2/{path}")
    if not fields:
        return url
    return f"{url}?{parse.urlencode([('fields[]', field) for field in fields])}"


def site_url(
    client, path: str, day: date | None = None, *, params: dict | None = None
) -> str:
    url = parse.urljoin(client.BASE_URL_SECURE, path)
    query = dict(params or {})
    if day is not None:
        query["date"] = day.isoformat()
    if not query:
        return url
    # Encoded exactly as the hand-built search URL always was (%20, bare "/"):
    # urlencode's default "+" for spaces hasn't been tried against MFP.
    return f"{url}?{parse.urlencode(query, safe='/', quote_via=parse.quote)}"


# MFP has no write API, so these replicate what the web app's own JavaScript
# sends: writes authenticate with the session's Bearer token plus the mfp-*
# client headers, and form posts add the page csrf token (form_headers).
def api_headers(client, extra: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {client.access_token}",
        "mfp-client-id": "mfp-main-js",
        "mfp-user-id": str(client.user_id),
        "X-Requested-With": "XMLHttpRequest",
    }
    if extra:
        headers.update(extra)
    return headers


def form_headers(
    client, csrf: str, referer: str, accept: str | None = None
) -> dict[str, str]:
    extra = {
        "X-CSRF-Token": csrf,
        "Origin": ORIGIN,
        "Referer": referer,
        "Content-Type": FORM_CONTENT_TYPE,
    }
    if accept:
        extra["Accept"] = accept
    return api_headers(client, extra)


def require_status(resp, endpoint: str, accepted: tuple[int, ...]) -> None:
    if resp.status_code not in accepted:
        raise RuntimeError(f"MyFitnessPal {endpoint} returned HTTP {resp.status_code}")


def plain_text(value: str | None) -> str | None:
    """MFP's JSON names use non-breaking spaces between words."""
    if value is None:
        return None
    return " ".join(str(value).split())


SERVICES_SIGNED_OUT = (301, 302, 303, 307, 308, 401, 403)


def get_service_json(client, path: str, params: dict | None = None):
    """The www site's /api/services routes, which the web app calls with the
    session cookie alone. A signed-out session is redirected to /account/logout
    rather than refused, and the page behind that redirect is the sign-out
    confirmation, so redirects are reported as a signed-out session and never
    followed (verified 2026-11-16)."""
    endpoint = f"/api/services/{path}"
    resp = client.session.get(
        site_url(client, f"api/services/{path}", params=params),
        headers={"Accept": "application/json"},
        allow_redirects=False,
    )
    if resp.status_code in SERVICES_SIGNED_OUT:
        raise RuntimeError(
            f"MyFitnessPal answered {endpoint} with HTTP {resp.status_code}: "
            "the session isn't signed in"
        )
    require_status(resp, endpoint, (200,))
    if "json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(
            f"MyFitnessPal answered {endpoint} with a page instead of data: "
            "the session isn't signed in"
        )
    return resp.json()


def get_document(client, url: str) -> lh.HtmlElement:
    resp = client.session.get(url, headers=api_headers(client))
    resp.raise_for_status()
    return lh.fromstring(resp.text)


def get_page(client, url: str) -> tuple[lh.HtmlElement, str]:
    doc = get_document(client, url)
    tokens = doc.xpath("//meta[@name='csrf-token']/@content")
    if not tokens:
        raise RuntimeError("couldn't read the MyFitnessPal csrf token")
    return doc, tokens[0]


def get_json(client, url: str) -> dict | None:
    resp = client.session.get(
        url, headers=api_headers(client, {"Accept": "application/json"})
    )
    resp.raise_for_status()
    return resp.json()


def post_legacy_delete(
    client, path: str, entry_id: str, token: str, *, referer: str
) -> None:
    resp = client.session.post(
        site_url(client, f"{path}/{entry_id}"),
        data={"_method": "delete", "authenticity_token": token},
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": ORIGIN,
            "Referer": referer,
        },
    )
    require_status(resp, f"/{path}", (200, 204))
