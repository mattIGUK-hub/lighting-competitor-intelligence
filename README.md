# iGuzzini UK | Competitor Intelligence Technical Pilot

This is a **public-source research proof of concept**, separate from the iGuzzini UK Marketing Hub V85. It monitors public news discovery for **ERCO, Fagerhult, Zumtobel, XAL, TRILUX and Delta Light**.

## Current status

- GitHub integration and repository write access: **verified**
- Research collector, six source queries, initial JSON feed and demo dashboard: **uploaded**
- Python unit tests: **included in the workflow**
- First real GitHub Actions scan: **not yet run**
- GitHub Pages publishing and HTMLtoLink connection: **not yet verified**

## Set up the first live test

1. Open the repository **Settings → Pages**.
2. Under **Build and deployment**, set **Source → GitHub Actions**. Save if a Save button appears.
3. Open the repository **Actions** tab. If GitHub asks you to enable Actions, review and enable them.
4. Select **Refresh and publish public competitor intelligence** in the left sidebar.
5. Select **Run workflow**, keep branch **main**, then click the green **Run workflow**.
6. Open the new workflow run. Confirm that both jobs, **refresh** and **publish**, finish successfully. In the **Discover public competitor news** step, check the line with **Collection result** and the status for each brand.
7. When publishing succeeds, open the demo: **https://mattiguk-hub.github.io/lighting-competitor-intelligence/**. The published feed will be at **https://mattiguk-hub.github.io/lighting-competitor-intelligence/intelligence.json**.
8. Report any error to ChatGPT, including the step name and error message. Do not add confidential information to the public repository.

**Important:** GitHub Pages will not deploy until Pages is configured and the workflow runs. The demo will initially show zero records. The first live scan may return no findings, source errors, or irrelevant news; a successful build alone does not establish data quality.

## What the files do

| Path | Purpose |
|---|---|
| `sources.json` | Six Google News RSS searches for public competitor stories |
| `collector.py` | Retrieves feeds, validates record dates and source URLs, categorises and deduplicates findings |
| `docs/intelligence.json` | Public, machine-readable research feed, initially empty |
| `docs/index.html` | Responsive technical demo reading the separately updated feed |
| `tests/test_collector.py` | Offline parser/input-validation tests |
| `.github/workflows/refresh.yml` | Daily scheduled scan (07:15 UTC), manual trigger and explicit Pages publishing |

## How refresh works

GitHub Actions performs the source scan and commits the updated JSON feed. It then publishes the `docs` directory to GitHub Pages, including both the data and demo. The demo's **Refresh Intelligence** button loads the *latest published data*, without modifying the HTML or starting a new scan.

The schedule is 07:15 **UTC**, which is 08:15 British Summer Time. Scheduled workflows may be delayed and GitHub may disable an inactive public-repository schedule.

## Accuracy and security

- This is **public research discovery**, not a verified market intelligence report.
- Google News RSS is free but not a contracted API and may change or return incomplete results.
- Each automated record is marked `verification: needs_review`.
- A headline, keyword-derived category, or `UK` keyword tag is not proof that the claim is accurate or UK-specific.
- A Google News link may be an intermediary rather than the original publisher URL.
- The **BASIC ASSESSMENT** button returns record counts, not AI-authored strategic interpretation.
- Automated LinkedIn/Instagram collection is not part of this pilot.
- All files deployed with GitHub Pages are **public**. Never commit internal iGuzzini strategy, private metrics, customer details, credentials or access tokens.
- The existing iGuzzini UK Marketing Hub is unchanged.

## What's next

After the first live run, review each of the six source statuses and manually check a small sample of discoveries for accuracy. Only then should we connect the public feed to the existing Marketing Hub through a tested HTTPS/CORS request from HTMLtoLink.
