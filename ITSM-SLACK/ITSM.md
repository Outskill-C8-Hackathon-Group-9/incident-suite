# ITSM Integration

``` text
                    LangGraph
                        │
                        ▼
                 Decision Engine
                        │
                        ▼
                 Ticket Manager
                        │
          ┌─────────────┴─────────────┐
          │                           │
     Remediative                 Investigative
          │                           │
          ▼                           ▼
   Create Ticket               Create Ticket
          │                           │
          ▼                           ▼
 Execute Cookbook             Assign (Round Robin)
          │                           │
          ▼                           ▼
 Verify Outcome             Update Ticket Owner
          │                           │
     Fixed? │                          │
      Yes   ▼                          ▼
          Close Ticket            Human Investigation
                 └────────────┬────────────┘
                              ▼
                         Notification
```

## Overview

The ITSM component is responsible for all ticket lifecycle operations.
The LangGraph workflow never interacts directly with the ticketing
platform. Instead, it invokes a Ticket Manager abstraction.

Responsibilities:

-   Create tickets
-   Update ticket details
-   Assign investigative tickets
-   Close tickets after successful remediation

## Ticket Lifecycle

### Remediative Path

1.  Create ticket using the AI service account.
2.  Execute the remediation cookbook.
3.  Verify the outcome.
4.  Automatically close the ticket if verification succeeds.
5.  Send notification.

### Investigative Path

1.  Create ticket using the AI service account.
2.  Assign the ticket using the Round Robin policy.
3.  Return the assigned engineer to the orchestrator.
4.  Human engineer performs investigation.
5.  Ticket updates continue through the normal lifecycle.

## Ticket Manager Interface

``` python
create_ticket(...)
assign_ticket(...)
update_ticket(...)
close_ticket(...)
```

`assign_ticket()` returns the assigned engineer so downstream components
can notify the appropriate user.
