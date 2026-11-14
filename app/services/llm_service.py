"""LLM service — abstraction over OpenAI and local HuggingFace models.

Provides a single ``generate_response`` interface so the rest of the
application doesn't need to know which backend is active.  When
``LLM_BACKEND=openai`` (default), uses the OpenAI Chat Completion API.
When ``LLM_BACKEND=local``, uses a HuggingFace text-generation pipeline.

This abstraction makes it trivial to swap LLM providers without changing
any calling code.
"""

from typing import Optional, List, Dict
import json

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class LLMService:
    """Unified interface for LLM generation across multiple backends.

    The backend is selected based on the ``LLM_BACKEND`` environment
    variable.  Each backend is lazy-loaded so unused dependencies
    (e.g. transformers for the local backend) don't need to be installed
    when using OpenAI.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.backend = settings.llm_backend.lower()
        self.model_name = settings.openai_model
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url or None
        self.local_model_name = settings.local_model_name
        self._client = None
        self._local_pipeline = None
        if self.backend == "ollama":
            self.base_url = settings.ollama_base_url
            self.model_name = settings.ollama_model
            self.api_key = "ollama"

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            system_prompt: System instructions (sets behavior, constraints).
            user_prompt: The user's query or task.
            conversation_history: Optional prior messages for context.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Returns:
            The generated text response.

        Raises:
            RuntimeError: If the LLM call fails.
            ValueError: If the API key is missing for the OpenAI backend.
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        if self.backend in {"openai", "ollama"}:
            return self._generate_openai(
                system_prompt, user_prompt, conversation_history, temp, tokens
            )
        elif self.backend == "gemini":
            return self._generate_gemini(
                system_prompt, user_prompt, conversation_history, temp, tokens
            )
        elif self.backend == "local":
            return self._generate_local(
                system_prompt, user_prompt, conversation_history, temp, tokens
            )
        else:
            raise ValueError(f"Unknown LLM backend: {self.backend}")

    def stream_response(self, system_prompt, user_prompt, conversation_history=None, max_tokens=None):
        """Yield provider tokens as received; never simulate a token stream."""
        tokens = max_tokens or self.max_tokens
        if self.backend == "gemini":
            yield from self._stream_gemini(system_prompt, user_prompt, conversation_history, tokens)
            return
        if self.backend not in {"openai", "ollama"}:
            # Other supported providers deliver one complete generation event.
            yield self.generate_response(system_prompt, user_prompt, conversation_history, max_tokens=tokens)
            return
        from openai import OpenAI
        if not self.api_key:
            raise ValueError("Configure an API key or select Ollama in the server environment.")
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=120)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history or [])
        messages.append({"role": "user", "content": user_prompt})
        try:
            with client.chat.completions.create(model=self.model_name, messages=messages,
                    temperature=self.temperature, max_tokens=tokens, stream=True) as stream:
                for event in stream:
                    if event.choices and event.choices[0].delta.content:
                        yield event.choices[0].delta.content
        finally:
            client.close()

    def _stream_gemini(self, system_prompt, user_prompt, history, max_tokens):
        """Forward native Gemini SSE deltas without waiting for the full answer."""
        import requests
        if not self.api_key:
            raise ValueError("Configure your Gemini API key on the server.")
        contents = [{"role": "model" if msg["role"] == "assistant" else "user",
                     "parts": [{"text": msg["content"]}]} for msg in (history or [])]
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})
        body = {"contents": contents, "systemInstruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {"temperature": self.temperature, "maxOutputTokens": max_tokens}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:streamGenerateContent?alt=sse"
        received = False
        with requests.post(url, headers={"x-goog-api-key": self.api_key}, json=body,
                           stream=True, timeout=(10, 90)) as response:
            response.raise_for_status()
            response.encoding = "utf-8"
            for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                event = json.loads(line[5:].strip())
                if event.get("error"):
                    raise RuntimeError("Gemini returned a generation error.")
                for candidate in event.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        if part.get("text") and not part.get("thought"):
                            received = True
                            yield part["text"]
            if not received:
                raise RuntimeError("Gemini returned no answer text. Check provider availability or safety restrictions.")

    def _generate_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate a response using the OpenAI Chat Completion API."""
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Please add your API key to the .env file or set the environment variable."
            )

        # Lazy-load the OpenAI client
        if self._client is None:
            try:
                from openai import OpenAI
                client_kwargs = {"api_key": self.api_key}
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                self._client = OpenAI(**client_kwargs)
            except ImportError:
                raise ImportError(
                    "openai package is not installed. Run: pip install openai"
                )

        # Build the message list
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (user/assistant pairs)
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        # Add the current user prompt
        messages.append({"role": "user", "content": user_prompt})

        logger.info(
            f"Calling OpenAI: model={self.model_name}, "
            f"messages={len(messages)}, temp={temperature}"
        )

        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            logger.info(
                f"OpenAI response received: {len(content)} chars, "
                f"tokens={response.usage.total_tokens if response.usage else 'N/A'}"
            )
            return content
        except Exception as exc:
            logger.error(f"OpenAI API call failed: {exc}")
            raise RuntimeError(f"LLM generation failed: {exc}") from exc

    def _generate_local(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate a response using a local HuggingFace model."""
        if self._local_pipeline is None:
            try:
                import torch
                from transformers import pipeline as hf_pipeline

                logger.info(f"Loading local model: {self.local_model_name}")
                self._local_pipeline = hf_pipeline(
                    "text-generation",
                    model=self.local_model_name,
                    torch_dtype=torch.float16,
                    device_map="auto",
                )
            except ImportError:
                raise ImportError(
                    "transformers and torch are not installed. "
                    "Run: pip install transformers torch"
                )

        # Build a simple chat prompt
        prompt_parts = [system_prompt]
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    prompt_parts.append(f"User: {content}")
                else:
                    prompt_parts.append(f"Assistant: {content}")
        prompt_parts.append(f"User: {user_prompt}")
        prompt_parts.append("Assistant:")

        full_prompt = "\n\n".join(prompt_parts)

        logger.info(f"Calling local model: {self.local_model_name}")

        try:
            result = self._local_pipeline(
                full_prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                return_full_text=False,
            )
            content = result[0]["generated_text"].strip()
            logger.info(f"Local model response received: {len(content)} chars")
            return content
        except Exception as exc:
            logger.error(f"Local model generation failed: {exc}")
            raise RuntimeError(f"LLM generation failed: {exc}") from exc

    def _generate_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate a response using Google Gemini's native REST API.

        Uses the v1beta generateContent endpoint.  The key is passed as
        a query parameter (``?key=``) which is the standard method for
        Gemini API keys, including the new ``AQ.`` format that does not
        work with the OpenAI-compatible Bearer-token endpoint.
        """
        import requests as _requests

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Please add your Gemini API key to the .env file."
            )

        model = self.model_name
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent"
        )

        # Build the contents list (conversation turns)
        contents = []

        # Add conversation history
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Gemini uses "model" instead of "assistant"
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}],
                })

        # Add the current user prompt
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})

        # Build the full request body
        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
            },
        }

        # System instructions are passed separately in Gemini
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        logger.info(
            f"Calling Gemini: model={model}, "
            f"contents={len(contents)}, temp={temperature}"
        )

        try:
            resp = _requests.post(url, json=body, headers={"x-goog-api-key": self.api_key}, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            # Extract text from the response
            candidates = data.get("candidates", [])
            if not candidates:
                # Check for blocked content
                prompt_feedback = data.get("promptFeedback", {})
                block_reason = prompt_feedback.get("blockReason")
                if block_reason:
                    return f"Response blocked: {block_reason}"
                return "No response generated."

            content_parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in content_parts)

            logger.info(f"Gemini response received: {len(text)} chars")
            return text

        except _requests.exceptions.HTTPError as exc:
            error_detail = ""
            try:
                error_detail = exc.response.json().get("error", {}).get("message", str(exc))
            except Exception:
                error_detail = str(exc)
            logger.error(f"Gemini API call failed: {error_detail}")
            raise RuntimeError(f"LLM generation failed: {error_detail}") from exc
        except Exception as exc:
            logger.error(f"Gemini API call failed: {exc}")
            raise RuntimeError(f"LLM generation failed: {exc}") from exc

    def is_available(self) -> bool:
        """Check if the configured LLM backend is available."""
        if self.backend == "openai":
            return bool(self.api_key)
        elif self.backend == "gemini":
            return bool(self.api_key)
        elif self.backend == "local":
            try:
                import transformers  # noqa: F401
                import torch  # noqa: F401
                return True
            except ImportError:
                return False
        return False
