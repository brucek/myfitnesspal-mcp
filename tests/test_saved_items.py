import json

import pytest
from conftest import FIXTURES, FakeClient, FakeResponse

from myfitnesspal_mcp import mfp_client, my_foods, my_meals, recipes
from myfitnesspal_mcp.mfp_web import get_service_json, plain_text

JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}


def fixture_json(name):
    return json.loads((FIXTURES / name).read_text())


def service_response(name):
    return FakeResponse(json_data=fixture_json(name), headers=JSON_HEADERS)


def test_plain_text_collapses_non_breaking_spaces():
    assert plain_text("Trail Mix  Bar ") == "Trail Mix Bar"
    assert plain_text(None) is None


def test_my_foods_lists_live_foods_with_nutrition_per_base_serving():
    client = FakeClient()
    client.session.route(
        "GET", "api/services/users/foods/mine", service_response("my_foods.json")
    )

    foods = my_foods.list_my_foods(client)

    assert [food["name"] for food in foods] == ["Trail Mix Bar", "Energy Gel"]
    bar = foods[0]
    assert bar["food_id"] == "900000000000001"
    assert bar["brand"] == "Acme"
    assert bar["nutrition_per"] == "1 bar"
    assert bar["servings"] == ["1 bar", "0.5 bar"]
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


def test_my_foods_passes_the_query_to_mfp_search():
    client = FakeClient()
    client.session.route(
        "GET", "api/services/users/foods/mine", service_response("my_foods.json")
    )

    my_foods.list_my_foods(client, "trail mix")

    method, url, kwargs = client.session.calls[0]
    assert url.endswith("api/services/users/foods/mine?search=trail%20mix")
    assert kwargs["allow_redirects"] is False


def test_my_meals_lists_foods_and_totals():
    client = FakeClient()
    client.session.route(
        "GET", "api/services/users/meals/mine", service_response("my_meals.json")
    )

    meals = my_meals.list_my_meals(client)

    assert [meal["name"] for meal in meals] == [
        "Oatmeal breakfast",
        "Turkey sandwich lunch",
    ]
    oatmeal = meals[0]
    assert oatmeal["meal_id"] == 111
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
