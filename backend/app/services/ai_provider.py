"""
Lumina_Ant - Capa de abstracción para proveedores de IA
Permite alternar entre Claude, OpenAI (ChatGPT) y Gemini desde .env
"""

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, List, Optional
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Interfaz base para todos los proveedores de IA."""

    # Almacena el uso de tokens de la última llamada (input/output/total)
    _last_usage: Dict = {}

    def get_last_usage(self) -> Dict:
        """
        Retorna el uso de tokens de la última llamada.
        {"input_tokens": int, "output_tokens": int, "total_tokens": int, "source": "exact"|"estimated"}
        """
        return self._last_usage.copy()

    @abstractmethod
    def chat_completion(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1500,
    ) -> str:
        """
        Envía una conversación al modelo y retorna la respuesta completa.
        Popula self._last_usage con los tokens consumidos.
        """
        ...

    @abstractmethod
    def single_prompt(self, prompt: str, max_tokens: int = 1500) -> str:
        """
        Envía un prompt único (sin historial) y retorna la respuesta.
        Usado para análisis (analyze_sales, explain_alert, etc.)
        """
        ...

    @abstractmethod
    async def stream_completion(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        """
        Envía una conversación al modelo y retorna un async generator
        que produce fragmentos de texto (deltas) conforme llegan.
        Popula self._last_usage al terminar el stream.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nombre del proveedor para logs."""
        ...


# ── Claude (Anthropic) ────────────────────────────────────────────

class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        import anthropic
        self._api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self._last_usage = {}
        logger.info(f"ClaudeProvider iniciado (modelo: {model})")

    def chat_completion(self, system_prompt: str, messages: List[Dict[str, str]], max_tokens: int = 1500) -> str:
        # cache_control: ephemeral → Claude cachea el system prompt si supera el mínimo de tokens.
        # Para prompts cortos simplemente se ignora sin coste adicional.
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        inp = response.usage.input_tokens
        out = response.usage.output_tokens
        cache_created = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        self._last_usage = {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
            "cache_creation_input_tokens": cache_created,
            "cache_read_input_tokens": cache_read,
            "source": "exact",
        }
        if cache_read:
            logger.debug(f"Claude cache HIT: {cache_read} tokens ahorrados")
        elif cache_created:
            logger.debug(f"Claude cache CREATED: {cache_created} tokens almacenados")
        return response.content[0].text

    def single_prompt(self, prompt: str, max_tokens: int = 1500) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        inp = response.usage.input_tokens
        out = response.usage.output_tokens
        self._last_usage = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out, "source": "exact"}
        return response.content[0].text

    async def stream_completion(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        import anthropic
        async_client = anthropic.AsyncAnthropic(api_key=self._api_key)
        self._last_usage = {}
        async with async_client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
            # get_final_message() es la forma oficial de obtener usage tras el stream
            try:
                final = await stream.get_final_message()
                inp = final.usage.input_tokens
                out = final.usage.output_tokens
                cache_created = getattr(final.usage, "cache_creation_input_tokens", 0) or 0
                cache_read = getattr(final.usage, "cache_read_input_tokens", 0) or 0
                self._last_usage = {
                    "input_tokens": inp,
                    "output_tokens": out,
                    "total_tokens": inp + out,
                    "cache_creation_input_tokens": cache_created,
                    "cache_read_input_tokens": cache_read,
                    "source": "exact",
                }
                if cache_read:
                    logger.debug(f"Claude stream cache HIT: {cache_read} tokens ahorrados")
                elif cache_created:
                    logger.debug(f"Claude stream cache CREATED: {cache_created} tokens almacenados")
            except Exception as e:
                logger.warning(f"No se pudo capturar usage del stream Claude: {e}")

    @property
    def provider_name(self) -> str:
        return "Claude"


# ── OpenAI (ChatGPT) ──────────────────────────────────────────────

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI
        self._api_key = api_key
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self._last_usage = {}
        logger.info(f"OpenAIProvider iniciado (modelo: {model})")

    def chat_completion(self, system_prompt: str, messages: List[Dict[str, str]], max_tokens: int = 1500) -> str:
        openai_messages = [{"role": "system", "content": system_prompt}]
        openai_messages.extend(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            max_tokens=max_tokens,
        )
        inp = response.usage.prompt_tokens
        out = response.usage.completion_tokens
        self._last_usage = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out, "source": "exact"}
        return response.choices[0].message.content

    def single_prompt(self, prompt: str, max_tokens: int = 1500) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        inp = response.usage.prompt_tokens
        out = response.usage.completion_tokens
        self._last_usage = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out, "source": "exact"}
        return response.choices[0].message.content

    async def stream_completion(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        from openai import AsyncOpenAI
        async_client = AsyncOpenAI(api_key=self._api_key)
        openai_messages = [{"role": "system", "content": system_prompt}]
        openai_messages.extend(messages)
        self._last_usage = {}
        stream = await async_client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},  # último chunk incluye usage
        )
        async for chunk in stream:
            # El último chunk (con choices vacío) trae el usage total
            if chunk.usage:
                inp = chunk.usage.prompt_tokens
                out = chunk.usage.completion_tokens
                self._last_usage = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out, "source": "exact"}
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @property
    def provider_name(self) -> str:
        return "OpenAI"


# ── Gemini (Google) ────────────────────────────────────────────────

class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self._last_usage = {}
        logger.info(f"GeminiProvider iniciado (modelo: {model})")

    def chat_completion(self, system_prompt: str, messages: List[Dict[str, str]], max_tokens: int = 1500) -> str:
        from google.genai import types

        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])],
            ))

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
            ),
        )
        try:
            meta = response.usage_metadata
            inp = meta.prompt_token_count or 0
            out = meta.candidates_token_count or 0
            self._last_usage = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out, "source": "exact"}
        except Exception:
            self._last_usage = {}
        return response.text

    def single_prompt(self, prompt: str, max_tokens: int = 1500) -> str:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
        )
        try:
            meta = response.usage_metadata
            inp = meta.prompt_token_count or 0
            out = meta.candidates_token_count or 0
            self._last_usage = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out, "source": "exact"}
        except Exception:
            self._last_usage = {}
        return response.text

    async def stream_completion(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        # Gemini sync SDK: ejecutar en thread pool; _last_usage queda seteado por chat_completion
        self._last_usage = {}
        text = await asyncio.to_thread(self.chat_completion, system_prompt, messages, max_tokens)
        yield text

    @property
    def provider_name(self) -> str:
        return "Gemini"


# ── Factory ────────────────────────────────────────────────────────

def get_ai_provider() -> Optional[AIProvider]:
    """
    Crea y retorna el proveedor de IA según la configuración en .env.
    Retorna None si no hay API key configurada (modo demo).
    """
    settings = get_settings()
    provider = settings.ai_provider.lower().strip()

    if provider == "claude":
        api_key = settings.anthropic_api_key
        if not api_key:
            logger.warning("AI_PROVIDER=claude pero ANTHROPIC_API_KEY está vacía → modo demo")
            return None
        return ClaudeProvider(api_key, settings.claude_model)

    elif provider == "openai":
        api_key = settings.openai_api_key
        if not api_key:
            logger.warning("AI_PROVIDER=openai pero OPENAI_API_KEY está vacía → modo demo")
            return None
        return OpenAIProvider(api_key, settings.openai_model)

    elif provider == "gemini":
        api_key = settings.google_api_key
        if not api_key:
            logger.warning("AI_PROVIDER=gemini pero GOOGLE_API_KEY está vacía → modo demo")
            return None
        return GeminiProvider(api_key, settings.gemini_model)

    else:
        logger.error(f"AI_PROVIDER desconocido: '{provider}'. Opciones: claude, openai, gemini")
        return None
