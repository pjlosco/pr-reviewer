# Pipeline Options for Code Review Agent

## Overview

This document outlines different pipeline options for triggering the code review agent. The agent itself remains the same regardless of the trigger mechanism.

## Option 1: GitHub Actions (Recommended for Simplicity)

### Architecture
```
GitHub PR Event → GitHub Actions Workflow → Agent → Review Comments
```

### Implementation
- **Trigger**: GitHub Actions workflow file (`.github/workflows/code-review.yml`)
- **Events**: `pull_request` events (opened, synchronize, reopened)
- **Secrets**: Store tokens in GitHub Secrets
- **Execution**: Runs in GitHub-hosted runners or self-hosted runners

### Advantages
- ✅ Native GitHub integration
- ✅ No webhook configuration needed
- ✅ Built-in secret management
- ✅ Free for public repositories
- ✅ Easy to test and debug
- ✅ Automatic PR context (PR number, URL, etc.)

### Disadvantages
- ❌ Limited to GitHub repositories
- ❌ Usage limits on free tier
- ❌ Less control over execution environment

### Example Workflow
```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Code Review Agent
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_TOKEN: ${{ secrets.JIRA_TOKEN }}
          CONFLUENCE_TOKEN: ${{ secrets.CONFLUENCE_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m agent.review_agent \
            --pr-url "${{ github.event.pull_request.html_url }}"
```

## Option 2: GitHub App

### Architecture
```
GitHub PR Event → GitHub App Webhook → App Server → Agent → Review Comments
```

### Implementation
- **Setup**: Register GitHub App, install on repositories
- **Webhook**: GitHub sends webhook to app server
- **Permissions**: Read PRs, write comments
- **Deployment**: App server (can be serverless)

### Advantages
- ✅ Fine-grained permissions
- ✅ Works across multiple repositories
- ✅ Can comment as bot user
- ✅ Enterprise-friendly
- ✅ Scalable architecture

### Disadvantages
- ❌ More complex setup
- ❌ Requires app server infrastructure
- ❌ Webhook handling complexity

## Option 3: Jenkins + Webhook (Original Design)

### Architecture
```
GitHub PR Event → Webhook → Jenkins Job → Agent → Review Comments
```

### Implementation
- **Webhook**: Configure GitHub webhook to Jenkins endpoint
- **Jenkins Job**: Receives webhook, triggers agent
- **Execution**: Runs in Jenkins environment

### Advantages
- ✅ Full control over execution
- ✅ Enterprise CI/CD integration
- ✅ Custom build pipelines
- ✅ Resource management

### Disadvantages
- ❌ Requires Jenkins infrastructure
- ❌ Webhook configuration complexity
- ❌ More moving parts

## Option 4: Direct Webhook to Agent

### Architecture
```
GitHub PR Event → Webhook → Agent Endpoint → Review Comments
```

### Implementation
- **Endpoint**: Agent exposes HTTP endpoint
- **Webhook**: GitHub sends webhook directly to agent
- **Deployment**: Agent runs as service (container, serverless, etc.)

### Advantages
- ✅ Simplest architecture
- ✅ Fewer components
- ✅ Direct integration

### Disadvantages
- ❌ Security concerns (webhook validation)
- ❌ Scaling challenges
- ❌ Error handling complexity
- ❌ No built-in retry mechanism

## Option 5: Scheduled/Polling

### Architecture
```
Cron Job → Poll GitHub API → Agent → Review Comments
```

### Implementation
- **Scheduler**: Cron job or scheduled task
- **Polling**: Periodically check for new/updated PRs
- **Execution**: Run agent for each PR found

### Advantages
- ✅ No webhook setup
- ✅ Simple to implement
- ✅ Works with any infrastructure

### Disadvantages
- ❌ Delayed reviews (not real-time)
- ❌ Inefficient (polling overhead)
- ❌ May miss rapid PR updates

## Option 6: Other CI/CD Platforms

### Examples
- **GitLab CI**: `.gitlab-ci.yml` with PR merge request events
- **CircleCI**: Workflow triggered on PR events
- **Azure DevOps**: Pipeline triggered on PR events
- **Bitbucket Pipelines**: Pipeline triggered on PR events

### Advantages
- ✅ Works with existing CI/CD
- ✅ Platform-native integration

### Disadvantages
- ❌ Platform-specific implementation
- ❌ May require platform-specific changes

## Recommendation Matrix

| Use Case | Recommended Option |
|----------|-------------------|
| **Simple setup, GitHub only** | GitHub Actions |
| **Enterprise, multiple repos** | GitHub App |
| **Existing Jenkins infrastructure** | Jenkins + Webhook |
| **Serverless/cloud-native** | GitHub App or Direct Webhook |
| **Multi-platform support** | GitHub App or Jenkins |

## Migration Path

The agent implementation is **trigger-agnostic**. You can:

1. Start with **GitHub Actions** (easiest to set up)
2. Migrate to **GitHub App** (if you need multi-repo or enterprise features)
3. Use **Jenkins** (if you have existing infrastructure)

The core agent code remains the same - only the trigger mechanism changes.

## Implementation Notes

### For GitHub Actions
- Use `github.event.pull_request.html_url` for PR URL
- Store all tokens in GitHub Secrets
- Consider using self-hosted runners for cost control

### For GitHub App
- Validate webhook signatures
- Handle webhook delivery retries
- Use GitHub App installation tokens

### For Jenkins
- Configure webhook authentication
- Set up Jenkins job parameters
- Handle webhook payload parsing

