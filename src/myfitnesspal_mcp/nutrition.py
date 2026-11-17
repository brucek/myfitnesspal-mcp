SUMMARY_FIELDS = {
    "protein": "protein",
    "carbs": "carbohydrates",
    "fat": "fat",
    "fiber": "fiber",
    "sugar": "sugar",
    "sodium": "sodium",
}


def summary(contents: dict | None) -> dict[str, float | None]:
    """MFP's `nutritional_contents` leaves out nutrients it has no value for,
    zeros included, so a missing field comes back as None."""
    contents = contents or {}
    energy = contents.get("energy")
    calories = energy.get("value") if isinstance(energy, dict) else energy
    return {
        "calories": calories,
        **{name: contents.get(key) for name, key in SUMMARY_FIELDS.items()},
    }
