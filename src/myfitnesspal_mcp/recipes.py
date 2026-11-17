from . import favorites, nutrition
from .food_search import serving_label
from .mfp_web import api_url, get_json, plain_text

# v2/recipes ignores `limit` and `page` and returns 10 recipes per request,
# paged by `offset` (verified 2026-11-16).
PAGE_SIZE = 10
MAX_PAGES = 50


def fetch_recipes(client) -> list[dict]:
    recipes: dict[str, dict] = {}
    for page in range(MAX_PAGES):
        url = f"{api_url(client, 'recipes')}?offset={page * PAGE_SIZE}"
        items = (get_json(client, url) or {}).get("items") or []
        new = [item for item in items if item.get("id") not in recipes]
        recipes.update((item.get("id"), item) for item in new)
        if len(items) < PAGE_SIZE or not new:
            break
    return list(recipes.values())


def recipe_summary(
    item: dict, *, include_ingredients: bool = False, diary_row: dict | None = None
) -> dict:
    ingredients = item.get("ingredients") or []
    summary = {
        "recipe_id": item.get("id"),
        "name": plain_text(item.get("name")),
        **favorites.diary_ids(diary_row),
        "servings": item.get("servings"),
        "nutrition": nutrition.summary(item.get("nutritional_contents")),
        "ingredient_count": len(ingredients),
    }
    if include_ingredients:
        summary["ingredients"] = [_ingredient(line) for line in ingredients]
    return summary


def _ingredient(line: dict) -> dict:
    food = line.get("food") or {}
    return {
        "text": plain_text(line.get("raw_text")),
        "food": plain_text(food.get("description")),
        "brand": plain_text(food.get("brand_name")),
        "servings": line.get("servings"),
        "serving": serving_label(line.get("serving_size") or {}),
    }
