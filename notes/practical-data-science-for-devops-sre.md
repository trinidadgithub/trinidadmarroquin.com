# Practical Data Science For DevOps And SRE

## Purpose

Create a future content track focused on applying simple, grounded data science methods to DevOps and SRE practices. The goal is not prediction hype or complex machine learning. The goal is better operational awareness, clearer analysis, and more disciplined reliability conversations using practical statistical methods.

This track should connect the author's DevOps/SRE experience with prior data science training, including a post-graduate certificate in data science from the University of Texas at San Antonio.

## Working Thesis

DevOps and SRE teams already generate useful data through incidents, deployments, alerts, metrics, logs, tickets, postmortems, and infrastructure changes. Most teams do not need advanced AI to benefit from that data. They need basic, explainable analysis that helps them see patterns, ask better questions, and make better operational decisions.

Useful methods include:

- Trend detection
- Baseline comparison
- Simple anomaly awareness
- Percentiles instead of averages
- Counts, rates, and recurrence analysis
- Incident clustering by tags or symptoms
- Change correlation with incident windows
- Moving averages for capacity and saturation
- Alert quality analysis
- Lightweight reliability datasets built from tickets, postmortems, and metrics

## Tone And Scope

Tone should be:

- Professional but practical
- Grounded in engineering operations
- Explainable to platform engineers, cloud engineers, SREs, technical managers, and DevOps practitioners
- Skeptical of hype
- Focused on awareness, analysis, and decision support

Avoid:

- Overstated AI claims
- Black-box prediction framing
- Academic or overly mathematical language unless necessary
- Treating data science as a replacement for engineering judgment
- Vendor-driven observability language

Preferred framing:

> Practical data science for SRE is not about predicting every outage. It is about using simple, explainable methods to detect patterns earlier, reduce repeated failure modes, and make reliability conversations more evidence-based.

## Candidate Content Track Title

**Practical Data Science For DevOps And SRE**

## Candidate Field Notes

1. **Using Simple Trend Analysis For SRE Signals**
   - Latency, error rate, saturation, deploy frequency
   - Rolling windows and moving averages
   - Trend direction over exact prediction

2. **Alert Fatigue Analysis With Basic Counts And Rates**
   - Alert volume by service, severity, and time window
   - Actioned vs ignored alerts
   - Repeat offenders
   - Noisy alert retirement

3. **Detecting Recurring Incident Patterns From Postmortems**
   - Tagging incidents by service, symptom, root cause, contributing factor
   - Counting recurrence
   - Separating root cause from trigger

4. **Change Failure Rate Analysis Without Overengineering**
   - Deployments vs incidents
   - Change windows
   - Rollbacks, hotfixes, failed deploys
   - DORA-style framing without vanity metrics

5. **Capacity Forecasting With Moving Averages**
   - CPU, memory, disk, queue depth, connection counts
   - Simple projection windows
   - When simple trends are enough

6. **Using Percentiles Instead Of Averages In Reliability Reviews**
   - p50, p95, p99 latency
   - Tail behavior and user pain
   - Why averages hide operational risk

7. **Correlating Deployments With Incident Windows**
   - Timeline overlays
   - Change records, Git commits, infrastructure drift
   - Avoiding false causality

8. **Building A Lightweight Reliability Dataset From Tickets And Logs**
   - Minimal schema
   - Incident date, service, symptoms, severity, trigger, resolution, recurrence
   - CSV-first analysis before tooling

## SLI Lab Bridge

The field note **Building A Small SLI Lab With Flask, Prometheus, And Grafana** creates a practical dataset for the first few articles in this track. It should be treated as a reusable lab, not just a one-off observability example.

Useful extensions from that lab:

- Define a sample SLO, such as `99% successful eligible requests over 30 days`, using the request-success SLI.
- Add a simple error budget calculation to show how different 5xx rates consume reliability budget over time.
- Add alerting rules for high 5xx error rate and sustained p95 latency once the SLO is clear.
- Export Prometheus data and analyze it with a small CSV or Python notebook workflow.
- Compare average latency against p95 and p99 latency to show how averages hide tail behavior.
- Use the generated histogram data as source material for **Using Percentiles Instead Of Averages In Reliability Reviews**.

The most natural follow-up is the percentiles field note because the lab already produces the data needed to compare average latency, typical latency, and tail latency without inventing a separate example.

## Reusable Prompt For Future Work

Use this prompt to restart the content track:

```text
I want to create a practical DevOps/SRE content track called "Practical Data Science For DevOps And SRE".

Context:
I have DevOps/SRE experience and a post-graduate certificate in data science from the University of Texas at San Antonio. I want to apply simple, well-grounded data science methods to operational engineering work. This should not be hype-driven or overly academic. The focus is additional awareness, better analysis, clearer reliability conversations, and reusable field-note patterns.

Tone:
- Professional but practical
- Written like engineering field notes
- Clear enough for platform engineers, cloud engineers, SREs, DevOps practitioners, and technical managers
- Avoid hype, black-box prediction claims, and vendor language
- Emphasize explainable methods and engineering judgment

Core thesis:
DevOps and SRE teams already produce useful data through alerts, incidents, deployments, tickets, logs, metrics, postmortems, and infrastructure changes. Basic data science methods such as trend analysis, baseline comparison, percentiles, recurrence counts, simple clustering, moving averages, and change correlation can improve operational awareness without requiring complex machine learning.

Please help me draft a field note for one of these topics:
1. Using Simple Trend Analysis For SRE Signals
2. Alert Fatigue Analysis With Basic Counts And Rates
3. Detecting Recurring Incident Patterns From Postmortems
4. Change Failure Rate Analysis Without Overengineering
5. Capacity Forecasting With Moving Averages
6. Using Percentiles Instead Of Averages In Reliability Reviews
7. Correlating Deployments With Incident Windows
8. Building A Lightweight Reliability Dataset From Tickets And Logs

For the selected topic, include:
- Strong title
- Short summary paragraph
- Problem statement
- Why the method matters to DevOps/SRE
- Minimal example dataset or table
- Simple analysis approach
- What decisions the analysis can support
- Risks, caveats, and false conclusions to avoid
- Practical next steps

Keep the content grounded, practical, and suitable for publishing as a field note on an engineering blog.
```

## First Recommended Article

Start with **Using Percentiles Instead Of Averages In Reliability Reviews**. Use **Alert Fatigue Analysis With Basic Counts And Rates** as the likely second article.

Reasoning:

- Both are immediately useful to SRE and DevOps readers.
- Both avoid heavy math.
- Both connect directly to observability, incidents, and operational decisions.
- Both can include small example tables and simple calculations.
- Both provide a strong bridge between data science fundamentals and reliability engineering.

Status:

- **Using Percentiles Instead Of Averages In Reliability Reviews** has been drafted as the first post in `content/posts/practical-data-science-for-devops/`.
- The article uses the SLI lab as the hands-on validation environment.

## Notes For Later

- Consider creating a `Practical Data Science For DevOps And SRE` series if the first two field notes work well.
- Keep examples small and reproducible with CSV, shell, Python, or spreadsheet workflows.
- Prefer explainability over automation.
- Emphasize that statistical signals should support engineering investigation, not replace it.
