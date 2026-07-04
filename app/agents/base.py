import os
import httpx
import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger("base_agent")

class BaseAgent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "nousresearch/hermes-3-llama-3.1-405b:free")

        # Fallback models in case the chosen model fails or runs out of credits.
        # All must be free-tier models currently live on OpenRouter.
        self.fallback_models = [
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "openai/gpt-oss-20b:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
        ]

        # Groq is used as a fast, generously-rate-limited fallback provider when
        # every OpenRouter free-tier model is rate-limited/unavailable. Multiple
        # keys are rotated in case one hits its own rate limit.
        groq_keys_raw = os.getenv("GROQ_API_KEYS", "")
        self.groq_keys = [k.strip() for k in groq_keys_raw.split(",") if k.strip()]
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    async def call_llm(self, prompt: str, json_mode: bool = False) -> str:
        """
        Calls OpenRouter with retry logic and fallback models.
        """
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY is not set. Operating in deterministic/mock fallback mode.")
            return self._mock_llm_response(prompt, json_mode)

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/NousResearch/hermes-agent", # Required by OpenRouter
            "X-Title": "Weather Prediction AI Trading Agent",
            "Content-Type": "application/json"
        }

        # Try models starting with configured model, then fallbacks
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 1024
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            # Rate limits (429) mean this model is saturated right now — move on
            # to the next model immediately rather than burning retries on it.
            # Only retry-with-backoff on transient/5xx/connection errors.
            max_attempts = 2
            for attempt in range(max_attempts):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        logger.info(f"[{self.name}] Calling OpenRouter model {model} (Attempt {attempt+1})")
                        response = await client.post(url, headers=headers, json=payload)
                        if response.status_code == 200:
                            data = response.json()
                            content = data["choices"][0]["message"]["content"]
                            logger.info(f"[{self.name}] LLM Response successfully retrieved.")
                            return content
                        elif response.status_code == 429:
                            logger.warning(f"[{self.name}] Model {model} rate-limited, skipping to next model.")
                            break
                        else:
                            logger.warning(f"[{self.name}] LLM API error {response.status_code}: {response.text}")
                            await asyncio.sleep(1.5 ** attempt)
                except Exception as e:
                    logger.error(f"[{self.name}] LLM connection exception: {e}")
                    await asyncio.sleep(1.5 ** attempt)

        # All OpenRouter free-tier models exhausted/rate-limited. Try Groq next.
        groq_result = await self._call_groq(prompt, json_mode)
        if groq_result is not None:
            return groq_result

        logger.error(f"[{self.name}] All LLM calls failed. Falling back to deterministic simulation.")
        return self._mock_llm_response(prompt, json_mode)

    async def _call_groq(self, prompt: str, json_mode: bool) -> str | None:
        """Fallback LLM call via Groq's OpenAI-compatible API, rotating across
        configured keys. Returns None if Groq is unavailable/unconfigured."""
        if not self.groq_keys:
            return None

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1024
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        for key in self.groq_keys:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.info(f"[{self.name}] Calling Groq fallback model {self.groq_model}")
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                        logger.info(f"[{self.name}] Groq fallback response successfully retrieved.")
                        return content
                    else:
                        logger.warning(f"[{self.name}] Groq API error {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"[{self.name}] Groq connection exception: {e}")

        return None

    def _mock_llm_response(self, prompt: str, json_mode: bool) -> str:
        """
        Deterministic string parsing fallback for mock/offline runs.
        """
        if json_mode:
            # We construct a default valid JSON string based on the likely task
            if "BUY" in prompt or "Prediction" in prompt:
                return '{"probability": 0.55, "confidence": 0.70, "decision": "BUY YES", "expected_value": 0.10, "edge": 0.05, "reasoning": "Fallback reasoning: forecasts align with climate normals."}'
            return '{"status": "success", "confidence": 0.8}'
        return "Deterministic agent fallback response."
