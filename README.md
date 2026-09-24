# RCM Opportunity Forecasting & Prior Authorization Intelligence

## Aim

To turn public Medicare Advantage enrollment data into clear, actionable business intelligence for
Revenue Cycle Management (RCM) teams -- showing where enrollment is growing, which insurance payers to
prioritize, where prior-authorization workload is concentrated, and what that growth is worth in dollars.

---

## Overview

This platform analyzes publicly available Medicare Advantage enrollment data covering over 36 million
members across all 50 states and thousands of counties. It answers four practical business questions:

1. **Where is enrollment growing fastest, and where is the untapped opportunity?**
2. **Which insurance payers are growing quickly and worth prioritizing for outreach?**
3. **Where is prior-authorization workload concentrated, so teams can plan capacity?**
4. **What is that enrollment growth worth in revenue terms?**

Every number shown is backed by a validation check, and every limitation of the underlying public data is
stated openly rather than hidden behind a confident-looking chart.

---

## Problem Statement

RCM and business development teams need to know where to focus their limited time and resources: which
states and counties are growing, which insurance payers are the best partners to pursue, and where
administrative workload (like prior authorization) is likely to be heaviest. Public government data holds
the answers, but it is large, partly hidden (some rows are suppressed for privacy), and easy to
misinterpret if not handled carefully. Teams need this turned into a single, trustworthy, easy-to-read
platform -- not a spreadsheet full of gaps and guesswork.

---

## Problems Found and Solutions

A structured review of the original version of this project found several issues that could have led to
misleading business decisions. Each was identified and corrected:

**Hidden data was silently treated as zero.** Government privacy rules hide roughly half of the raw data
rows. The original version ignored this, understating real enrollment. **Solution:** every enrollment
figure is now shown as an honest range (low to high), so no one mistakes a partial count for the full
picture.

**The forecast's accuracy claim was based on a single lucky test.** A forecast was judged reliable from
one snapshot in time, which can be misleading. **Solution:** the forecast is now tested 15 separate times
across different time windows and compared against a simple baseline every time, so its reliability is
proven, not assumed.

**Two features were accidentally the same thing under different names**, one meant to represent
authorization delays, which risked confusing users. **Solution:** removed the duplicate and replaced it
with a properly built, member-weighted exposure score.

**The market-opportunity scoring rewarded the wrong markets** -- it favored places that were already
saturated instead of places with room to grow. **Solution:** the scoring logic was corrected to reward
markets with real growth headroom, and the new ranking was stress-tested against alternate scoring
weights to confirm it holds up.

**The project could not be reliably rebuilt from scratch** -- a key step only existed in someone's personal
notebook. **Solution:** the entire pipeline now runs end-to-end with a single command, and every result
is reproducible by anyone on the team.

**There was no way to know if a check had actually passed or failed** -- every validation check always
printed "pass," regardless of the real numbers. **Solution:** every check now has a real, numeric pass/fail
threshold, and the results are visible and auditable.

---

## Key Features & Benefits

- **Honest enrollment reporting** -- every figure is shown as a range, reflecting real data limitations
  instead of hiding them.
- **Proven forecasting** -- the enrollment forecast is validated across 15 independent tests, not a single
  lucky guess, and clearly beats a simple baseline.
- **State and county-level market opportunity ranking** -- shows exactly where growth potential is
  highest, stress-tested against different scoring assumptions so the ranking can be trusted.
- **Payer scorecard** -- ranks insurance companies by growth, size, and administrative burden, so RCM
  teams know exactly which payers to prioritize for partnership and outreach.
- **Prior-authorization exposure view** -- shows where authorization workload is concentrated by plan and
  by member volume, helping teams plan staffing and capacity.
- **Revenue estimation** -- converts enrollment growth into a clearly labeled revenue estimate, with a
  transparent range (low, base, high) rather than a single misleading number.
- **Built-in validation dashboard** -- every underlying check is visible, with real pass/fail results, so
  the platform's reliability can be verified at a glance.
- **One-click, repeatable pipeline** -- the entire analysis can be rerun end-to-end at any time as new
  data becomes available.

---

## Architecture

![Pipeline Architecture](reports/figures/architecture_animated.gif)

Data flows in one direction, start to finish: public CMS data is loaded and cleaned, growth and
forecasting analysis run on top of it, prior-authorization and payer data are layered in, and every
result flows into a single validated dashboard -- so nothing shown to the end user skips the checks along
the way.

---

## Dashboard

### Executive Overview
A single-page summary of the most important numbers: current enrollment, growth rate, the best-performing
forecast model, and the top opportunity markets.

![Executive Overview](docs/assets/screenshots/01_overview.png)

### Enrollment Forecast
Shows the enrollment trend and compares forecasting models against each other and against a simple
baseline, so the chosen model's reliability is visible, not assumed.

![Enrollment Forecast](docs/assets/screenshots/02_forecast.png)

### Hierarchical Forecast
Breaks the national forecast down to the state and county level, clearly marking which regions' forecasts
are reliable (green) versus directional only (red).

![Hierarchical Forecast](docs/assets/screenshots/03_hierarchical.png)

### Growth Opportunity
An interactive map and ranking of every state and county by growth opportunity, with the scoring
methodology stress-tested for stability.

![Growth Opportunity](docs/assets/screenshots/04_growth.png)

### Payer Scorecard
Ranks insurance payers by growth, member scale, and prior-authorization burden -- the top candidates for
outreach and partnership.

![Payer Scorecard](docs/assets/screenshots/05_payer.png)

### PA Exposure
Shows how many health plan members fall into low, medium, and high prior-authorization exposure, weighted
by actual enrollment, not just plan counts.

![PA Exposure](docs/assets/screenshots/06_pa.png)

### Proxy Revenue
Converts the enrollment forecast into a clearly labeled revenue estimate range, with the underlying
assumption stated in plain language.

![Proxy Revenue](docs/assets/screenshots/07_revenue.png)

### Validation
Every automated check behind this platform, shown with its real result -- full transparency into how the
numbers were verified.

![Validation](docs/assets/screenshots/08_validation.png)

---

## Conclusion

This platform turns publicly available Medicare Advantage data into a trustworthy, decision-ready
business intelligence tool for RCM teams. A structured review found and corrected several issues that
could have led to misleading conclusions -- from hidden data being silently ignored, to an unproven
forecast, to a market-ranking system that rewarded the wrong markets. Every number shown today is backed
by a visible, auditable check, and every limitation of the underlying public data is stated openly rather
than hidden. The result is a platform that RCM and business teams can genuinely rely on to decide where to
focus growth efforts, which payers to prioritize, and where to plan for administrative workload -- with
the confidence that comes from knowing exactly how each number was produced and verified.
