"""
LLM Client Module
Provides a unified interface for multiple LLM providers (OpenAI, Anthropic, Google Gemini)
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


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
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
                logger.info("Gemini client initialized successfully")
            except ImportError:
                logger.warning("Google Generative AI package not installed. Install with: pip install google-generativeai")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
    
    def is_available(self) -> bool:
        return self.client is not None and self.api_key is not None
    
    def generate(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.is_available():
            logger.error("Gemini client not available")
            return None
        
        try:
            model = self.client.GenerativeModel(self.model)
            response = model.generate_content(
                contents=f"System: {system_prompt}\n\nUser: {user_prompt}",
                generation_config={
                    'temperature': 0.7,
                    'max_output_tokens': 2000
                }
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None


class LLMClient:
    """
    Unified LLM client that wraps multiple providers
    Supports: OpenAI GPT, Anthropic Claude, Google Gemini
    """
    
    # Provider priority order (tried in this order)
    PROVIDERS = ['openai', 'anthropic', 'gemini']
    
    def __init__(self, config: Dict):
        self.config = config
        self.llm_config = config.get('llm', {})
        self.enabled = self.llm_config.get('enabled', False)
        
        # Initialize all providers
        self.providers: Dict[str, BaseLLMClient] = {
            'openai': OpenAIClient(config),
            'anthropic': AnthropicClient(config),
            'gemini': GeminiClient(config)
        }
        
        # Determine primary provider
        self.primary_provider = self.llm_config.get('provider', 'openai')
        
        logger.info(f"LLM Client initialized - Enabled: {self.enabled}, Provider: {self.primary_provider}")
    
    def is_enabled(self) -> bool:
        """Check if LLM is enabled in config"""
        return self.enabled
    
    def is_available(self) -> bool:
        """Check if any provider is available"""
        if not self.enabled:
            return False
        
        # Check primary provider first
        if self.primary_provider in self.providers:
            if self.providers[self.primary_provider].is_available():
                return True
        
        # Try other providers
        for provider_name in self.PROVIDERS:
            if provider_name != self.primary_provider:
                if provider_name in self.providers:
                    if self.providers[provider_name].is_available():
                        logger.info(f"Using fallback provider: {provider_name}")
                        return True
        
        return False
    
    def generate_analysis(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Generate analysis using available LLM provider
        
        Args:
            system_prompt: System instructions with rules
            user_prompt: User query with data
            
        Returns:
            Generated analysis or None if failed
        """
        if not self.is_available():
            logger.warning("LLM not available")
            return None
        
        # Try primary provider first
        if self.primary_provider in self.providers:
            provider = self.providers[self.primary_provider]
            if provider.is_available():
                result = provider.generate(system_prompt, user_prompt)
                if result:
                    return result
        
        # Try fallback providers
        for provider_name in self.PROVIDERS:
            if provider_name != self.primary_provider:
                provider = self.providers[provider_name]
                if provider.is_available():
                    logger.info(f"Falling back to {provider_name}")
                    result = provider.generate(system_prompt, user_prompt)
                    if result:
                        return result
        
        logger.error("All LLM providers failed")
        return None
    
    def get_provider_status(self) -> Dict[str, bool]:
        """Get status of all providers"""
        return {
            name: provider.is_available() 
            for name, provider in self.providers.items()
        }


# Global client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client(config: Dict) -> LLMClient:
    """Get or create the global LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(config)
    return _llm_client


def reset_llm_client():
    """Reset the global LLM client (for testing)"""
    global _llm_client
    _llm_client = None
