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
    zeros included, so a missing field comes back as None. Recipe values carry
    float noise (32.65999984741211), hence the rounding."""
    contents = contents or {}
    energy = contents.get("energy")
    calories = energy.get("value") if isinstance(energy, dict) else energy
    return {
        "calories": _rounded(calories),
        **{name: _rounded(contents.get(key)) for name, key in SUMMARY_FIELDS.items()},
    }


def _rounded(value):
    return round(value, 1) if isinstance(value, float) else value
