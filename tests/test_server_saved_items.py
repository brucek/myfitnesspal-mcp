import asyncio
import datetime
import json

import pytest
from conftest import FIXTURES, FakeClient, FakeResponse

from myfitnesspal_mcp import server
from myfitnesspal_mcp.store import Store

JSON_HEADERS = {"Content-Type": "application/json"}
HTML_HEADERS = {"Content-Type": "text/html"}


class FakeContext:
    async def info(self, message):
        pass


def favorites_response(kind):
    return FakeResponse(
        text=(FIXTURES / f"favorites_{kind}.html").read_text(), headers=HTML_HEADERS
    )


def fixture_response(name):
    return FakeResponse(
        json_data=json.loads((FIXTURES / name).read_text()), headers=JSON_HEADERS
    )


@pytest.fixture
def saved_items(tmp_path, monkeypatch):
    store = Store(tmp_path / "server.db")
    client = FakeClient()
    client.session.route(
        "GET", "api/services/users/foods/mine", fixture_response("my_foods.json")
    )
    client.session.route(
        "GET", "api/services/users/meals/mine", fixture_response("my_meals.json")
    )
    client.session.route(
        "GET", "recipes?offset=0", fixture_response("recipes_page1.json")
    )
    client.session.route(
        "GET", "recipes?offset=10", fixture_response("recipes_page2.json")
    )
    for kind in ("recipes", "meals", "my_foods", "recent"):
        client.session.route("GET", f"food/load_{kind}", favorites_response(kind))
    polls, refreshed = [], []
    monkeypatch.setattr(server, "_store", store)
    monkeypatch.setattr(server.mfp_client, "get_client", lambda: client)
    monkeypatch.setattr(
        server.sync, "poll", lambda store, client, **kwargs: polls.append(kwargs)
    )
    monkeypatch.setattr(
        server.sync, "refresh_day", lambda store, client, day: refreshed.append(day)
    )
    return store, polls, refreshed


def run(coro):
    return asyncio.run(coro)


def test_recent_foods_reads_the_window_after_syncing(saved_items):
    store, polls, refreshed = saved_items
    today = datetime.date.today()
    store.replace_diary(
        today.isoformat(), [{"meal": "Breakfast", "name": "Oats", "calories": 150}]
    )
    store.replace_diary(
        (today - datetime.timedelta(days=20)).isoformat(),
        [{"meal": "Lunch", "name": "Old Soup", "calories": 200}],
    )

    result = run(server.fitness_recent_foods(days=14, ctx=FakeContext()))

    assert result["total"] == 1
    assert result["foods"][0]["name"] == "Oats"
    assert result["start"] == (today - datetime.timedelta(days=13)).isoformat()
    assert polls == [{"days": 14, "force": False}]
    assert refreshed == [today - datetime.timedelta(days=1), today]


def test_recent_foods_forces_a_gap_fill_past_the_sync_window(saved_items):
    _, polls, _ = saved_items
    run(server.fitness_recent_foods(days=90, ctx=FakeContext()))
    assert polls == [{"days": 90, "force": True}]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"days": 0}, "days must be between"),
        ({"days": 400}, "days must be between"),
        ({"limit": 0}, "limit must be at least 1"),
    ],
)
def test_recent_foods_validates_arguments(saved_items, kwargs, message):
    with pytest.raises(ValueError, match=message):
        run(server.fitness_recent_foods(ctx=FakeContext(), **kwargs))


def test_list_my_foods_limits_and_counts(saved_items):
    result = run(server.fitness_list_my_foods(limit=1, ctx=FakeContext()))
    assert result["total"] == 2
    assert [food["name"] for food in result["foods"]] == ["Trail Mix Bar"]


def test_list_my_meals_filters_by_name(saved_items):
    result = run(server.fitness_list_my_meals(query="turkey", ctx=FakeContext()))
    assert result["total"] == 1
    assert result["meals"][0]["name"] == "Turkey sandwich lunch"


def test_list_recipes_filters_limits_and_adds_ingredients(saved_items):
    everything = run(server.fitness_list_recipes(limit=3, ctx=FakeContext()))
    assert everything["total"] == 11
    assert len(everything["recipes"]) == 3
    assert "ingredients" not in everything["recipes"][0]

    bowl = run(
        server.fitness_list_recipes(
            query="chicken bowl", include_ingredients=True, ctx=FakeContext()
        )
    )
    assert bowl["total"] == 1
    assert bowl["recipes"][0]["name"] == "Chicken Rice Bowl"
    assert bowl["recipes"][0]["food_id"] == "5000000001"
    assert bowl["recipes"][0]["weight_id"] == "6000000001"
    assert bowl["recipes"][0]["ingredients"][0]["food"] == "Chicken Breast"


def test_list_tools_reject_a_zero_limit(saved_items):
    for tool in (
        server.fitness_list_my_foods,
        server.fitness_list_my_meals,
        server.fitness_list_recipes,
    ):
        with pytest.raises(ValueError, match="limit must be at least 1"):
            run(tool(limit=0, ctx=FakeContext()))


@pytest.fixture
def logged(saved_items, monkeypatch):
    calls = []

    def fake_log_exact(client, food, day, meal, *, quantity, page=None):
        calls.append({"food": food, "meal": meal, "quantity": quantity})
        return {
            "logged": food["name"],
            "added_entries": [{"meal": meal.title(), "name": food["name"]}],
            "date": day.isoformat(),
        }

    monkeypatch.setattr(server.food_logging, "log_exact", fake_log_exact)
    return calls


def test_log_food_from_a_saved_recipe_by_name(logged):
    result = run(
        server.fitness_log_food(
            query="Turkey Burger", source="recipes", meal="lunch", ctx=FakeContext()
        )
    )

    assert result["logged"] == "Turkey Burger"
    assert result["source"] == "recipes"
    assert logged == [
        {
            "food": {
                "food_id": "5000000002",
                "weight_id": "6000000002",
                "name": "Turkey Burger",
            },
            "meal": "lunch",
            "quantity": 1.0,
        }
    ]


def test_log_food_from_a_saved_meal_and_my_food_serving(logged):
    run(server.fitness_log_food(query="oatmeal", source="meals", ctx=FakeContext()))
    run(
        server.fitness_log_food(
            query="trail mix",
            source="my_foods",
            serving=2,
            quantity=3,
            ctx=FakeContext(),
        )
    )

    assert logged[0]["food"]["food_id"] == "111"
    assert logged[1]["food"]["weight_id"] == "6200000002"
    assert logged[1]["quantity"] == 3


def test_log_food_from_source_returns_choices_when_ambiguous(logged):
    result = run(
        server.fitness_log_food(query="turkey", source="recipes", ctx=FakeContext())
    )

    assert result["needs_choice"] is True
    assert [match["name"] for match in result["matches"]] == [
        "Turkey Burger",
        "Spicy Turkey Burger",
    ]
    assert logged == []


def test_log_food_from_source_lists_names_when_nothing_matches(logged):
    with pytest.raises(server.food_logging.NoSavedMatch) as raised:
        run(server.fitness_log_food(query="salmon", source="meals", ctx=FakeContext()))

    assert "Oatmeal breakfast, Turkey sandwich lunch" in str(raised.value)
    assert not server.mfp_client.is_auth_error(raised.value)
    assert logged == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"source": "recipes"}, "source needs query"),
        ({"source": "pantry", "query": "x"}, "source must be one of"),
        (
            {"source": "my_foods", "query": "energy gel", "serving": 2},
            "serving must be between 1 and 1",
        ),
    ],
)
def test_log_food_from_source_validates_arguments(logged, kwargs, message):
    with pytest.raises(ValueError, match=message):
        run(server.fitness_log_food(ctx=FakeContext(), **kwargs))
    assert logged == []
