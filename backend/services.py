import asyncio
import random
import time
from collections.abc import Callable

from google import genai
from google.genai import types

PROMPTS: dict[str, Callable[[str], str]] = {
    "qa": lambda text: f"""You are EduGenie, a careful learning assistant. Answer the student's question directly, then add a short explanation and an example when useful. Use clear language and say when a claim is uncertain.\n\nQuestion: {text}""",
    "explain": lambda text: f"""Explain the topic below to a beginner. Use these headings: Simple definition, Key ideas, Example, Quick recap. Keep the explanation clear and practical.\n\nTopic: {text}""",
    "summarize": lambda text: f"""Summarize the educational content below. Preserve the essential facts, remove repetition, and use concise bullet points followed by a one-sentence takeaway.\n\nContent: {text}""",
    "quiz": lambda text: f"""Create exactly three multiple-choice questions from the topic or passage below. Each question must have four options labelled A through D. Put the answer key and a one-line explanation after all questions. Do not use Markdown code fences.\n\nTopic or passage: {text}""",
    "recommendations": lambda text: f"""Create a practical learning path for the topic below. Organize it into Beginner, Intermediate, and Advanced stages. Include a suggested timeline, practice activities, useful resource types, and progress checks. Do not invent links.\n\nTopic: {text}""",
}

class EduGenieService:
    def __init__(self, api_key: str | None, gemini_model: str, fallback_models: list[str] | None = None, local_explanations: bool = False, request_timeout_ms: int = 30_000):
        http_options = types.HttpOptions(
            timeout=request_timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=1),
        )
        self.client = genai.Client(api_key=api_key, http_options=http_options) if api_key else None
        self.gemini_model = gemini_model
        self.fallback_models = [model.strip() for model in (fallback_models or []) if model.strip() and model.strip() != gemini_model]
        self.local_explanations = local_explanations
        self._local_pipeline = None

    @property
    def gemini_configured(self) -> bool:
        return self.client is not None

    @property
    def explanation_provider(self) -> str:
        return "MBZUAI/LaMini-Flan-T5-783M" if self.local_explanations else self.gemini_model

    async def run(self, task: str, user_input: str) -> tuple[str, str]:
        cleaned = user_input.strip()
        if task not in PROMPTS:
            raise ValueError("Unsupported learning task.")
        if not cleaned:
            raise ValueError("Please enter a question, topic, or passage.")
        if task == "explain" and self.local_explanations:
            return await asyncio.to_thread(self._run_local_explanation, cleaned)
        return await asyncio.to_thread(self._run_gemini, PROMPTS[task](cleaned))

    def _run_gemini(self, prompt: str) -> tuple[str, str]:
        if self.client is None:
            raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY and restart the server.")

        response = None
        model_used = self.gemini_model
        quota_error = None
        for model in [self.gemini_model, *self.fallback_models]:
            model_used = model
            for attempt in range(3):
                try:
                    response = self.client.models.generate_content(model=model, contents=prompt)
                    break
                except Exception as exc:
                    message = str(exc)
                    if "429" in message or "RESOURCE_EXHAUSTED" in message:
                        quota_error = exc
                        break
                    temporary = "503" in message or "UNAVAILABLE" in message or "high demand" in message.lower()
                    if not temporary:
                        raise RuntimeError(f"The AI service could not complete the request: {exc}") from exc
                    if attempt == 2:
                        break
                    time.sleep((2**attempt) + random.uniform(0.2, 0.8))
            if response is not None:
                break

        if response is None and quota_error is not None:
            raise RuntimeError(
                "The available Gemini models have reached their current quota. "
                "Please wait for the quota to reset or review your Gemini API plan."
            ) from quota_error
        if response is None:
            raise RuntimeError("Gemini is temporarily unavailable after several retries. Please try again shortly.")
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("The AI service returned an empty response. Please try again.")
        return text, model_used

    def _run_local_explanation(self, topic: str) -> tuple[str, str]:
        try:
            if self._local_pipeline is None:
                from transformers import pipeline
                self._local_pipeline = pipeline("text2text-generation", model="MBZUAI/LaMini-Flan-T5-783M")
            output = self._local_pipeline(PROMPTS["explain"](topic), max_new_tokens=384, do_sample=False)
            text = output[0]["generated_text"].strip()
        except ImportError as exc:
            raise RuntimeError("Local explanations require the optional 'transformers' and 'torch' packages.") from exc
        except Exception as exc:
            raise RuntimeError(f"The local explanation model could not complete the request: {exc}") from exc
        return text, "MBZUAI/LaMini-Flan-T5-783M"
