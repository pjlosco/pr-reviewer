# Token Handling and CI System Compatibility

## Overview

The PR Review Agent uses environment variables for all authentication tokens. This approach is **CI-agnostic** and works with all CI/CD systems without modification.

## Current Implementation

The GitHub MCP server (and all other components) simply read tokens from environment variables:

```python
token = os.getenv("GITHUB_TOKEN")
```

This is the **standard approach** used by all CI systems.

## CI System Compatibility

### ✅ GitHub Actions
- **Token**: `GITHUB_TOKEN` is automatically provided
- **Setup**: No configuration needed - just use `${{ secrets.GITHUB_TOKEN }}`
- **Permissions**: Automatically scoped to repository
- **Workflow**:
  ```yaml
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  ```

### ✅ Jenkins
- **Token**: Set as environment variable or use Credentials plugin
- **Setup**: Add token to Jenkins credentials or environment
- **Workflow**:
  ```groovy
  environment {
    GITHUB_TOKEN = credentials('github-token')
  }
  ```
  Or via webhook handler:
  ```python
  os.environ['GITHUB_TOKEN'] = jenkins_credentials.get('github-token')
  ```

### ✅ GitLab CI
- **Token**: Set as CI/CD variable
- **Setup**: Add token in GitLab project settings → CI/CD → Variables
- **Workflow**:
  ```yaml
  variables:
    GITHUB_TOKEN: $GITHUB_TOKEN
  ```

### ✅ CircleCI
- **Token**: Set as environment variable in project settings
- **Setup**: Add token in CircleCI project settings → Environment Variables
- **Workflow**:
  ```yaml
  environment:
    GITHUB_TOKEN: $GITHUB_TOKEN
  ```

### ✅ Azure DevOps
- **Token**: Set as pipeline variable (secret)
- **Setup**: Add token in pipeline variables (mark as secret)
- **Workflow**:
  ```yaml
  variables:
    GITHUB_TOKEN: $(github-token)
  ```

### ✅ Other CI Systems
- **Any CI system** that supports environment variables works
- No code changes needed
- Just set `GITHUB_TOKEN` environment variable

## Token Requirements

### GitHub Token Permissions

For the PR Review Agent to work, the GitHub token needs:

- **`repo`** scope (for private repos) OR
- **`public_repo`** scope (for public repos only)
- Specifically needs:
  - `pull_requests: read` - To fetch PR details
  - `pull_requests: write` - To post review comments
  - `contents: read` - To read repository contents

### Token Types

1. **Personal Access Token (PAT)**
   - User creates token with required scopes
   - Works for all repositories user has access to
   - Good for: Personal projects, small teams

2. **GitHub App Token**
   - App-based authentication
   - Fine-grained permissions
   - Better for: Enterprise, multiple repos
   - Auto-rotates

3. **GitHub Actions Token** (automatic)
   - Automatically provided in GitHub Actions
   - Scoped to current repository
   - No setup needed
   - Good for: GitHub-hosted repos

## Security Best Practices

1. **Never commit tokens to code**
   - Always use secrets/environment variables
   - Use CI system's secret management

2. **Use least privilege**
   - Only grant minimum required permissions
   - Use repository-scoped tokens when possible

3. **Rotate tokens regularly**
   - Especially for long-lived tokens
   - GitHub Apps auto-rotate (better for enterprise)

4. **Monitor token usage**
   - Check GitHub token usage logs
   - Set up alerts for unusual activity

## Implementation Notes

### Why Environment Variables?

✅ **Pros:**
- Works with ALL CI systems
- Standard practice
- Simple implementation
- No CI-specific code needed
- Easy to test locally

❌ **Cons:**
- None! This is the industry standard

### Alternative Approaches (Not Recommended)

1. **Config files**: ❌ Not secure, CI-specific
2. **Command-line args**: ❌ Visible in logs, not secure
3. **CI-specific APIs**: ❌ Would require different code per CI system

## Testing Locally

For local testing, just set the environment variable:

```bash
export GITHUB_TOKEN="your_token_here"
python app.py --pr-url "https://github.com/owner/repo/pull/123"
```

## Conclusion

**The current implementation is perfect for all CI systems.** 

- ✅ No changes needed for different CI systems
- ✅ Standard approach used industry-wide
- ✅ Works with GitHub Actions, Jenkins, GitLab, CircleCI, Azure DevOps, etc.
- ✅ Simple and secure

The agent code doesn't need to know which CI system is running it - it just reads environment variables, which all CI systems support.

