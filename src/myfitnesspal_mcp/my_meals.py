from . import favorites
from .mfp_web import get_service_json, plain_text

MEAL_FOOD_FIELDS = ("calories", "protein", "carbs", "fat", "sodium", "sugar")


def list_my_meals(client) -> list[dict]:
    loggable = {row["food_id"]: row for row in favorites.load(client, "meals")}
    return [
        _meal(item, loggable.get(str(item.get("meal_id"))))
        for item in get_service_json(client, "users/meals/mine") or []
    ]


def _meal(item: dict, row: dict | None) -> dict:
    foods = [
        {
            "name": plain_text(food.get("description")),
            **{field: food.get(field) for field in MEAL_FOOD_FIELDS},
        }
        for food in item.get("foods") or []
    ]
    return {
        "meal_id": item.get("meal_id"),
        "name": plain_text(item.get("description")),
        **favorites.diary_ids(row),
        "foods": foods,
        "totals": {
            field: round(sum(food[field] or 0 for food in foods), 1)
            for field in MEAL_FOOD_FIELDS
        },
    }
