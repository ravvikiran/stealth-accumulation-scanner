"""
LLM Integration Module
Provides AI-powered analysis using configurable LLM providers
"""

from src.llm.llm_client import LLMClient, get_llm_client

__all__ = ['LLMClient', 'get_llm_client']
