import pytest

from myfitnesspal_mcp import recent_foods


def entry(day, meal, name, calories=100.0):
    return {
        "day": day,
        "meal": meal,
        "name": name,
        "calories": calories,
        "protein": 10.0,
        "carbs": 5.0,
        "fat": 2.0,
    }


ENTRIES = [
    entry("2026-07-08", "Breakfast", "Greek Yogurt, 1 cup", 130.0),
    entry("2026-07-08", "Lunch", "Turkey\u00a0Sandwich"),
    entry("2026-07-07", "Breakfast", "Greek Yogurt, 1 cup", 120.0),
    entry("2026-07-06", "Snacks", "greek yogurt,  1 cup", 120.0),
    entry("2026-07-06", "Breakfast", "Coffee"),
    entry("2026-07-05", "Breakfast", "Coffee"),
    entry("2026-07-04", "Breakfast", "Coffee"),
]


def test_groups_by_food_with_counts_dates_and_last_logged_nutrition():
    foods, total = recent_foods.summarize(ENTRIES)

    assert total == 3
    assert [food["name"] for food in foods] == [
        "Greek Yogurt, 1 cup",
        "Turkey Sandwich",
        "Coffee",
    ]
    yogurt = foods[0]
    assert yogurt["times_logged"] == 3
    assert yogurt["last_logged"] == "2026-07-08"
    assert yogurt["first_logged"] == "2026-07-06"
    assert yogurt["meals"] == ["Breakfast", "Snacks"]
    assert yogurt["last_logged_as"]["calories"] == 130.0


def test_frequent_sort_and_limit_keep_the_total():
    foods, total = recent_foods.summarize(ENTRIES, sort="frequent", limit=2)

    assert total == 3
    assert [(food["name"], food["times_logged"]) for food in foods] == [
        ("Coffee", 3),
        ("Greek Yogurt, 1 cup", 3),
    ]


def test_filters_by_query_words_and_meal():
    foods, _ = recent_foods.summarize(ENTRIES, query="yogurt cup", meal="snacks")

    assert [(food["name"], food["times_logged"]) for food in foods] == [
        ("greek yogurt, 1 cup", 1)
    ]


def test_rejects_unknown_sort():
    with pytest.raises(ValueError, match="sort must be one of"):
        recent_foods.summarize(ENTRIES, sort="tasty")
