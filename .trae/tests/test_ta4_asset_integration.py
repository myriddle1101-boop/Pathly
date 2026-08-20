from source_grounded_v4_generator import generate_source_grounded_lecture_v4
from test_source_grounded_v4_s4 import _daily, _links, _live_content, _v3


def test_live_request_contains_published_tiered_assets():
    captured = []

    def capture(request):
        captured.append(request)
        return _live_content(request)

    generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="asset-test",
        profile={
            "cognitive_traits": {"mathematical_ability": 2, "programming_ability": 2, "abstract_thinking": 2, "logical_reasoning": 2},
            "affective_defaults": {"interest_tags": ["no_preference"], "preferred_examples": ["daily_life"], "learning_style": "example"},
        }, model_generator=capture,
    )
    assert captured
    assets = captured[0]["teaching_assets"]
    assert {item["asset_type"] for item in assets} >= {"foundation_intuition", "foundation_worked_example", "visual_or_coordinate_description"}
    assert captured[0]["asset_manifest_version"] == "ta-golden-v2"
