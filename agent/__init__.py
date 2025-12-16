"""
Code Review Agent Package

This package provides an AI-powered code review agent that uses LangGraph
to orchestrate code reviews with context from GitHub, Jira, and Confluence.
"""

from agent.review_agent import run_review_agent

__all__ = ["run_review_agent"]
__version__ = "0.1.0"

