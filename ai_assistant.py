from __future__ import annotations

import os
from typing import List, Optional

import anthropic

from logger_config import setup_logger
from rag.retriever import Retriever

logger = setup_logger("ai_assistant")

_SYSTEM_PROMPT = (
    "You are PawPal+, a knowledgeable and warm pet care assistant. "
    "You help pet owners understand and optimize their pet's daily care schedule.\n\n"
    "When given a pet's schedule and relevant care documentation:\n"
    "1. Explain WHY each task matters for this specific pet (species + age)\n"
    "2. Give practical, actionable tips grounded in the provided documentation\n"
    "3. Note any important timing or sequencing considerations\n"
    "4. Keep your tone friendly, specific, and encouraging\n\n"
    "Base all explanations strictly on the provided documentation. "
    "If a topic is not covered in the documentation, say so rather than speculating."
)


class AIAssistant:
    """
    Combines RAG document retrieval with the Claude API to produce
    personalized, evidence-based explanations of pet care schedules.

    Usage
    -----
    assistant = AIAssistant()          # reads ANTHROPIC_API_KEY from env
    text = assistant.explain_schedule(
        pet_name="Mochi", species="dog", age_years=3,
        schedule_items=[{"name": "Morning walk", "duration": 30, "priority": 8, "category": "exercise"}],
        time_available=60,
    )
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required. "
                "Set it in a .env file or pass api_key= to AIAssistant()."
            )
        self.client = anthropic.Anthropic(api_key=key)
        self.retriever = Retriever()
        logger.info("AIAssistant initialised")

    def explain_schedule(
        self,
        pet_name: str,
        species: str,
        age_years: float,
        schedule_items: List[dict],
        time_available: int,
    ) -> str:
        """
        Return an AI-generated, RAG-enhanced explanation of *schedule_items*.

        Each dict in *schedule_items* must have:
            name (str), duration (int), priority (int)
        Optionally: category (str)

        The retriever is queried with the pet's species and task categories so
        that relevant knowledge-base chunks are injected into the prompt before
        the Claude API call is made.
        """
        categories = " ".join(
            item.get("category", "general") for item in schedule_items
        )
        query = f"{species} {categories} care schedule"
        docs = self.retriever.retrieve(query, top_k=4)
        context = "\n\n---\n\n".join(docs) or "No specific documentation available."

        task_lines = "\n".join(
            "  • {name} — {duration} min, priority {priority}{cat}".format(
                **item,
                cat=f", category: {item['category']}" if item.get("category") else "",
            )
            for item in schedule_items
        )

        user_prompt = (
            f"Pet: {pet_name} ({species}, {age_years} years old)\n"
            f"Owner's available time today: {time_available} minutes\n\n"
            f"Today's scheduled tasks:\n{task_lines}\n\n"
            "---\n"
            f"Relevant pet care documentation:\n{context}\n\n"
            "---\n"
            f"Please explain why this is a good schedule for {pet_name}. "
            "Use the documentation as your reference and give practical tips "
            f"for each task, keeping in mind that {pet_name} is a "
            f"{age_years}-year-old {species}."
        )

        logger.info(
            "Calling Claude API for %s (%s) — %d tasks, %d doc chunks",
            pet_name,
            species,
            len(schedule_items),
            len(docs),
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text
            logger.info(
                "Claude response received: %d chars (input tokens: %s, cache: %s)",
                len(text),
                getattr(response.usage, "input_tokens", "?"),
                getattr(response.usage, "cache_read_input_tokens", "n/a"),
            )
            return text
        except anthropic.APIError as exc:
            logger.error("Claude API error: %s", exc)
            raise
