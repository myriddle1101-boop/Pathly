from agents.concept_expander import ConceptExpander
from infra.profile_schema import LearnerProfile


class FakeRepository:
    def __init__(self):
        self.topics = {
            "Foundation": {
                "id": "Foundation",
                "difficulty_level": 1,
                "estimated_learning_time": "400 min",
            },
            "Target": {
                "id": "Target",
                "difficulty_level": 1,
                "estimated_learning_time": "600 min",
            },
        }

    def get_topic(self, name):
        return self.topics.get(name)

    def get_prerequisites(self, name):
        return ["Foundation"] if name == "Target" else []


def profile(days=10, minutes=60):
    return LearnerProfile(
        user_id="capacity-user",
        name="Capacity User",
        academic_level="unspecified",
        domain="user-defined",
        goal_text="learn target",
        target_days=days,
        daily_minutes=minutes,
        prior_knowledge_level=2,
        math_foundation=3,
        programming_foundation=3,
        self_regulation=3,
        motivation_level=3,
        confidence_level=2,
        anxiety_level=2,
        pace_preference="medium",
    )


def test_capacity_first_estimate_uses_total_time_before_requested_days():
    result = ConceptExpander(FakeRepository()).expand(
        ordered_topics=["Foundation", "Target"],
        target_topics=["Target"],
        profile=profile(),
        requested_days=10,
        available_daily_minutes=60,
    )
    estimate = result["workload_estimate"]
    assert estimate["total_required_minutes"] == 1000
    assert estimate["recommended_daily_minutes"] == 100
    assert estimate["available_capacity_minutes"] == 600
    assert estimate["capacity_gap_minutes"] == -400
    assert estimate["additional_minutes_needed"] == 400
    assert estimate["capacity_status"] == "insufficient"
    assert estimate["minimum_recommended_days"] == 17
    assert estimate["is_final"] is False


def test_concept_units_are_bounded_and_preserve_real_concept_ids():
    result = ConceptExpander(FakeRepository()).expand(
        ordered_topics=["Foundation", "Target"],
        target_topics=["Target"],
        profile=profile(days=20),
        requested_days=20,
        available_daily_minutes=60,
    )
    units = result["concept_units"]
    assert sum(unit["estimated_minutes"] for unit in units) == 1000
    assert all(0 < unit["estimated_minutes"] <= 30 for unit in units)
    assert {unit["concept_id"] for unit in units} == {"Foundation", "Target"}
    assert result["concept_path"][1]["prerequisite_ids"] == ["Foundation"]
    assert result["workload_estimate"]["recommended_daily_minutes"] == 50
    assert result["workload_estimate"]["capacity_status"] == "excess"


def test_sparse_graph_is_reported_without_inventing_nodes():
    repo = FakeRepository()
    repo.get_prerequisites = lambda name: []
    result = ConceptExpander(repo).expand(
        ordered_topics=["Target"],
        target_topics=["Target"],
        profile=profile(),
        requested_days=7,
        available_daily_minutes=90,
    )
    assert [node["concept_id"] for node in result["concept_path"]] == ["Target"]
    assert result["coverage_warnings"]


def test_units_respect_daily_capacity_below_default_unit_size():
    result = ConceptExpander(FakeRepository()).expand(
        ordered_topics=["Foundation"],
        target_topics=["Foundation"],
        profile=profile(days=30, minutes=15),
        requested_days=30,
        available_daily_minutes=15,
    )
    assert all(unit["estimated_minutes"] <= 15 for unit in result["concept_units"])