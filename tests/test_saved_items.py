import json

import pytest
from conftest import FIXTURES, FakeClient, FakeResponse

from myfitnesspal_mcp import favorites, mfp_client, my_foods, my_meals, recipes
from myfitnesspal_mcp.mfp_web import get_service_json, plain_text

JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}
HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}


def favorites_response(kind):
    return FakeResponse(
        text=(FIXTURES / f"favorites_{kind}.html").read_text(), headers=HTML_HEADERS
    )


def client_with(*routes):
    client = FakeClient()
    for fragment, response in routes:
        client.session.route("GET", fragment, response)
    return client


def fixture_json(name):
    return json.loads((FIXTURES / name).read_text())


def service_response(name):
    return FakeResponse(json_data=fixture_json(name), headers=JSON_HEADERS)


def test_plain_text_collapses_non_breaking_spaces():
    assert plain_text("Trail Mix  Bar ") == "Trail Mix Bar"
    assert plain_text(None) is None


def my_foods_client():
    return client_with(
        ("api/services/users/foods/mine", service_response("my_foods.json")),
        ("food/load_my_foods", favorites_response("my_foods")),
    )


def test_my_foods_lists_live_foods_with_nutrition_per_base_serving():
    client = my_foods_client()

    foods = my_foods.list_my_foods(client)

    assert [food["name"] for food in foods] == ["Trail Mix Bar", "Energy Gel"]
    bar = foods[0]
    assert bar["food_id"] == "5200000001"
    assert bar["weight_id"] == "6200000001"
    assert bar["brand"] == "Acme"
    assert bar["nutrition_per"] == "1 bar"
    assert bar["servings"] == [
        {"weight_id": "6200000001", "serving": "1 bar"},
        {"weight_id": "6200000002", "serving": "0.5 bar"},
    ]
    assert bar["nutrition"] == {
        "calories": 190,
        "protein": 5,
        "carbs": 24,
        "fat": 8,
        "fiber": None,
        "sugar": 11,
        "sodium": 95,
    }
    assert foods[1]["nutrition"]["protein"] is None


def test_my_food_missing_from_the_add_food_page_has_no_diary_ids():
    client = client_with(
        ("api/services/users/foods/mine", service_response("my_foods.json")),
        ("food/load_my_foods", FakeResponse(text="", headers=HTML_HEADERS)),
    )

    bar = my_foods.list_my_foods(client)[0]

    assert (bar["food_id"], bar["weight_id"]) == (None, None)
    assert bar["servings"][0] == {"weight_id": None, "serving": "1 bar"}


def test_my_foods_passes_the_query_to_mfp_search():
    client = my_foods_client()

    my_foods.list_my_foods(client, "trail mix")

    method, url, kwargs = client.session.calls[0]
    assert url.endswith("api/services/users/foods/mine?search=trail%20mix")
    assert kwargs["allow_redirects"] is False


def test_my_meals_lists_foods_and_totals():
    client = client_with(
        ("api/services/users/meals/mine", service_response("my_meals.json")),
        ("food/load_meals", favorites_response("meals")),
    )

    meals = my_meals.list_my_meals(client)

    assert [meal["name"] for meal in meals] == [
        "Oatmeal breakfast",
        "Turkey sandwich lunch",
    ]
    oatmeal = meals[0]
    assert oatmeal["meal_id"] == 111
    assert (oatmeal["food_id"], oatmeal["weight_id"]) == ("111", "6100000001")
    assert oatmeal["foods"][0]["name"] == "Rolled Oats"
    assert oatmeal["totals"]["calories"] == 234
    assert oatmeal["totals"]["protein"] == 6.1
    assert meals[1]["totals"]["sugar"] == 0


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(302, headers={"Location": "/account/logout"}),
        FakeResponse(401, json_data={"error": "unauthorized"}, headers=JSON_HEADERS),
        FakeResponse(200, text="<html></html>", headers={"Content-Type": "text/html"}),
    ],
)
def test_signed_out_services_response_is_an_auth_error(response):
    client = FakeClient()
    client.session.route("GET", "api/services/users/meals/mine", response)

    with pytest.raises(RuntimeError) as raised:
        get_service_json(client, "users/meals/mine")

    assert "isn't signed in" in str(raised.value)
    assert mfp_client.is_auth_error(raised.value)


def test_recipes_page_by_offset_until_a_short_page():
    client = FakeClient()
    client.session.route(
        "GET", "recipes?offset=0", service_response("recipes_page1.json")
    )
    client.session.route(
        "GET", "recipes?offset=10", service_response("recipes_page2.json")
    )

    fetched = recipes.fetch_recipes(client)

    assert len(fetched) == 11
    assert [call[1].rsplit("=", 1)[1] for call in client.session.calls] == ["0", "10"]


def test_recipes_stop_when_offset_repeats_a_page():
    client = FakeClient()
    client.session.route(
        "GET", "recipes?offset=", service_response("recipes_page1.json")
    )

    assert len(recipes.fetch_recipes(client)) == 10
    assert len(client.session.calls) == 2


def test_recipe_summary_with_and_without_ingredients():
    item = fixture_json("recipes_page1.json")["items"][0]

    summary = recipes.recipe_summary(item)
    assert summary["name"] == "Chicken Rice Bowl"
    assert summary["servings"] == 2.0
    assert summary["nutrition"]["calories"] == 400.0
    assert summary["nutrition"]["fiber"] == 4.0
    noisy = dict(item, nutritional_contents={"protein": 32.65999984741211})
    assert recipes.recipe_summary(noisy)["nutrition"]["protein"] == 32.7
    assert summary["ingredient_count"] == 1
    assert "ingredients" not in summary

    detailed = recipes.recipe_summary(item, include_ingredients=True)
    assert detailed["ingredients"] == [
        {
            "text": "8 oz chicken breast",
            "food": "Chicken Breast",
            "brand": "Generic",
            "servings": 2.0,
            "serving": "4 oz",
        }
    ]


def test_favorites_rows_carry_diary_ids_and_servings():
    client = client_with(("food/load_my_foods", favorites_response("my_foods")))

    rows = favorites.load(client, "my_foods")

    assert rows[0] == {
        "name": "Acme - Trail Mix Bar",
        "food_id": "5200000001",
        "weight_id": "6200000001",
        "servings": [
            {"weight_id": "6200000001", "serving": "1 bar"},
            {"weight_id": "6200000002", "serving": "0.5 bar"},
        ],
    }
    assert client.session.calls[0][2]["allow_redirects"] is False


def test_favorites_default_to_the_selected_serving():
    client = client_with(("food/load_recent", favorites_response("recent")))
    assert favorites.load(client, "recent")[0]["weight_id"] == "6300000002"


def test_favorites_reject_an_unknown_source():
    with pytest.raises(ValueError, match="source must be one of"):
        favorites.load(FakeClient(), "pantry")


def test_favorites_signed_out_redirect_is_an_auth_error():
    client = client_with(
        (
            "food/load_recipes",
            FakeResponse(302, headers={"Location": "/account/logout"}),
        )
    )
    with pytest.raises(RuntimeError) as raised:
        favorites.load(client, "recipes")
    assert mfp_client.is_auth_error(raised.value)


def test_matching_prefers_an_exact_name_over_partial_matches():
    client = client_with(("food/load_recipes", favorites_response("recipes")))
    rows = favorites.load(client, "recipes")

    assert [row["name"] for row in favorites.matching(rows, "turkey burger")] == [
        "Turkey Burger"
    ]
    assert [row["name"] for row in favorites.matching(rows, "turkey")] == [
        "Turkey Burger",
        "Spicy Turkey Burger",
    ]
    assert favorites.matching(rows, "salmon") == []
