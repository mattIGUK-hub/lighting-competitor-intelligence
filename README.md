# iGuzzini UK | Public Competitor Marketing Research

Public, source-linked background data for the **Competitors** section of the iGuzzini UK Marketing Hub. The main Hub is a separate static HTML file hosted independently.

## Current features

- **Reviewed marketing comparisons:** \`docs/marketing-assessments.json\` contains six competitors versus iGuzzini across Messaging, Branding, Social Media, Events, Website and Content. Each assessment includes a source link, geographic scope and editorial comparison.
- **Conservative website-change monitoring:** \`monitor_sources.json\` defines selected public URLs. \`website_monitor.py\` checks their readable server HTML. \`docs/site-change-monitor.json\` publishes successes, access failures, initial baselines and subsequent changed-text signals.
- **Existing exploratory news feed:** \`collector.py\`, \`sources.json\` and \`docs/intelligence.json\` remain available for technical research, but are not part of the V89 comparison interface.
- **Automation:** GitHub Actions validates the collector, refreshes the news feed, checks selected public webpages and publishes the \`docs\` directory to GitHub Pages daily at 07:15 UTC. Manual execution is also available from Actions.

## Public published files

- Comparisons: https://mattiguk-hub.github.io/lighting-competitor-intelligence/marketing-assessments.json
- Source monitoring: https://mattiguk-hub.github.io/lighting-competitor-intelligence/site-change-monitor.json
- Earlier exploratory news feed: https://mattiguk-hub.github.io/lighting-competitor-intelligence/intelligence.json

## What Run Assessment actually does

The V89 Hub button requests the **latest published research dataset** and the **latest published source-monitor result**, then shows the selected competitor against iGuzzini in the six requested categories. It also compares the reviewed research section text against the last assessment saved in the same browser.

**It does not start a new GitHub Actions run or perform a fresh AI web research session.** Starting a GitHub Actions workflow from a public HTML page would require secure server-side authentication, which this implementation does not have.

The daily source monitor detects whether readable HTML on selected public webpages has changed since its prior successful scan. Such a change is a **research prompt**, not a verified marketing insight. Editorial assessments require reviewing the evidence and updating the public JSON. GitHub's workflow may republish those JSON changes without a new Hub HTML release.

## Access and data-quality limitations

- Only selected public HTML URLs are monitored; the checker cannot reliably assess all visual branding, every page or all published social media posts.
- Initial successful checks create baselines; a later successful check is needed before any comparison can detect a change.
- Some websites block scripted visitors with HTTP 403 or 429, and client-rendered content may be missing. Blocked sources must remain marked **unavailable**, never silently marked **unchanged**.
- Brand claims, opinions and inferred marketing strategy must remain clearly separated from confirmed source facts.
- UK examples are preferred. Global examples are explicitly marked as such.
- This GitHub repository and its Pages output are **public**. Never place iGuzzini internal plans, private customer data, credentials, marketing analytics or confidential observations here.
- No follower counts or speculative engagement metrics are collected. No paid API is required.
- GitHub schedule execution may be delayed or disabled if the repository is inactive.

## Maintenance

Review \`docs/marketing-assessments.json\` as new evidence becomes available, retaining source links and the actual \`reviewed_at\` date for the research. Add or remove official pages in \`monitor_sources.json\` as appropriate. Verify the Actions refresh and publish jobs after changes. The public data are versioned in Git history.

Tests: \`python -m unittest discover -s tests -v\`.
