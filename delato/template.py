NEW_TICKET_SUBJECT="[delato] Issue '''$$description''' found in host $$host (ID: $$alarm_id)."

NEW_TICKET_BODY="""

Alarm '''$$description''' has not been resolved within its defined
severity expiration ($$expiration seconds).

** Details **

- Host: $$host.
- Description: $$description.
- Severity: $$severity.
- Age: $$age.


** Please take the appropriate actions to resolve the issue.

-- Ticket automatically created by delato. --
"""

UPDATE_TICKET_BODY="""
Friendly reminder for acting in the problem described above.

Please take the appropriate actions to resolve the issue.

Ticket automatically updated by delato.
"""

CLOSE_TICKET_BODY="""
The issue described is no longer present.

Thanks for the accurate response.

Ticket automatically closed by delato.
"""
