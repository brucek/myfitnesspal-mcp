from .food_ranking import name_matches, normalize_query
from .mfp_web import plain_text

SORTS = ("recent", "frequent")


def summarize(
    entries: list[dict],
    *,
    query: str | None = None,
    meal: str | None = None,
    sort: str = "recent",
    limit: int = 30,
) -> tuple[list[dict], int]:
    """`entries` are diary rows newest day first, so the first row seen for a
    food is its most recent log. Returns (foods, total matching before limit)."""
    if sort not in SORTS:
        raise ValueError(f"sort must be one of: {', '.join(SORTS)} (got {sort!r})")
    foods: dict[str, dict] = {}
    for entry in entries:
        if meal and normalize_query(entry.get("meal") or "") != normalize_query(meal):
            continue
        if not name_matches(entry.get("name"), query):
            continue
        key = normalize_query(entry.get("name") or "")
        food = foods.get(key)
        if food is None:
            food = foods[key] = {
                "name": plain_text(entry.get("name")),
                "times_logged": 0,
                "last_logged": entry["day"],
                "first_logged": entry["day"],
                "meals": {},
                "last_logged_as": {
                    nutrient: entry.get(nutrient)
                    for nutrient in ("calories", "protein", "carbs", "fat")
                },
            }
        food["times_logged"] += 1
        food["first_logged"] = entry["day"]
        meal_name = entry.get("meal") or "Unknown"
        food["meals"][meal_name] = food["meals"].get(meal_name, 0) + 1

    ordered = list(foods.values())
    if sort == "frequent":
        ordered.sort(key=lambda food: (-food["times_logged"], food["name"] or ""))
    for food in ordered:
        food["meals"] = sorted(food["meals"], key=lambda name: -food["meals"][name])
    return ordered[:limit], len(ordered)
