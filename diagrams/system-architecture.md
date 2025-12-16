# System Architecture Diagram

## Component Architecture

```mermaid
graph TB
    subgraph "GitHub"
        GH[GitHub Repository]
        GA[GitHub Actions<br/>Workflow]
    end
    
    subgraph "CI/CD Environment"
        AG[Code Review Agent<br/>LangGraph State Machine]
    end
    
    subgraph "MCP Servers"
        GH_MCP[GitHub MCP Server<br/>FastMCP + PyGithub<br/>Real Implementation]
        JIRA_MCP[Jira MCP Server<br/>FastMCP + jira library<br/>Real API or Stubs]
        CONF_MCP[Confluence MCP Server<br/>FastMCP + LangChain ConfluenceLoader<br/>Real API, Stubs, or Semantic Search]
    end
    
    subgraph "Semantic Search"
        CHROMADB[ChromaDB<br/>Vector Store<br/>Optional]
    end
    
    subgraph "External Services"
        GH_API[GitHub API]
        JIRA_API[Jira API<br/>Real or Stub Data]
        CONF_API[Confluence API<br/>Real or Stub Data]
    end
    
    subgraph "LLM Services"
        LLM[OpenAI/Anthropic/Google<br/>gpt-3.5-turbo, claude-haiku, etc.]
    end
    
    subgraph "Observability"
        LS[LangSmith<br/>Optional Tracing]
    end
    
    GH -->|PR Event| GA
    GA -->|PR URL| AG
    
    AG -->|Tool Calls| GH_MCP
    AG -->|Tool Calls| JIRA_MCP
    AG -->|Tool Calls| CONF_MCP
    AG -->|LLM Requests| LLM
    AG -->|Traces| LS
    
    GH_MCP -->|API Calls| GH_API
    JIRA_MCP -->|API Calls or Stub Data| JIRA_API
    CONF_MCP -->|API Calls or Stub Data| CONF_API
    CONF_MCP -->|Semantic Search| CHROMADB
    
    GH_API -->|PR Data| GH_MCP
    JIRA_API -->|Ticket Data| JIRA_MCP
    CONF_API -->|Page Data| CONF_MCP
    
    GH_MCP -->|PR Details| AG
    JIRA_MCP -->|Acceptance Criteria| AG
    CONF_MCP -->|Domain Context| AG
    
    AG -->|Review Comments| GH_MCP
    GH_MCP -->|Post Comments| GH_API
    
    style GH_MCP fill:#90EE90
    style JIRA_MCP fill:#FFE4B5
    style CONF_MCP fill:#FFE4B5
    style CHROMADB fill:#FFB6C1
    style AG fill:#87CEEB
    style LLM fill:#DDA0DD
    style LS fill:#E6E6FA
```

## Legend
- **Solid lines**: Active data flow
- **Green**: Real implementation (GitHub MCP - always real)
- **Orange**: Dual mode (Jira/Confluence MCP - real API or stubs)
- **Pink**: Optional semantic search (ChromaDB)
- **Blue**: Agent component
- **Purple**: LLM service
- **Lavender**: Optional observability

## Key Features

- **GitHub Actions Integration**: Primary trigger mechanism (also supports Jenkins, other CI/CD)
- **MCP Architecture**: All external data access via MCP servers
- **Dual Mode Support**: Jira/Confluence can use real APIs or stub data
- **Semantic Search**: ChromaDB integration for automatic Confluence doc discovery
- **Multi-LLM Support**: OpenAI, Anthropic, Google providers
- **LangSmith Integration**: Optional observability and tracing

