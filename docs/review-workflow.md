# Review Workflow and Actions

## Overview

This document outlines the review actions available to the PR Review Agent and how they map to human reviewer actions.

## Current Implementation

### ✅ What We Have

1. **`get_pr_details()`** - Fetch PR information
   - PR diff, description, author, files, commits, labels
   - ✅ Covers: Reading PR and understanding changes

2. **`post_review_comment()`** - Post individual comments
   - General PR comments
   - File-level comments
   - Line-specific comments
   - ✅ Covers: Commenting on specific issues

3. **`post_review_comments()`** - Post multiple comments
   - Batch posting for efficiency
   - ✅ Covers: Posting multiple review points

4. **`submit_review()`** - Submit formal review (NEW)
   - Approve PR
   - Request changes (block PR)
   - Comment only (no approval/block)
   - ✅ Covers: Formal review decision

## Human Reviewer Actions

### What Human Reviewers Do

1. ✅ **Read PR** - `get_pr_details()` covers this
2. ✅ **Comment on code** - `post_review_comment()` covers this
3. ✅ **Comment on multiple lines** - `post_review_comments()` covers this
4. ✅ **Approve PR** - `submit_review(event="APPROVE")` covers this
5. ✅ **Request changes** - `submit_review(event="REQUEST_CHANGES")` covers this
6. ✅ **Submit review with comments** - `submit_review()` with comments covers this

### What We Don't Support (Out of Scope)

1. ❌ **Merge PR** - Not a review action, handled by CI/CD or manual merge
2. ❌ **Close PR** - Not a review action
3. ❌ **Assign reviewers** - Not typically done during review
4. ❌ **Add labels** - Could be added if needed, but not core review action
5. ❌ **Dismiss reviews** - Not needed for automated reviews

## Review Decision Logic

The agent should decide review outcome based on analysis:

### Approve (`event="APPROVE"`)
- Use when: Code meets all requirements, no blocking issues
- Conditions:
  - All acceptance criteria met (if Jira context available)
  - No critical issues found
  - Code follows domain guidelines (if Confluence context available)
  - Human-focused review criteria pass

### Request Changes (`event="REQUEST_CHANGES"`)
- Use when: Critical issues found that block merge
- Conditions:
  - Critical bugs or security issues
  - Missing required functionality
  - Violates architectural guidelines
  - Fails acceptance criteria

### Comment (`event="COMMENT"`)
- Use when: Issues found but not blocking
- Conditions:
  - Minor improvements suggested
  - Best practice recommendations
  - Non-critical issues
  - Code works but could be better

## Workflow Recommendation

### Option 1: Comments Only (Current Default)
```
1. Analyze code
2. Generate review comments
3. Post comments via post_review_comments()
4. Submit review as COMMENT (optional)
```
**Use case**: Provide feedback without blocking

### Option 2: Formal Review with Decision
```
1. Analyze code
2. Determine review outcome (approve/request changes/comment)
3. Generate review comments
4. Submit review with event and comments
```
**Use case**: Automated approval/rejection based on criteria

## Implementation Notes

### When to Use Each Tool

**`post_review_comment()` / `post_review_comments()`**
- Use for: Detailed feedback on specific lines/files
- Best for: Educational feedback, suggestions
- Doesn't: Approve or block PR

**`submit_review()`**
- Use for: Formal review decision
- Best for: Automated approval/rejection
- Does: Approve, request changes, or comment with decision

### Combining Tools

The agent can:
1. Post detailed comments first (`post_review_comments()`)
2. Then submit formal review (`submit_review()`)
3. Or do both in one call (`submit_review()` with comments parameter)

## Future Enhancements (If Needed)

1. **Add labels** - Could add labels like "needs-review", "approved", etc.
2. **Request specific reviewers** - Could request human review for complex PRs
3. **Update PR status** - Could set PR status/checks
4. **Comment on commits** - Could review individual commits

These are not core review actions and can be added later if needed.

## What Review Comments Look Like

### End-to-End Flow

The agent follows this flow to post review comments:

1. **Analyze Code** → LLM analyzes PR changes against acceptance criteria and domain context
2. **Generate Comments** → LLM generates structured review comments with file paths and line numbers
3. **Post Comments** → Comments are posted to GitHub PR via GitHub MCP server

### Comment Types

#### 1. Summary Comment (GitHub Actions)

In GitHub Actions, the agent posts a summary comment with the review decision:

```markdown
**Review Decision: APPROVE** ✅

Code review completed. The implementation meets all acceptance 
criteria from DEMO-101. The OAuth2 authentication flow is correctly 
implemented with proper session management.

---
*Note: GitHub Actions cannot submit official reviews, so this is posted as a comment.*
```

#### 2. Line-Specific Comments

Comments on specific lines appear in the "Files changed" tab:

**Example:**
- **File**: `src/api.py`
- **Line**: 45
- **Comment**: 
  ```
  Consider returning proper HTTP status codes. According to the 
  API Design Guidelines, authentication errors should return 
  401 Unauthorized, not just an error message in the response body.
  ```

#### 3. File-Level Comments

General comments about a file:

**Example:**
- **File**: `src/auth.py`
- **Comment**:
  ```
  **File: src/auth.py**
  
  Overall structure looks good. Consider adding more comprehensive 
  error handling for edge cases like network timeouts during OAuth 
  token exchange.
  ```

### Review Decision Format

The agent determines one of three review decisions:

#### APPROVE ✅
```markdown
**Review Decision: APPROVE** ✅

Code review completed. All acceptance criteria met, no critical 
issues found. Ready to merge.
```

#### REQUEST CHANGES ❌
```markdown
**Review Decision: REQUEST CHANGES** ❌

Code review completed with 3 comment(s). Critical issues found 
that must be addressed:
- Missing error handling
- Security concern with token storage
- Performance issue in algorithm

Please address these issues before merging.
```

#### COMMENT 💬
```markdown
**Review Decision: COMMENT** 💬

Code review completed with 2 comment(s). Code is acceptable but 
has some suggestions for improvement.
```

### Complete Example

Here's what a full review looks like on a PR:

**Conversation Tab:**
```
[AI Code Review Bot] - 2 minutes ago
**Review Decision: REQUEST CHANGES** ❌

Code review completed with 4 comment(s).

Issues found:
- Missing HTTP status codes in API responses
- Performance concern with O(n*k) algorithm
- Missing error handling for edge cases

Please address the critical issues before merging.

---
*Note: GitHub Actions cannot submit official reviews, so this is posted as a comment.*
```

**Files Changed Tab:**
```
src/api.py
  Line 45: Consider returning proper HTTP status codes...
  Line 67: Return 404 when session not found...

src/leetcode_sliding_window.py
  Line 15: Use sliding window technique for O(n) complexity...

src/auth.py
  Line 52: Add timeout handling for OAuth token exchange...
```

### GitHub Actions Limitation

**Important**: GitHub Actions cannot submit official reviews (approve/request changes). The agent automatically:

1. Detects GitHub Actions environment
2. Posts review decision as a comment instead
3. Posts all line-specific and file-level comments normally
4. Includes a note explaining the limitation

This provides the same feedback without hitting GitHub's restrictions.

### Outside GitHub Actions

When running in other environments (local, Jenkins, etc.), the agent can:
- Submit official reviews with approve/request changes
- Post line-specific comments as part of the review
- Block PRs from merging if REQUEST_CHANGES is used

## Conclusion

✅ **We have full support for all core review actions:**
- Reading PRs
- Commenting on code (line-specific, file-level, general)
- Posting review decisions (as comments in GitHub Actions, official reviews elsewhere)
- Requesting changes
- Providing context-aware feedback

The implementation is complete and fully wired end-to-end. All review comments are posted via the GitHub MCP server and appear directly on the PR.

