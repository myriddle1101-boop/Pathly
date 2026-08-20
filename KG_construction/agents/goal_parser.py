from __future__ import annotations

import json
import os
import re

from openai import OpenAI

from env_loader import load_project_env
from agents.planning_schema import PlanningRequest
from infra.config import DEFAULT_LLM_MODEL

load_project_env()


COMMON_FILLER = {
    "i",
    "want",
    "to",
    "learn",
    "study",
    "understand",
    "in",
    "within",
    "days",
    "day",
    "for",
    "the",
    "a",
    "an",
    "and",
    "of",
    "per",
    "every",
    "each",
}

CHINESE_FILLER_PHRASES = [
    "我想在",
    "我想了解",
    "我想学习",
    "我想学",
    "想学",
    "我想",
    "想要",
    "希望",
    "内学习",
    "学习",
    "了解",
    "掌握",
    "在",
    "每天",
    "每周",
    "之内",
    "以内",
]


class GoalParser:
    KNOWN_CONCEPT_PATTERNS = [
        (r"(?i)(?:\brag\b|retrieval[- ]augmented generation|检索增强生成)", "Retrieval-Augmented Generation (RAG)"),
        (r"(?i)(?:\btransformers?\b|变换器模型)", "Transformers"),
        (r"(?i)(?:\bmachine learning\b|\bml\b|机器学习)", "Machine Learning"),
        (r"(?i)(?:\bneural networks?\b|神经网络)", "Neural Networks"),
        (r"(?i)(?:\blarge language models?\b|\bllms?\b|大语言模型)", "Large Language Models"),
    ]

    def __init__(self, model_name: str = DEFAULT_LLM_MODEL):
        self.model_name = model_name

    def parse(
        self,
        goal_text: str,
        default_days: int = 7,
        default_daily_minutes: int = 60,
    ) -> PlanningRequest:
        explicit = self._extract_known_concept(goal_text)
        if explicit:
            return PlanningRequest(
                goal_text=goal_text,
                target_concepts=[explicit],
                requested_days=self._extract_days(goal_text) or default_days,
                daily_minutes=self._extract_daily_minutes(goal_text) or default_daily_minutes,
                constraints=[],
                learning_style_hints=[],
            )
        try:
            return self._parse_with_llm(goal_text, default_days, default_daily_minutes)
        except Exception:
            return self._parse_with_rules(goal_text, default_days, default_daily_minutes)

    def _extract_known_concept(self, goal_text: str) -> str | None:
        for pattern, canonical in self.KNOWN_CONCEPT_PATTERNS:
            if re.search(pattern, goal_text):
                return canonical
        return None

    def _client(self) -> OpenAI:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("未检测到 OPENAI_API_KEY")
        return OpenAI(api_key=api_key)

    def _parse_with_llm(
        self,
        goal_text: str,
        default_days: int,
        default_daily_minutes: int,
    ) -> PlanningRequest:
        prompt = f"""
You are extracting a structured planning request for a learning planner.

User goal:
{goal_text}

Return JSON only:
{{
  "goal_text": "...",
  "target_concepts": ["one primary technical concept"],
  "requested_days": {default_days},
  "daily_minutes": {default_daily_minutes},
  "constraints": ["...", "..."],
  "learning_style_hints": ["...", "..."]
}}

Rules:
- Return exactly one primary technical concept explicitly requested by the user.
- Do not expand the goal into a syllabus, prerequisites, applications, architectures, or model examples.
- Do not invent constraints or learning preferences. Only include constraints or hints literally stated by the user.
- requested_days must be an integer >= 1.
- daily_minutes must be an integer >= 15.
- If time is not given, use defaults.
"""
        client = self._client()
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(response.choices[0].message.content)
        return PlanningRequest(
            goal_text=data.get("goal_text", goal_text),
            target_concepts=self._clean_target_concepts(data.get("target_concepts", []), goal_text)[:1],
            requested_days=max(1, int(data.get("requested_days", default_days))),
            daily_minutes=max(15, int(data.get("daily_minutes", default_daily_minutes))),
            constraints=[],
            learning_style_hints=[],
        )

    def _parse_with_rules(
        self,
        goal_text: str,
        default_days: int,
        default_daily_minutes: int,
    ) -> PlanningRequest:
        extracted_days = self._extract_days(goal_text)
        extracted_daily_minutes = self._extract_daily_minutes(goal_text)
        requested_days = extracted_days or default_days
        daily_minutes = extracted_daily_minutes or default_daily_minutes
        explicit = self._extract_known_concept(goal_text)
        targets = [explicit] if explicit else self._clean_target_concepts([], goal_text)
        constraints = []
        if extracted_days is None:
            constraints.append("days_defaulted")
        if extracted_daily_minutes is None:
            constraints.append("daily_minutes_defaulted")
        return PlanningRequest(
            goal_text=goal_text,
            target_concepts=targets,
            requested_days=requested_days,
            daily_minutes=daily_minutes,
            constraints=constraints,
            learning_style_hints=[],
        )

    def _extract_days(self, goal_text: str) -> int | None:
        patterns = [
            r"(\d+)\s*\u5929",
            r"(\d+)\s*days?",
            r"(\d+)\s*day",
        ]
        lowered = goal_text.lower()
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                return int(match.group(1))
        return None

    def _extract_daily_minutes(self, goal_text: str) -> int | None:
        lowered = goal_text.lower()
        patterns = [
            (r"\u6bcf\u5929\s*(\d+)\s*\u5206\u949f", 1),
            (r"\u6bcf\u5929\s*(\d+)\s*\u5c0f\u65f6", 60),
            (r"(\d+)\s*\u5206\u949f", 1),
            (r"(\d+)\s*min(?:ute)?s?", 1),
            (r"(\d+)\s*\u5c0f\u65f6", 60),
            (r"(\d+)\s*hours?", 60),
        ]
        for pattern, multiplier in patterns:
            match = re.search(pattern, lowered)
            if match:
                return int(match.group(1)) * multiplier
        return None

    def _clean_target_concepts(self, concepts: list[str], goal_text: str) -> list[str]:
        cleaned = []
        for concept in concepts:
            item = str(concept).strip()
            if item:
                cleaned.append(item)
        if cleaned:
            return cleaned

        if self._contains_cjk(goal_text):
            candidate = goal_text
            candidate = re.sub(r"\d+\s*\u5929", " ", candidate)
            candidate = re.sub(r"\u6bcf\u5929\s*\d+\s*\u5206\u949f", " ", candidate)
            candidate = re.sub(r"\u6bcf\u5929\s*\d+\s*\u5c0f\u65f6", " ", candidate)
            candidate = re.sub(r"\d+\s*\u5206\u949f", " ", candidate)
            candidate = re.sub(r"\d+\s*\u5c0f\u65f6", " ", candidate)
            candidate = re.sub(r"[\uFF0C\u3002\uFF01\uFF1F\uFF1B\uFF1A\u3001,.!?;:()]", " ", candidate)
            candidate = re.sub(r"\s+", "", candidate)
            for phrase in CHINESE_FILLER_PHRASES:
                candidate = candidate.replace(phrase, "")
            candidate = re.sub(
                r"^(?:\u6211\u60f3\u5728|\u6211\u60f3\u4e86\u89e3|\u6211\u60f3\u5b66\u4e60|\u5185\u5b66\u4e60|\u6211\u60f3|\u60f3\u8981|\u5e0c\u671b|\u5b66\u4e60|\u4e86\u89e3)+",
                "",
                candidate,
            )
            candidate = candidate.strip()
            if candidate:
                return [candidate]
            return [goal_text.strip()]

        candidate_text = re.sub(r"[,.!?;:()]", " ", goal_text)
        candidate_text = re.sub(r"\d+\s*(days?|minutes?|hours?|mins?)", " ", candidate_text, flags=re.I)
        tokens = [token for token in candidate_text.split() if token.lower() not in COMMON_FILLER]
        if not tokens:
            return [goal_text.strip()]
        return [" ".join(tokens[:6]).strip()]

    def _clean_text_list(self, items: list[str]) -> list[str]:
        cleaned = []
        for item in items:
            value = str(item).strip()
            if value:
                cleaned.append(value)
        return cleaned

    def _contains_cjk(self, text: str) -> bool:
        return any("\u4e00" <= ch <= "\u9fff" for ch in text)
