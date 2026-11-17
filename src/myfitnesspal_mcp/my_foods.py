from . import nutrition
from .food_search import serving_label
from .mfp_web import get_service_json, plain_text


def list_my_foods(client, query: str | None = None) -> list[dict]:
    params = {"search": query} if query else None
    items = get_service_json(client, "users/foods/mine", params) or []
    return [_food(item) for item in items if not item.get("deleted")]


def _food(item: dict) -> dict:
    servings = item.get("serving_sizes") or []
    base = next(
        (serving for serving in servings if serving.get("nutrition_multiplier") == 1),
        servings[0] if servings else {},
    )
    return {
        "food_id": item.get("id"),
        "name": plain_text(item.get("description")),
        "brand": plain_text(item.get("brand_name")),
        "nutrition_per": serving_label(base),
        "nutrition": nutrition.summary(item.get("nutritional_contents")),
        "servings": [label for label in map(serving_label, servings) if label],
        "updated_at": item.get("updated_at"),
    }
