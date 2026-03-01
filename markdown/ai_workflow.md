First, the user inputs the URL to their product page.

We run a one-off browser use agent (using the browser use custom bu model) that pulls all use cases from the page plus any other relevant online information. This outputs a text description of what the product does.

Then, we have a claude API call. This claude call (using CLAUDE_MODEL) will take the information from the landing page. It will then expand and reason in depth on the description to generate a list of everything that the product/service does. Then, using the info of what the product does, it creates a list of compliance risks. This will require in depth prompting - you'll need to do in depth research with a normal claude instance. You'll need to prompt to find what portions of the product will have regulatory exposure, and then find exact regulatory risks (requires prompting + ability for claude to search the internet). The output of this claude call will be an array of text that contains the list of risks / relevant regulations and why that regulation applies to this product. It should be able to find microscopic diffs - humans can usually research the big diffs but not the small ones.
Output format (use professional field names):
- Regulation title
- Why it's a risk
- Other metadata as needed (e.g. jurisdiction, scope, source URL)
- Check interval in seconds (t) — how often this watch should run
- Current state of the regulation — snapshot from the internet at risk-creation time (updated on each run)

Then, using this list, you'll create a watch for every single regulation. The watches get all the info from the risks and store it with each associated watch. Each watch runs every t seconds (its check interval). How it'll work is a claude agent will have the ability to spawn in browseruse subagents (browseruse always uses its own custom bu model). The claude agent will take in the information about the risk/regulation and use the browser use agents to see if there are any changes. It'll read from the database to check the last state of the regulation. If there is any diff, it'll spawn in up to a total of 15 BU agents to find more information about the diff and what it means (from news, public guidelines, consulting firms, reuters, etc). The BU agents will have to navigate multi-step pages. Then the output will be:
- New AI-written state of the regulation — persisted on the watch for the next run
- Exact language diff — previous stored regulation text vs newly observed text; shown on the "runs" page (where each watch run's results are listed)
- AI summary of how to comply
- AI summary of the change

The last three things (language diff + how to comply + summary of change) will become a new linear ticket and slack message.