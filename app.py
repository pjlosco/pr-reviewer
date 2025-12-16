#!/usr/bin/env python3
"""
PR Review Agent - Main Entry Point

This is the main entry point for the PR Review Agent.
It can be run directly or via the command line.

Usage:
    python app.py --pr-url <PR_URL>
    python -m app --pr-url <PR_URL>
"""

import argparse
import sys
from agent.review_agent import run_review_agent


def main():
    """Main entry point for the PR Review Agent."""
    parser = argparse.ArgumentParser(
        description="AI-powered code review agent for pull requests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app.py --pr-url https://github.com/owner/repo/pull/123
  python -m app --pr-url https://github.com/owner/repo/pull/123

Environment Variables:
  GITHUB_TOKEN          - GitHub API token (required)
  OPENAI_API_KEY        - OpenAI API key (or ANTHROPIC_API_KEY, GOOGLE_API_KEY)
  LLM_PROVIDER          - LLM provider: "openai", "anthropic", or "google"
  LLM_MODEL             - Model name (e.g., "gpt-3.5-turbo")
  LLM_TEMPERATURE       - Temperature setting (default: 0.7)
  LANGCHAIN_TRACING_V2  - Enable LangSmith tracing ("true" or "false")
  LANGCHAIN_API_KEY     - LangSmith API key (optional)
  JIRA_*                - Jira configuration (optional)
  CONFLUENCE_*          - Confluence configuration (optional)
        """
    )
    
    parser.add_argument(
        "--pr-url",
        type=str,
        required=True,
        help="URL of the pull request to review (e.g., https://github.com/owner/repo/pull/123)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    try:
        # Run the review agent
        run_review_agent(pr_url=args.pr_url, verbose=args.verbose)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

