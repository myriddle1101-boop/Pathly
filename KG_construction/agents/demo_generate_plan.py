from __future__ import annotations

import json

from agents.planning_agent import PlanningAgent
from infra.profile_store import ProfileStore


def ask_user_id() -> str:
    return input("请输入用户 ID（回车使用 demo_undergrad_1）：\n> ").strip() or "demo_undergrad_1"


def ask_goal_text() -> str:
    return input("请输入学习目标（回车使用画像中的目标）：\n> ").strip()


def ask_output_path() -> str:
    return input("请输入输出 JSON 路径（回车使用 planning_output.json）：\n> ").strip() or "planning_output.json"


def main() -> None:
    store = ProfileStore()
    user_id = ask_user_id()
    profile = store.get_profile(user_id)
    if profile is None:
        raise ValueError(f"未找到用户画像: {user_id}")

    goal_text = ask_goal_text() or profile.goal_text
    output_path = ask_output_path()

    agent = PlanningAgent()
    plan = agent.generate_plan(goal_text=goal_text, profile=profile)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"[OK] 课程计划已生成: {output_path}")


if __name__ == "__main__":
    main()
