from lxml import html as lh

from .food_ranking import name_matches, normalize_query
from .mfp_web import api_headers, get_signed_in, plain_text, site_url

# The website's "Add Food To <meal>" page loads its Recent, My Foods, Meals and
# Recipes tabs from /food/load_<kind>. Each row carries the food_id + weight_id
# that /food/add accepts, which the API's ids for the same recipes, foods and
# meals are not; a saved meal's food_id is its meal_id (verified 2026-11-16).
KINDS = ("recipes", "meals", "my_foods", "recent")
ROW_XPATH = "//tr[.//input[contains(@name, '[food_id]')]]"


def load(client, kind: str) -> list[dict]:
    if kind not in KINDS:
        raise ValueError(f"source must be one of: {', '.join(KINDS)} (got {kind!r})")
    endpoint = f"/food/load_{kind}"
    resp = get_signed_in(
        client, site_url(client, f"food/load_{kind}"), endpoint, api_headers(client)
    )
    if not resp.text.strip():
        return []
    return [_row(row) for row in lh.fromstring(resp.text).xpath(ROW_XPATH)]


def _row(row) -> dict:
    options = row.xpath(".//select[contains(@name, '[weight_id]')]/option")
    servings = [
        {"weight_id": option.get("value"), "serving": plain_text(option.text_content())}
        for option in options
    ]
    selected = [option.get("value") for option in options if option.get("selected")]
    return {
        "name": plain_text(row.xpath("string(./td[2])")),
        "food_id": row.xpath(".//input[contains(@name, '[food_id]')]/@value")[0],
        "weight_id": (selected or [s["weight_id"] for s in servings] or [None])[0],
        "servings": servings,
    }


def by_name(items: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in items:
        index.setdefault(normalize_query(item["name"] or ""), item)
    return index


def matching(items: list[dict], query: str) -> list[dict]:
    """An exact name match wins over partial ones, so "Gigi Burger" picks that
    recipe even when "Gigi Turkey Burger" also exists."""
    wanted = normalize_query(query)
    exact = [item for item in items if normalize_query(item["name"] or "") == wanted]
    return exact or [item for item in items if name_matches(item["name"], query)]


def diary_ids(item: dict | None) -> dict:
    if item is None:
        return {"food_id": None, "weight_id": None}
    return {"food_id": item["food_id"], "weight_id": item["weight_id"]}
