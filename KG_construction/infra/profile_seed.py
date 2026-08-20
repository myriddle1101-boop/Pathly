from infra.profile_schema import LearnerProfile
from infra.profile_store import ProfileStore


def seed_profiles() -> None:
    store = ProfileStore()
    profiles = [
        LearnerProfile(
            user_id="demo_undergrad_1",
            name="Demo Undergraduate",
            academic_level="undergraduate",
            domain="machine learning",
            goal_text="I want to learn neural networks in 7 days.",
            target_days=7,
            daily_minutes=90,
            prior_knowledge_level=2,
            math_foundation=2,
            programming_foundation=4,
            self_regulation=3,
            interest_tags=["computer vision", "applications"],
            preferred_style="example_first",
            motivation_level=4,
            confidence_level=3,
            anxiety_level=2,
            known_topics=["Linear Regression", "Classification"],
            skill_tree={"Linear Regression": 0.85, "Classification": 0.75, "Probability": 0.55},
            preferred_examples=["real world case studies", "visual explanations"],
            pace_preference="medium",
            mastery_vector={"Linear Regression": 0.8, "Classification": 0.75},
            completed_topics=["Linear Regression"],
            current_day=1,
        ),
        LearnerProfile(
            user_id="demo_undergrad_2",
            name="Demo Cautious Learner",
            academic_level="undergraduate",
            domain="machine learning",
            goal_text="I need a 10-day plan for deep learning basics.",
            target_days=10,
            daily_minutes=60,
            prior_knowledge_level=1,
            math_foundation=2,
            programming_foundation=2,
            self_regulation=4,
            interest_tags=["healthcare", "ethics"],
            preferred_style="step_by_step",
            motivation_level=4,
            confidence_level=2,
            anxiety_level=4,
            known_topics=[],
            skill_tree={"Probability": 0.35, "Matrix Multiplication": 0.2},
            preferred_examples=["worked examples", "simple analogies"],
            pace_preference="slow",
            mastery_vector={},
            completed_topics=[],
            current_day=1,
        ),
    ]
    for profile in profiles:
        store.upsert_profile(profile)
    print(f"[OK] ??? demo ??????: {len(profiles)}")


if __name__ == "__main__":
    seed_profiles()
