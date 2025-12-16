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

## Conclusion

✅ **We have full support for all core review actions:**
- Reading PRs
- Commenting on code
- Approving PRs
- Requesting changes
- Submitting formal reviews

The implementation is complete for the review workflow. No additional actions needed for basic review functionality.

