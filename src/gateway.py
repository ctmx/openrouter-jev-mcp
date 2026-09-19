"""
src/gateway.py

General-purpose local gateway and client for TypeSafe Jev.
Supports:
  - OpenRouter Decisions API (POST https://openrouter.ai/api/alpha/decisions)
  - Native TypeSafe System One API (POST https://api.typesafe.ai/v1/systemone)
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Union
import httpx

DEFAULT_OPENROUTER_MODEL = "~typesafe/jev-latest"
DEFAULT_TYPESAFE_MODEL = "jev-latest"


@dataclass
class DecisionResult:
    model: str
    answers: Dict[str, Any]
    usage: Dict[str, Any]
    raw_response: Dict[str, Any]


class JevGateway:
    """
    Reusable local gateway for evaluating structured Jev decisions.
    """

    def __init__(
        self,
        openrouter_api_key: Optional[str] = None,
        typesafe_api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.openrouter_api_key = openrouter_api_key or os.environ.get("OPENROUTER_API_KEY")
        self.typesafe_api_key = typesafe_api_key or os.environ.get("TYPESAFE_API_KEY")
        self.use_openrouter = bool(self.openrouter_api_key and not self.typesafe_api_key)
        
        if self.use_openrouter:
            self.model = model or DEFAULT_OPENROUTER_MODEL
        else:
            self.model = model or DEFAULT_TYPESAFE_MODEL

    def evaluate(
        self,
        state: Union[str, Dict[str, Any], List[Any]],
        questions: Dict[str, Any]
    ) -> DecisionResult:
        """
        Evaluates an arbitrary map of Choice, Score, and Noul questions against state.
        """
        # Format questions for JSON transport
        serialized_questions = {}
        for q_id, q_data in questions.items():
            if hasattr(q_data, "model_dump"):
                serialized_questions[q_id] = q_data.model_dump(exclude_none=True)
            elif isinstance(q_data, dict):
                serialized_questions[q_id] = q_data
            else:
                serialized_questions[q_id] = {"instructions": str(q_data)}

        # Route 1: OpenRouter Decisions API
        if self.use_openrouter or not self.typesafe_api_key:
            if not self.openrouter_api_key:
                raise ValueError("Neither OPENROUTER_API_KEY nor TYPESAFE_API_KEY is configured.")
            
            url = "https://openrouter.ai/api/alpha/decisions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "state": state,
                "questions": serialized_questions
            }
            response = httpx.post(url, headers=headers, json=payload, timeout=20.0)
            response.raise_for_status()
            data = response.json()
            return DecisionResult(
                model=data.get("model", self.model),
                answers=data.get("answers", {}),
                usage=data.get("usage", {}),
                raw_response=data
            )

        # Route 2: Native TypeSafe SDK
        from typesafe_sdk import TypeSafeClient
        client = TypeSafeClient(api_key=self.typesafe_api_key, model=self.model)
        resp = client.system_one(state=state, questions=questions)
        return DecisionResult(
            model=resp.model or self.model,
            answers=resp.answers,
            usage={"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
            raw_response={"answers": resp.answers}
        )

    def check(self, state: Any, proposition: str) -> Dict[str, Any]:
        """
        Fast single yes/no proposition (Noul).
        """
        q = {
            "check": {
                "type": "noul",
                "instructions": proposition
            }
        }
        res = self.evaluate(state, q)
        return res.answers.get("check", {})

    def choice(
        self,
        state: Any,
        instructions: str,
        options: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Fast single categorical choice from a closed set.
        """
        q = {
            "selection": {
                "type": "choice",
                "instructions": instructions,
                "criteria": options
            }
        }
        res = self.evaluate(state, q)
        return res.answers.get("selection", {})

    def score(
        self,
        state: Any,
        instructions: str,
        rubric: List[str]
    ) -> Dict[str, Any]:
        """
        Fast single rubric score.
        """
        q = {
            "score": {
                "type": "score",
                "instructions": instructions,
                "criteria": rubric
            }
        }
        res = self.evaluate(state, q)
        return res.answers.get("score", {})
