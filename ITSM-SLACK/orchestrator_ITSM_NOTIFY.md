# LangGraph Orchestrator Integration

## Workflow

``` 
     │
     ▼
Decision Engine
     │
     ├───────────────┐
     │               │
     ▼               ▼
Remediative    Investigative
     │               │
     ▼               ▼
 Ticket Manager   Ticket Manager
     │               │
 Execute Fix    Round Robin Assign
     │               │
 Verify          Notify
     │
 Close Ticket
     │
 Notify
```

## Responsibilities

### Decision Engine

Determines whether an incident is:

-   Remediative
-   Investigative

### Ticket Manager

Owns every interaction with the ITSM platform.

### Notification Node

Consumes ticket information returned by the Ticket Manager and publishes
notifications.

## Design Principles

-   LLM performs reasoning and classification.
-   Ticket operations are deterministic.
-   Round Robin assignment is deterministic.
-   Notification logic is independent of ticketing logic.
-   Components communicate through structured state rather than
    platform-specific APIs.
