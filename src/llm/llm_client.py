"""
LLM Client Module
Provides a unified interface for multiple LLM providers with automatic failover
"""

import os
import json
import logging
import time
import threading
from typing import Dict, Optional, Any, List
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    """Status of an LLM provider"""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"

    def __str__(self):
        return self.value


class RateLimitError(Exception):
    """Raised when a provider's rate limit is exceeded"""
    def __init__(self, provider: str, retry_after: int = 60):
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded for {provider}, retry after {retry_after}s")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Generate a response from the LLM"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM client is properly configured"""
        pass
    
    def get_provider_name(self) -> str:
        """Return the provider name"""
        return self.__class__.__name__.replace('Client', '').lower()


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = config.get('llm', {}).get('openai_model', 'gpt-4o')
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized successfully")
            except ImportError:
                logger.warning("OpenAI package not installed. Install with: pip install openai")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
    
    def is_available(self) -> bool:
        return self.client is not None and self.api_key is not None
    
    def generate(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.is_available():
            logger.error("OpenAI client not available")
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            error_str = str(e).lower()
            # Check for rate limit or quota errors
            if 'rate limit' in error_str or 'quota' in error_str or '429' in error_str:
                logger.warning(f"OpenAI rate limit/quota exceeded: {e}")
                raise RateLimitError('openai', retry_after=60)
            logger.error(f"OpenAI API error: {e}")
            return None


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = config.get('llm', {}).get('anthropic_model', 'claude-3-5-sonnet-20241022')
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.client = None
        
        if self.api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
                logger.info("Anthropic client initialized successfully")
            except ImportError:
                logger.warning("Anthropic package not installed. Install with: pip install anthropic")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
    
    def is_available(self) -> bool:
        return self.client is not None and self.api_key is not None
    
    def generate(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.is_available():
            logger.error("Anthropic client not available")
            return None
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.7,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            error_str = str(e).lower()
            # Check for rate limit or quota errors
            if 'rate limit' in error_str or 'quota' in error_str or '429' in error_str or 'over_limit' in error_str:
                logger.warning(f"Anthropic rate limit/quota exceeded: {e}")
                raise RateLimitError('anthropic', retry_after=60)
            logger.error(f"Anthropic API error: {e}")
            return None


class GeminiClient(BaseLLMClient):
    """Google Gemini client"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = config.get('llm', {}).get('gemini_model', 'gemini-1.5-pro')
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.client = None
        
        if self.api_key:
            try:
                import google.genai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
                logger.info("Gemini client initialized successfully")
            except ImportError:
                logger.warning("Google GenAI package not installed. Install with: pip install google-genai")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
    
    def is_available(self) -> bool:
        return self.client is not None and self.api_key is not None
    
    def generate(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.is_available():
            logger.error("Gemini client not available")
            return None
        
        try:
            model = self.client.models.generate(
                model=self.model,
                contents=f"System: {system_prompt}\n\nUser: {user_prompt}",
                config={
                    'temperature': 0.7,
                    'max_output_tokens': 2000
                }
            )
            return model.text if hasattr(model, 'text') else str(model)
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'quota' in error_str or '429' in error_str or 'resource_exhausted' in error_str:
                logger.warning(f"Gemini rate limit/quota exceeded: {e}")
                raise RateLimitError('gemini', retry_after=60)
            logger.error(f"Gemini API error: {e}")
            return None


class MiniMaxClient(BaseLLMClient):
    """MiniMax AI client - Free tier available"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = config.get('llm', {}).get('minimax_model', 'abab6.5s-chat')
        self.api_key = os.getenv('MINIMAX_API_KEY')
        self.client = None
        self.base_url = "https://api.minimax.chat/v1"
        
        if self.api_key:
            try:
                import requests
                self.client = requests
                logger.info("MiniMax client initialized successfully")
            except ImportError:
                logger.warning("Requests package not installed.")
            except Exception as e:
                logger.error(f"Failed to initialize MiniMax client: {e}")
    
    def is_available(self) -> bool:
        return self.client is not None and self.api_key is not None
    
    def generate(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.is_available():
            logger.error("MiniMax client not available")
            return None
        
        try:
            url = f"{self.base_url}/text/chatcompletion_v2"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            response = self.client.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('choices', [{}])[0].get('message', {}).get('content')
            elif response.status_code == 429:
                logger.warning(f"MiniMax rate limit exceeded")
                raise RateLimitError('minimax', retry_after=60)
            else:
                logger.error(f"MiniMax API error: {response.status_code} - {response.text}")
                return None
                
        except RateLimitError:
            raise
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or '429' in error_str:
                logger.warning(f"MiniMax rate limit exceeded: {e}")
                raise RateLimitError('minimax', retry_after=60)
            logger.error(f"MiniMax API error: {e}")
            return None


class OllamaClient(BaseLLMClient):
    """Ollama client - Free local LLM"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = config.get('llm', {}).get('ollama_model', 'llama2')
        self.base_url = config.get('llm', {}).get('ollama_url', 'http://localhost:11434')
        self.client = None
        
        # Check if we can import requests
        try:
            import requests
            self.client = requests
            # Test connection
            try:
                response = self.client.get(f"{self.base_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    logger.info(f"Ollama client initialized successfully at {self.base_url}")
                else:
                    logger.debug(f"Ollama not responding at {self.base_url}")
                    self.client = None
            except Exception as e:
                logger.debug(f"Cannot connect to Ollama at {self.base_url}: {e}")
                self.client = None
        except ImportError:
            logger.warning("Requests package not installed.")
    
    def is_available(self) -> bool:
        if self.client is None:
            return False
        try:
            # Quick health check
            response = self.client.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def generate(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.is_available():
            logger.error("Ollama client not available")
            return None
        
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": f"System: {system_prompt}\n\nUser: {user_prompt}",
                "temperature": 0.7,
                "stream": False
            }
            
            response = self.client.post(url, json=payload, timeout=120)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', '')
            elif response.status_code == 429:
                logger.warning(f"Ollama rate limit exceeded")
                raise RateLimitError('ollama', retry_after=30)
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return None
                
        except RateLimitError:
            raise
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or '429' in error_str:
                logger.warning(f"Ollama rate limit: {e}")
                raise RateLimitError('ollama', retry_after=30)
            logger.error(f"Ollama API error: {e}")
            return None


class LLMFailoverClient:
    """
    LLM Client with automatic failover when rate limited
    Tracks provider status and automatically switches to next available provider
    """
    
    # Provider priority order - free providers first
    PROVIDER_PRIORITY = [
        'ollama',      # Free local - try first if available
        'minimax',     # Free tier available
        'gemini',      # Has free tier
        'anthropic',   # Has some free credits
        'openai'       # Usually paid
    ]
    
    # How long to wait before retrying a rate-limited provider (seconds)
    # Will be overridden by config if provided
    RATE_LIMIT_RECOVERY_TIME = 300  # 5 minutes
    
    def __init__(self, config: Dict):
        self.config = config
        self.llm_config = config.get('llm', {})
        self.enabled = self.llm_config.get('enabled', False)
        
        # Initialize all providers
        self.providers: Dict[str, BaseLLMClient] = {
            'openai': OpenAIClient(config),
            'anthropic': AnthropicClient(config),
            'gemini': GeminiClient(config),
            'minimax': MiniMaxClient(config),
            'ollama': OllamaClient(config)
        }
        
        # Track provider status
        self.provider_status: Dict[str, ProviderStatus] = {
            name: ProviderStatus.AVAILABLE for name in self.providers
        }
        self.provider_rate_limited_at: Dict[str, float] = {}
        
        # Rate limit recovery time - read from config if provided
        self.RATE_LIMIT_RECOVERY_TIME = self.llm_config.get('rate_limit_recovery_seconds', 300)
        
        # Primary provider preference
        self.primary_provider = self.llm_config.get('provider', 'openai')
        
        # Current active provider (starts with primary)
        self.current_provider = self.primary_provider
        
        # Log initialization
        available = [name for name, p in self.providers.items() if p.is_available()]
        logger.info(f"LLM Client initialized - Enabled: {self.enabled}")
        logger.info(f"Available providers: {available}")
        
        # Thread safety lock for provider status updates
        self._lock = threading.Lock()
    
    def is_enabled(self) -> bool:
        """Check if LLM is enabled in config"""
        return self.enabled
    
    def _is_provider_available(self, provider_name: str) -> bool:
        """Check if a specific provider is available (considering rate limits)"""
        with self._lock:
            if provider_name not in self.providers:
                return False
            
            # Check if basic availability
            if not self.providers[provider_name].is_available():
                return False
            
            # Check if rate limited
            if provider_name in self.provider_rate_limited_at:
                rate_limited_time = self.provider_rate_limited_at[provider_name]
                if time.time() - rate_limited_time < self.RATE_LIMIT_RECOVERY_TIME:
                    logger.debug(f"Provider {provider_name} is rate limited, waiting {(self.RATE_LIMIT_RECOVERY_TIME - (time.time() - rate_limited_time)):.0f}s more")
                    return False
                else:
                    # Recovery time passed, reset rate limit status
                    logger.info(f"Provider {provider_name} rate limit recovery period expired")
                    del self.provider_rate_limited_at[provider_name]
                    self.provider_status[provider_name] = ProviderStatus.AVAILABLE
            
            return True
    
    def _mark_rate_limited(self, provider_name: str):
        """Mark a provider as rate limited"""
        with self._lock:
            self.provider_status[provider_name] = ProviderStatus.RATE_LIMITED
            self.provider_rate_limited_at[provider_name] = time.time()
            logger.warning(f"Provider {provider_name} marked as rate limited")
    
    def _get_next_available_provider(self, exclude: List[str] = None) -> Optional[str]:
        if exclude is None:
            exclude = []
        """Get the next available provider, excluding specified ones"""
        
        # First try primary provider if not excluded
        if self.primary_provider not in exclude and self._is_provider_available(self.primary_provider):
            return self.primary_provider
        
        # Try providers in priority order
        for provider_name in self.PROVIDER_PRIORITY:
            if provider_name not in exclude and self._is_provider_available(provider_name):
                return provider_name
        
        return None
    
    def is_available(self) -> bool:
        """Check if any provider is available"""
        if not self.enabled:
            return False
        
        for provider_name in self.providers:
            if self._is_provider_available(provider_name):
                return True
        
        return False
    
    def generate_analysis(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Generate analysis with automatic failover
        
        Args:
            system_prompt: System instructions with rules
            user_prompt: User query with data
            
        Returns:
            Generated analysis or None if all providers failed
        """
        if not self.is_available():
            logger.warning("No LLM provider available")
            return None
        
        tried_providers = []
        max_attempts = len(self.providers)  # Limit to number of providers available
        attempts = 0
        
        while attempts < max_attempts:
            attempts += 1
            # Get next available provider
            provider_name = self._get_next_available_provider(exclude=tried_providers)
            
            if provider_name is None:
                logger.error("All LLM providers are rate limited or unavailable")
                return None
            
            tried_providers.append(provider_name)
            provider = self.providers[provider_name]
            
            logger.info(f"Trying provider: {provider_name}")
            
            try:
                result = provider.generate(system_prompt, user_prompt)
                
                if result:
                    # Success! Update current provider
                    if provider_name != self.current_provider:
                        logger.info(f"Switched to provider: {provider_name}")
                        self.current_provider = provider_name
                    return result
                else:
                    # Provider returned None (non-rate-limit failure)
                    logger.warning(f"Provider {provider_name} returned no result")
                    
            except RateLimitError as e:
                # Provider is rate limited, mark it and try next
                logger.warning(f"Provider {provider_name} rate limited: {e}")
                self._mark_rate_limited(provider_name)
                # Continue to try next provider
                continue
            
            except Exception as e:
                logger.error(f"Unexpected error from {provider_name}: {e}")
                # Continue to try next provider
        
        return None
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get detailed status of all providers"""
        status = {}
        for name, provider in self.providers.items():
            basic_available = provider.is_available()
            fully_available = self._is_provider_available(name)
            
            rate_limited = name in self.provider_rate_limited_at
            recovery_time = None
            if rate_limited:
                elapsed = time.time() - self.provider_rate_limited_at[name]
                remaining = self.RATE_LIMIT_RECOVERY_TIME - elapsed
                recovery_time = max(0, int(remaining))
            
            status[name] = {
                'configured': basic_available,
                'available': fully_available,
                'rate_limited': rate_limited,
                'recovery_seconds': recovery_time,
                'is_current': name == self.current_provider
            }
        
        return status
    
    def force_switch_provider(self, provider_name: str = None):
        """Manually switch to a specific provider, or switch to next available if none specified"""
        if provider_name and provider_name in self.providers:
            if self._is_provider_available(provider_name):
                self.current_provider = provider_name
                logger.info(f"Manually switched to provider: {provider_name}")
            else:
                logger.warning(f"Provider {provider_name} is not available")
        else:
            # Switch to next available
            next_provider = self._get_next_available_provider()
            if next_provider:
                self.current_provider = next_provider
                logger.info(f"Switched to next available provider: {next_provider}")
    
    def reset_rate_limits(self):
        """Reset all rate limits (for testing or manual recovery)"""
        self.provider_rate_limited_at.clear()
        for name in self.provider_status:
            self.provider_status[name] = ProviderStatus.AVAILABLE
        logger.info("All provider rate limits reset")


# Backwards compatibility alias
class LLMClient(LLMFailoverClient):
    """Backwards compatibility alias for LLMFailoverClient"""
    pass


# Global client instance
_llm_client: Optional[LLMFailoverClient] = None


def get_llm_client(config: Dict) -> LLMFailoverClient:
    """Get or create the global LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMFailoverClient(config)
    return _llm_client


def reset_llm_client():
    """Reset the global LLM client (for testing)"""
    global _llm_client
    _llm_client = None
