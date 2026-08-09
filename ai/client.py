"""OpenAI-compatible HTTP client for AI model endpoints."""

import base64
import json
import logging
import threading
from io import BytesIO
from typing import Any

import requests
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, retry_if_result

logger = logging.getLogger(__name__)


class AIClient:
    """HTTP client for OpenAI-compatible vision and text models."""

    def __init__(self, base_url: str, api_key: str = '', model: str = '',
                 timeout: int = 120):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = timeout or 120
        self._resolved_model = None
        self._session = requests.Session()
        if api_key:
            self._session.headers['Authorization'] = f'Bearer {api_key}'
        # Add keep-alive and connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=0,
            pool_block=False
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    def _resolve_model(self, model: str = '') -> str:
        """Resolve model name, auto-detecting if needed."""
        resolved = model or self.model
        if resolved in ('auto', '', None):
            if self._resolved_model is None:
                models = self.get_models()
                if models:
                    self._resolved_model = models[0]['id']
                    logger.info(f"Auto-detected model: {self._resolved_model}")
            resolved = self._resolved_model or ''
        return resolved

    def chat_completion(self, messages: list[dict], model: str = '',
                        max_tokens: int = 4096, temperature: float = 0.7,
                        stream: bool = False) -> dict[str, Any]:
        """Send a chat completion request with hard timeout.

        Uses non-streaming by default for better output quality.
        Set stream=True for OMLX backends that buffer non-streaming responses.
        """
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            'model': self._resolve_model(model),
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'stream': stream,
        }

        if stream:
            # Streaming mode with thread for hard timeout
            result = [None]
            error = [None]

            def _do_streaming_request():
                try:
                    chunks = []
                    with self._session.post(url, json=payload, stream=True,
                                            timeout=self.timeout) as resp:
                        resp.raise_for_status()
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                data = line_str[6:]
                                if data.strip() == '[DONE]':
                                    break
                                try:
                                    chunk = json.loads(data)
                                    if 'choices' in chunk:
                                        for choice in chunk['choices']:
                                            delta = choice.get('delta', {})
                                            content = delta.get('content', '')
                                            if content:
                                                chunks.append(content)
                                except json.JSONDecodeError:
                                    pass

                    result[0] = {
                        'id': 'stream',
                        'object': 'chat.completion',
                        'choices': [{
                            'message': {'content': ''.join(chunks)},
                            'finish_reason': 'stop',
                        }],
                    }
                except Exception as e:
                    error[0] = e

            t = threading.Thread(target=_do_streaming_request, daemon=True)
            t.start()
            t.join(timeout=self.timeout)

            if t.is_alive():
                logger.error(f"Hard timeout ({self.timeout}s) for {url}")
                raise requests.exceptions.Timeout(f"Request timed out after {self.timeout}s")

            if error[0]:
                raise error[0]

            return result[0]
        else:
            # Non-streaming mode
            with self._session.post(url, json=payload, timeout=self.timeout) as resp:
                resp.raise_for_status()
                return resp.json()

    def vision_completion(self, messages: list[dict], image_data: bytes,
                          mime_type: str = 'image/jpeg', model: str = '',
                          max_tokens: int = 4096, temperature: float = 0.7,
                          image_size: int = 1280) -> dict[str, Any]:
        """Send a vision completion request with an image."""
        # Resize image if needed
        if image_size:
            image_data = self._resize_image(image_data, image_size)

        b64 = base64.b64encode(image_data).decode('ascii')
        data_url = f"data:{mime_type};base64,{b64}"

        # Ensure the user message contains the image URL
        for msg in messages:
            if msg.get('role') == 'user':
                if isinstance(msg.get('content'), list):
                    msg['content'].append({
                        'type': 'image_url',
                        'image_url': {'url': data_url, 'detail': 'high'}
                    })
                else:
                    msg['content'] = [
                        {'type': 'text', 'text': msg['content']},
                        {'type': 'image_url', 'image_url': {'url': data_url, 'detail': 'high'}}
                    ]
                break

        return self.chat_completion(
            messages=messages,
            model=model or self.model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def _resize_image(self, image_data: bytes, max_dimension: int) -> bytes:
        """Resize image to fit within max_dimension while preserving aspect ratio."""
        try:
            img = Image.open(BytesIO(image_data))

            # Skip if already small enough
            if max(img.width, img.height) <= max_dimension:
                return image_data

            # Preserve aspect ratio
            ratio = max_dimension / max(img.width, img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

            buf = BytesIO()
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save(buf, format='JPEG', quality=85)
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Image resize failed, using original: {e}")
            return image_data

    def get_models(self) -> dict:
        """List available models at the endpoint.
        Returns {'status': 'ok'|'error', 'models': [...], 'message': str, 'status_code': int}
        """
        url = f"{self.base_url}/v1/models"
        try:
            resp = self._session.get(url, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    return {'status': 'ok', 'models': data.get('data', []), 'message': '', 'status_code': 200}
                except Exception:
                    return {'status': 'error', 'models': [], 'message': 'Invalid server response', 'status_code': 200}
            elif resp.status_code == 401:
                return {'status': 'error', 'models': [], 'message': 'Invalid API key', 'status_code': 401}
            elif resp.status_code == 403:
                return {'status': 'error', 'models': [], 'message': 'API key not authorized', 'status_code': 403}
            else:
                return {'status': 'error', 'models': [], 'message': f'Server error: {resp.status_code}', 'status_code': resp.status_code}
        except requests.exceptions.ConnectionError:
            return {'status': 'error', 'models': [], 'message': 'Cannot connect to server', 'status_code': 0}
        except requests.exceptions.Timeout:
            return {'status': 'error', 'models': [], 'message': 'Connection timed out', 'status_code': 0}
        except Exception as e:
            logger.warning(f"Could not fetch model list from {url}: {e}")
            return {'status': 'error', 'models': [], 'message': str(e), 'status_code': 0}

    def health_check(self) -> bool:
        """Check if the endpoint is reachable."""
        try:
            resp = self._session.get(f"{self.base_url}/v1/models", timeout=5)
            return resp.status_code in (200, 401)  # 401 means server is up but needs key
        except Exception:
            return False

    def close(self) -> None:
        """Close the session."""
        self._session.close()
