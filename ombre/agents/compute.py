"""
Ombre Compute Agent
===================
Intelligent model routing and inference execution.
Selects the optimal model and provider for every request based on
task type, cost, latency, and availability.

Supports: OpenAI, Anthropic, Groq, Mistral, Cohere
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


# Task type detection keywords
TASK_KEYWORDS = {
    "coding": [
        "code", "function", "class", "debug", "implement", "write a script",
        "python", "javascript", "typescript", "sql", "api", "algorithm",
        "fix this", "refactor", "unit test", "bug",
    ],
    "reasoning": [
        "analyze", "explain why", "compare", "evaluate", "assess", "think through",
        "what are the implications", "pros and cons", "should i", "decision",
        "strategy", "plan", "consider", "reason",
    ],
    "summarization": [
        "summarize", "tldr", "brief", "summary", "key points", "main points",
        "overview", "digest", "condense", "shorten",
    ],
    "analysis": [
        "analyze", "review", "examine", "study", "research", "investigate",
        "deep dive", "comprehensive", "thorough", "detailed analysis",
    ],
    "chat": [
        "hi", "hello", "thanks", "how are", "what do you think",
        "tell me about", "can you", "could you",
    ],
}


class ComputeAgent:
    """
    Ombre Compute Agent — Intelligent model routing.

    Routes each request to the best available model based on:
    - Task type detection
    - Provider availability
    - Cost optimization
    - Current latency profiles
    - Fallback chains for reliability
    """

    def __init__(self, config: Any):
        self.config = config
        self._provider_latencies: Dict[str, float] = {}
        self._provider_failures: Dict[str, int] = {}
        self._request_count = 0
        self._total_tokens = 0
        self._total_cost = 0.0

    def process(self, ctx: Any) -> Any:
        """
        Select the optimal model and provider for this request.

        Args:
            ctx: PipelineContext

        Returns:
            Modified context with selected_model and selected_provider set
        """
        ctx.activate_agent("compute")
        start = time.time()

        # Detect task type
        task_type = self._detect_task_type(ctx.get_effective_prompt())

        # Select model
        model, provider = self._select_model(ctx.model, task_type)
        ctx.selected_model = model
        ctx.selected_provider = provider
        ctx.model_rationale = f"task={task_type}, optimized for cost+quality"

        # Set fallback chain
        ctx.fallback_providers = self._get_fallback_chain(provider)

        # Estimate cost before inference
        estimated_input_tokens = ctx.original_token_count or 500
        cost_without_ombre = self._estimate_raw_cost(estimated_input_tokens, model)
        ctx.estimated_cost_without_ombre = cost_without_ombre

        elapsed = round((time.time() - start) * 1000, 2)
        logger.debug(
            f"Compute routing | request={ctx.request_id} | "
            f"model={model} | provider={provider} | task={task_type} | {elapsed}ms"
        )
        return ctx

    def infer(self, ctx: Any) -> Any:
        """
        Execute model inference with the selected provider.
        Handles retries and fallback to other providers.

        Args:
            ctx: PipelineContext with selected_model and selected_provider set

        Returns:
            Modified context with raw_response and token counts
        """
        self._request_count += 1
        start = time.time()

        # Build messages for inference
        messages = self._build_messages(ctx)
        system = ctx.system

        # Try primary provider first
        providers_to_try = [ctx.selected_provider] + ctx.fallback_providers

        last_error = None
        for provider in providers_to_try:
            try:
                response, tokens = self._call_provider(
                    provider=provider,
                    model=ctx.selected_model,
                    messages=messages,
                    system=system,
                    temperature=ctx.temperature,
                    max_tokens=ctx.max_tokens,
                )

                if provider != ctx.selected_provider:
                    logger.info(
                        f"Fallback succeeded | request={ctx.request_id} | "
                        f"provider={provider}"
                    )
                    ctx.selected_provider = provider

                ctx.raw_response = response
                ctx.response_text = response
                ctx.tokens_used = tokens["total"]
                ctx.prompt_tokens = tokens["prompt"]
                ctx.completion_tokens = tokens["completion"]
                ctx.inference_end = time.time()

                # Calculate actual cost
                model_cost = self.config.get_model_cost(ctx.selected_model)
                actual_cost = (
                    (tokens["prompt"] / 1000) * model_cost["input"] +
                    (tokens["completion"] / 1000) * model_cost["output"]
                )
                ctx.actual_cost = actual_cost

                # Calculate cost saved vs no optimization
                cost_saved = max(0, ctx.estimated_cost_without_ombre - actual_cost)
                ctx.cost_saved += cost_saved

                self._total_tokens += tokens["total"]
                self._total_cost += actual_cost

                elapsed = round((time.time() - start) * 1000, 2)
                logger.info(
                    f"Inference complete | request={ctx.request_id} | "
                    f"model={ctx.selected_model} | tokens={tokens['total']} | "
                    f"cost=${actual_cost:.4f} | {elapsed}ms"
                )
                return ctx

            except Exception as e:
                last_error = str(e)
                self._provider_failures[provider] = (
                    self._provider_failures.get(provider, 0) + 1
                )
                logger.warning(
                    f"Provider failed | request={ctx.request_id} | "
                    f"provider={provider} | error={str(e)[:100]}"
                )
                continue

        # All providers failed
        error_msg = f"All providers failed. Last error: {last_error}"
        ctx.add_error(error_msg)
        ctx.response_text = f"[Error: {error_msg}]"
        logger.error(f"All providers failed | request={ctx.request_id}")
        return ctx

    def embed(self, ctx: Any) -> List[float]:
        """Generate embeddings using the configured provider."""
        provider = "openai" if self.config.openai_key else "cohere"
        try:
            if provider == "openai":
                return self._embed_openai(ctx.get_effective_prompt())
            elif provider == "cohere":
                return self._embed_cohere(ctx.get_effective_prompt())
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

    def _detect_task_type(self, prompt: str) -> str:
        """Detect the task type from the prompt text."""
        prompt_lower = prompt.lower()
        scores: Dict[str, int] = {}

        for task_type, keywords in TASK_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                scores[task_type] = score

        if not scores:
            return "default"

        return max(scores, key=scores.get)

    def _select_model(
        self,
        preferred_model: str,
        task_type: str,
    ) -> tuple:
        """Select the best model and provider."""
        if preferred_model != "auto":
            # User specified a model — use it if the provider is available
            provider = self.config._get_model_provider(preferred_model)
            if provider in self.config.available_providers:
                return preferred_model, provider
            logger.warning(
                f"Preferred model {preferred_model} provider not available, "
                f"falling back to auto-selection"
< truncated lines 234-257 >
        raise ValueError(
            "No AI providers configured. "
            "Pass at least one API key: openai_key, anthropic_key, or groq_key. "
            "Example: Ombre(openai_key='sk-...')"
        )

    def _get_fallback_chain(self, primary_provider: str) -> List[str]:
        """Get ordered list of fallback providers."""
        available = self.config.available_providers
        return [p for p in available if p != primary_provider]

    def _build_messages(self, ctx: Any) -> List[Dict[str, str]]:
        """Build the messages array for inference."""
        messages = []

        # Add conversation history
        for msg in ctx.conversation_history[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        # Build the current user message
        user_content_parts = []

        full_context = ctx.get_full_context()
        if full_context:
            user_content_parts.append(full_context)

        user_content_parts.append(ctx.get_effective_prompt())
        user_content = "\n\n".join(user_content_parts)

        messages.append({
            "role": "user",
            "content": user_content,
        })

        return messages

    def _call_provider(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> tuple:
        """Call a specific AI provider."""
        if provider == "openai":
            return self._call_openai(model, messages, system, temperature, max_tokens)
        elif provider == "anthropic":
            return self._call_anthropic(model, messages, system, temperature, max_tokens)
        elif provider == "groq":
            return self._call_groq(model, messages, system, temperature, max_tokens)
        elif provider == "mistral":
            return self._call_mistral(model, messages, system, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _call_openai(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> tuple:
        """Call OpenAI API."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        client = OpenAI(api_key=self.config.openai_key)
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = client.chat.completions.create(
            model=model,
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.config.request_timeout_seconds,
        )

        text = response.choices[0].message.content or ""
        tokens = {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
            "total": response.usage.total_tokens,
        }
        return text, tokens

    def _call_anthropic(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> tuple:
        """Call Anthropic API."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        client = anthropic.Anthropic(api_key=self.config.anthropic_key)

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        text = response.content[0].text if response.content else ""
        tokens = {
            "prompt": response.usage.input_tokens,
            "completion": response.usage.output_tokens,
            "total": response.usage.input_tokens + response.usage.output_tokens,
        }
        return text, tokens

    def _call_groq(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> tuple:
        """Call Groq API."""
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("groq package not installed. Run: pip install groq")

        client = Groq(api_key=self.config.groq_key)
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = client.chat.completions.create(
            model=model,
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        tokens = {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
            "total": response.usage.total_tokens,
        }
        return text, tokens

    def _call_mistral(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> tuple:
        """Call Mistral API."""
        try:
            from mistralai import Mistral
        except ImportError:
            raise ImportError("mistralai package not installed. Run: pip install mistralai")

        client = Mistral(api_key=self.config.mistral_key)
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = client.chat.complete(
            model=model,
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        tokens = {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
            "total": response.usage.total_tokens,
        }
        return text, tokens

    def _embed_openai(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI."""
        from openai import OpenAI
        client = OpenAI(api_key=self.config.openai_key)
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small",
        )
        return response.data[0].embedding

    def _embed_cohere(self, text: str) -> List[float]:
        """Generate embeddings using Cohere."""
        import cohere
        client = cohere.Client(self.config.cohere_key)
        response = client.embed(
            texts=[text],
            model="embed-english-v3.0",
            input_type="search_query",
        )
        return response.embeddings[0]

    def _estimate_raw_cost(self, tokens: int, model: str) -> float:
        """Estimate cost without Ombre optimization."""
        costs = self.config.get_model_cost(model)
        return (tokens / 1000) * costs["input"]

    def stats(self) -> Dict[str, Any]:
        """Return compute agent statistics."""
        return {
            "total_requests": self._request_count,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 4),
            "provider_failures": self._provider_failures,
            "available_providers": self.config.available_providers,
        }
