# Slack Notification

``` text
                 Workflow Event
                       │
                       ▼
                Notification Node
                       │
          ┌────────────┴────────────┐
          │                         │
    Team Channel               Direct Message
          │                         │
          ▼                         ▼
   All Team Members          Assigned Engineer
```

## Notification Rules

### Investigative Incidents

-   Post incident summary to the team channel.
-   Send a direct message to the assigned engineer.
-   Include:
    -   Ticket ID
    -   Severity
    -   Host
    -   Summary
    -   Ticket link

### Remediative Incidents

-   Post to the team channel only.
-   Include:
    -   Ticket ID
    -   Remediation performed
    -   Verification result
    -   Final status (Closed)

No direct message is sent because no human owner is assigned.

## Inputs

The notification node consumes:

-   Ticket ID
-   Ticket URL
-   Severity
-   Incident summary
-   Assigned engineer (optional)
-   Verification status
