# Stub Data Format Specification

This document defines the format for stub data files that demo projects can provide for Jira and Confluence context.

## Overview

Stub data files allow demo projects to provide realistic context for code reviews without requiring real Jira or Confluence API access. The format matches the real API response structure for seamless switching.

## Jira Stub Data Format

### File: `jira-stubs.json`

```json
{
  "tickets": {
    "TICKET-KEY": {
      "id": "string",
      "key": "string",
      "summary": "string",
      "description": "string",
      "status": "string",
      "assignee": {
        "displayName": "string",
        "emailAddress": "string"
      },
      "acceptanceCriteria": ["string"],
      "labels": ["string"],
      "issueType": "string",
      "priority": "string",
      "created": "ISO8601 datetime",
      "updated": "ISO8601 datetime"
    }
  },
  "relatedTickets": {
    "TICKET-KEY": ["TICKET-KEY", "TICKET-KEY"]
  }
}
```

### Example

```json
{
  "tickets": {
    "AUTH-101": {
      "id": "10123",
      "key": "AUTH-101",
      "summary": "Implement OAuth2 authentication",
      "description": "Add OAuth2 authentication flow for user login. Support Google and GitHub providers.",
      "status": "In Progress",
      "assignee": {
        "displayName": "Jane Developer",
        "emailAddress": "jane@example.com"
      },
      "acceptanceCriteria": [
        "User can log in with Google OAuth2",
        "User can log in with GitHub OAuth2",
        "Session is maintained for 24 hours",
        "Logout functionality works correctly",
        "Error handling for failed authentication"
      ],
      "labels": ["authentication", "security", "backend", "oauth2"],
      "issueType": "Story",
      "priority": "High",
      "created": "2024-01-15T10:00:00.000Z",
      "updated": "2024-01-20T14:30:00.000Z"
    },
    "AUTH-102": {
      "id": "10124",
      "key": "AUTH-102",
      "summary": "Add password reset functionality",
      "description": "Implement password reset flow with email verification and secure token generation.",
      "status": "To Do",
      "assignee": null,
      "acceptanceCriteria": [
        "User can request password reset via email",
        "Reset email is sent within 5 minutes",
        "Reset link expires after 1 hour",
        "Password is securely hashed before storage"
      ],
      "labels": ["authentication", "security", "email"],
      "issueType": "Story",
      "priority": "Medium",
      "created": "2024-01-16T09:00:00.000Z",
      "updated": "2024-01-16T09:00:00.000Z"
    }
  },
  "relatedTickets": {
    "AUTH-101": ["AUTH-102", "AUTH-103"],
    "AUTH-102": ["AUTH-101"]
  }
}
```

### Field Descriptions

- **`tickets`**: Object mapping ticket keys to ticket data
  - **`id`**: Internal Jira ticket ID
  - **`key`**: Ticket key (e.g., "AUTH-101")
  - **`summary`**: Short description of the ticket
  - **`description`**: Detailed description
  - **`status`**: Current status (e.g., "To Do", "In Progress", "Done")
  - **`assignee`**: Person assigned to ticket (can be null)
  - **`acceptanceCriteria`**: Array of acceptance criteria strings
  - **`labels`**: Array of label strings
  - **`issueType`**: Type of issue (e.g., "Story", "Bug", "Task")
  - **`priority`**: Priority level (e.g., "Low", "Medium", "High", "Critical")
  - **`created`**: ISO8601 datetime when ticket was created
  - **`updated`**: ISO8601 datetime when ticket was last updated

- **`relatedTickets`**: Object mapping ticket keys to arrays of related ticket keys

## Confluence Stub Data Format

### File: `confluence-stubs.json`

```json
{
  "pages": {
    "PAGE-ID": {
      "id": "string",
      "title": "string",
      "space": {
        "key": "string",
        "name": "string"
      },
      "body": {
        "storage": {
          "value": "HTML content"
        }
      },
      "version": {
        "number": 1
      },
      "created": "ISO8601 datetime",
      "updated": "ISO8601 datetime"
    }
  },
  "spaces": {
    "SPACE-KEY": {
      "key": "string",
      "name": "string",
      "description": "string"
    }
  }
}
```

### Example

```json
{
  "pages": {
    "123456": {
      "id": "123456",
      "title": "Authentication Architecture",
      "space": {
        "key": "ENG",
        "name": "Engineering"
      },
      "body": {
        "storage": {
          "value": "<h1>Authentication Architecture</h1><p>Our authentication system uses OAuth2 with the following components:</p><h2>Flow</h2><ol><li>User initiates login</li><li>Redirect to OAuth provider</li><li>Callback with authorization code</li><li>Exchange code for access token</li><li>Store session in Redis</li></ol><h2>Security Considerations</h2><ul><li>All tokens are encrypted</li><li>Session timeout: 24 hours</li><li>Refresh tokens rotate every 7 days</li></ul>"
        }
      },
      "version": {
        "number": 3
      },
      "created": "2024-01-10T09:00:00.000Z",
      "updated": "2024-01-18T15:20:00.000Z"
    },
    "789012": {
      "id": "789012",
      "title": "API Design Guidelines",
      "space": {
        "key": "ENG",
        "name": "Engineering"
      },
      "body": {
        "storage": {
          "value": "<h1>API Design Guidelines</h1><h2>REST API Standards</h2><ul><li>Use HTTP status codes correctly (200, 201, 400, 401, 404, 500)</li><li>Version APIs in URL path: /api/v1/...</li><li>Return consistent error formats</li><li>Document with OpenAPI 3.0</li><li>Use pagination for list endpoints</li></ul><h2>Authentication</h2><p>All API endpoints require Bearer token authentication in the Authorization header.</p>"
        }
      },
      "version": {
        "number": 2
      },
      "created": "2024-01-05T10:00:00.000Z",
      "updated": "2024-01-12T11:30:00.000Z"
    }
  },
  "spaces": {
    "ENG": {
      "key": "ENG",
      "name": "Engineering",
      "description": "Engineering documentation and guidelines"
    },
    "PROD": {
      "key": "PROD",
      "name": "Product",
      "description": "Product requirements and specifications"
    }
  }
}
```

### Field Descriptions

- **`pages`**: Object mapping page IDs to page data
  - **`id`**: Confluence page ID
  - **`title`**: Page title
  - **`space`**: Space information
    - **`key`**: Space key (e.g., "ENG")
    - **`name`**: Space name (e.g., "Engineering")
  - **`body.storage.value`**: HTML content of the page
  - **`version.number`**: Version number of the page
  - **`created`**: ISO8601 datetime when page was created
  - **`updated`**: ISO8601 datetime when page was last updated

- **`spaces`**: Object mapping space keys to space information
  - **`key`**: Space key
  - **`name`**: Space name
  - **`description`**: Space description

## Usage in Demo Projects

### Creating Stub Files

1. Create `stubs/` directory in your demo project
2. Create `jira-stubs.json` with your ticket data
3. Create `confluence-stubs.json` with your documentation
4. Reference in workflow:

```yaml
env:
  JIRA_STUB_DATA_PATH: ./stubs/jira-stubs.json
  CONFLUENCE_STUB_DATA_PATH: ./stubs/confluence-stubs.json
```

### Linking PRs to Stubs

The agent extracts ticket IDs from PR descriptions or labels. Make sure your stub data includes tickets that match:

- PR description: "Fixes AUTH-101"
- PR labels: `["AUTH-101"]`
- PR title: "AUTH-101: Implement OAuth2"

The agent will look up "AUTH-101" in the stub data.

### Linking to Confluence Pages

The agent can identify Confluence pages from:
- Jira ticket descriptions (if they reference pages)
- PR descriptions
- Configuration in workflow

You can also configure specific pages:
```yaml
env:
  CONFLUENCE_PAGE_IDS: "123456,789012"  # Comma-separated page IDs
```

## Validation

The agent validates stub data on load:
- JSON structure must be valid
- Required fields must be present
- Ticket keys must be unique
- Related tickets must reference existing tickets

If validation fails, the agent logs errors and falls back to default minimal stubs.

## Best Practices

1. **Keep it realistic**: Use realistic ticket data that matches your project
2. **Include acceptance criteria**: These are crucial for code review context
3. **Link related tickets**: Use `relatedTickets` to show relationships
4. **Update regularly**: Keep stub data in sync with actual project state
5. **Version control**: Commit stub files to your repository
6. **Document**: Add comments in JSON (though not standard, can use `_comment` fields)

