Execute a compliance monitoring pass for this watch.

## WATCH DETAILS
- **Name:** {watch_name}
- **Description:** {watch_description}
- **Run ID:** {run_id}

## WATCH CONFIG
{watch_config}

## INSTRUCTIONS

1. Read the watch config above. Identify the primary target (first entry in `targets`).
2. Spawn a browser agent for the primary target with precise extraction instructions.
3. If additional targets exist, spawn agents for them (max 3 more).
4. Summarize what you dispatched and finish.

Do NOT over-think. Spawn agents and summarize. The browser agents handle the actual web navigation.