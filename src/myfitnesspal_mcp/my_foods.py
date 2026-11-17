from . import favorites, nutrition
from .food_ranking import normalize_query
from .food_search import serving_label
from .mfp_web import get_service_json, plain_text


def list_my_foods(client, query: str | None = None) -> list[dict]:
    params = {"search": query} if query else None
    items = get_service_json(client, "users/foods/mine", params) or []
    loggable = favorites.by_name(favorites.load(client, "my_foods"))
    return [_food(item, loggable) for item in items if not item.get("deleted")]


def _food(item: dict, loggable: dict[str, dict]) -> dict:
    name = plain_text(item.get("description"))
    brand = plain_text(item.get("brand_name"))
    # The add-food page lists a food as "Brand - Name" when it has a brand.
    row = loggable.get(normalize_query(f"{brand} - {name}")) if brand else None
    row = row or loggable.get(normalize_query(name or ""))
    servings = item.get("serving_sizes") or []
    base = next(
        (serving for serving in servings if serving.get("nutrition_multiplier") == 1),
        servings[0] if servings else {},
    )
    return {
        "name": name,
        "brand": brand,
        **favorites.diary_ids(row),
        "nutrition_per": serving_label(base),
        "nutrition": nutrition.summary(item.get("nutritional_contents")),
        "servings": row["servings"]
        if row
        else [
            {"weight_id": None, "serving": label}
            for label in map(serving_label, servings)
            if label
        ],
        "updated_at": item.get("updated_at"),
    }
