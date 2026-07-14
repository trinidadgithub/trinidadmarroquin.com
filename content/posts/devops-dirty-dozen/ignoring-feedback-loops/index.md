+++
title = "The Signal You Ignored: The DevOps Ignoring Feedback Loops Anti-Pattern"
date = 2026-06-23T00:00:00-05:00
draft = false
description = "Part 6 of the DevOps Dirty Dozen series: how ignoring monitoring signals, user feedback, and anomaly warnings turns small problems into catastrophic failures — and what it takes to build a culture that listens."
tags = ["devops", "sre", "feedback-loops", "monitoring", "anomalies", "incidents", "observability"]
categories = ["DevOps Dirty Dozen"]
series = ["The DevOps Dirty Dozen"]
+++

Part 6 of the DevOps Dirty Dozen Series: *Quod non reficitur, deficit* — what is not renewed, deteriorates.

**Insight:** Emphasizes the importance of constant improvement through feedback.

Every engineer has a story about the alert that fired too many times, the dashboard that showed a slow climb, the user complaint that got buried in a ticket queue. And every engineer has a story about the night that same ignored signal became a full-blown incident.

Ignoring feedback loops is not a failure of tooling. It is a failure of response. The monitoring stack can be world-class, the dashboards immaculate, the on-call rotation perfectly staffed — and none of it matters if the organization has trained itself to look away.

In this sixth article of the DevOps Dirty Dozen, we examine how feedback loops atrophy, why teams rationalize ignoring signals, and what it takes to build a culture where feedback actually changes behavior.

{{< figure src="drowned-signal.svg" alt="A lone red alert line buried in a sea of gray noise lines" caption="The signal is usually there. The hard part is not detecting it. It is choosing to act." >}}

## The Anatomy Of Broken Feedback Loops

A feedback loop is any mechanism that returns information about a system's output back into its input. In DevOps, these loops include:

- Monitoring alerts and dashboards
- Incident postmortems and action items
- User complaints and feature requests
- Deployment failure rates and rollback triggers
- Performance regression detection
- Security scan findings

A broken feedback loop looks the same regardless of the source: the signal arrives, and nothing changes.

Here is what that looks like in practice:

1. **Alert Fatigue As Policy:** Alarms fire so frequently that the on-call engineer checks the channel and, seeing nothing burning, looks away. The one genuine alert is indistinguishable from the twenty false ones. Teams respond by tuning alert severity upward until nothing is urgent — and then the real emergency has no severity high enough to break through.

2. **Dashboards Without Decisions:** The team builds beautiful dashboards reviewed in weekly meetings. Metrics are up, metrics are down. The meeting ends. No action is taken. The dashboards become screensavers — visually present, functionally inert.

3. **Postmortems That End At The Document:** The incident is resolved. A postmortem is written. Action items are assigned. The document is filed. Six months later, the same incident happens again. The postmortem was written, but it was never read as a plan.

4. **The Buried User Report:** A user reports a subtle anomaly — increased latency at a specific time of day, an intermittent error in a non-critical path. The ticket is triaged as low priority. Weeks later, the anomaly surfaces as a production incident affecting the same path, now critical.

5. **The Gradual Climb:** CPU creeps up one percent per week. Memory fragmentation grows incrementally. Each individual change is too small to alert on. After six months, the system tips over during a routine deploy. The data was there the entire time. Nobody was watching for trends, only thresholds.

{{< figure src="gradual-climb.svg" alt="A line chart showing a slow upward trend over weeks with a sudden spike at the end labeled 'incident'" caption="The disaster did not happen in an instant. It was measured in weeks of ignored data." >}}

## The Cost Of Ignoring Feedback

The cost of broken feedback loops compounds because each ignored signal erodes the next one.

1. **Small Problems Become Large Ones:** Every production outage that could have been prevented by acting on a early warning represents debt that compounds in silence. The anomaly you ignore today is the P0 you wake up for tomorrow.

2. **Trust In Monitoring Collapses:** When alerts are routinely ignored, the entire monitoring investment is wasted. Engineers stop trusting the tools, then stop looking at them. The observability stack becomes a line item on a budget rather than an operational lever.

3. **On-Call Burnout Accelerates:** Responding to real incidents is exhausting. Responding to incidents that should never have happened — because a signal was ignored weeks ago — is demoralizing. Teams that ignore feedback loops burn through on-call engineers faster.

4. **Organizational Learning Stops:** Feedback loops are how teams learn. Without them, every incident is a novel surprise. The same root causes recur. The organization plateaus while the systems around it grow more complex.

5. **User Trust Erodes Slowly, Then All At Once:** Users notice when their feedback disappears into a void. They stop reporting issues. The silence is not a sign that things are working — it is a sign that users have given up.

{{< figure src="eroding-trust.svg" alt="A faucet labeled 'user feedback' dripping into a bucket with a crack at the bottom" caption="Every ignored signal is a crack in the organizational learning system." >}}

## A Real-World Example: The Latency That Did Not Matter

I worked with a team that ran a platform serving time-sensitive financial data. For three months, a monitoring dashboard showed a gradual latency increase in one API endpoint. The increase was small — fifty milliseconds over the baseline — and it only affected a non-critical reporting call used by internal teams.

The latency dashboard was reviewed in the weekly operations meeting. Each week, the same question: "Is this worth investigating?" Each week, the same answer: "It is not affecting customers. We will get to it."

The latency was a symptom of a connection pool leak in a shared library. The leak was gradual. The connection pool had reserve capacity, so the leak only manifested as slower acquisition times, not failures. The team knew about the library — it had been flagged in a dependency audit six months prior — but replacing it was shelved for "when we have time."

Week twelve was the failure point. The connection pool exhausted its reserves during a traffic spike triggered by a market event. The non-critical endpoint timed out. Then the timeout cascaded into the critical path because the shared library held connections across threads. The reporting endpoint took down the trading feed.

The incident cost more in engineering time alone than replacing the library would have cost ten times over. The signal was visible for three months. The team looked at it weekly. Nobody acted because the feedback loop ended at the dashboard.

What fixed it was not better monitoring. The monitoring was already good enough. What fixed it was a practice: every dashboard reviewed in the weekly meeting had to have a decision attached. If a metric had been trending in the same direction for three consecutive meetings, it was automatically escalated. The feedback loop was not broken at the instrumentation layer. It was broken at the response layer.

## Why Feedback Loops Break

Feedback loops do not break because engineers are lazy or indifferent. They break because of systemic pressures:

1. **Signal-To-Noise Ratio Deteriorates:** Every alert, dashboard, and report added to the ecosystem makes the next one harder to see. Teams add signals faster than they remove them. The noise drowns the signal.

2. **Action Requires Ownership:** A signal without an owner is noise. If nobody is responsible for responding to a metric trend, the trend will be observed indefinitely without action. Ownership is the difference between data and intelligence.

3. **Reactive Cultures Reward Heroism:** In organizations that celebrate the engineer who "saved the weekend," there is little incentive to prevent the weekend from needing saving. Ignoring early warnings allows incidents to become dramatic — and dramatic incidents generate recognition.

4. **Tooling Replaces Practice:** A team that buys a monitoring platform and declares observability "done" has confused the tool with the practice. The dashboard exists. The alert fires. But there is no habit of acting on the information. The loop is built but not closed.

5. **Feedback Fatigue:** When every signal demands a response, teams develop a protective numbness. The only way to preserve energy is to ignore everything until something catches fire. This is not a failure of attention. It is a failure of signal prioritization.

{{< figure src="noise-vs-signal.svg" alt="A person at a desk with hundreds of floating alert boxes, only one of which is red" caption="When everything is urgent, nothing is." >}}

## Closing The Loop

Fixing broken feedback loops does not require new tooling. It requires new habits.

1. **Audit Your Signals Quarterly:** Every three months, review every alert, dashboard, and automated report. Which ones drove a decision in the last quarter? Remove or tune the rest. Signal count should trend down, not up.

2. **Attach Decisions To Dashboards:** A dashboard without a decision attached is a screensaver. For every dashboard, define: "If this metric crosses X threshold, we do Y." If there is no Y, the dashboard does not need to exist.

3. **Create A Trend Review Practice:** Threshold alerts catch spikes. Trend alerts catch declines. Add a regular review of metrics moving in the wrong direction slowly — the one percent per week problems that become catastrophic in month six.

4. **Close Postmortem Action Items:** A postmortem without verified completion of action items is a diary entry. Track action items to closure. If an action item is not completed within two sprints, it needs a sponsor or it needs to be removed.

5. **Make User Feedback Visible:** User-reported issues should appear in the same dashboards as system metrics. If the only way to see user complaints is to search the ticket system, the feedback loop is broken before it starts. Surface user sentiment alongside CPU and latency.

6. **Celebrate Prevention, Not Heroism:** When an engineer identifies an early signal and prevents an incident, that should receive more recognition than the midnight heroics that could have been avoided. Shift the incentive from response to prevention.

{{< figure src="closed-loop.svg" alt="A circular flow from observe to decide to act to verify, labeled as a closed feedback loop" caption="A closed feedback loop turns data into improvement. An open one just collects observations." >}}

## Applying The Scientific Method

Broken feedback loops are a failure of the observation-to-action cycle. The scientific method provides a structure for repair:

1. **Observe:** What signals exist? Which ones are being ignored? Which ones drove action in the last month?

2. **Hypothesize:** "If we review this dashboard weekly with a decision requirement, we will catch regressions two weeks earlier on average."

3. **Test:** Implement the practice on one dashboard or one signal category for one month.

4. **Measure:** Did the practice change behavior? Were regressions caught earlier? Was an incident prevented?

5. **Iterate:** Expand the practice or adjust based on what was learned. The goal is not to monitor everything. It is to act on the right things.

## Carl Sagan's Baloney Detection Kit

When a signal is ignored, the justifications often sound reasonable. Apply critical thinking to evaluate them:

- **"It is probably nothing."** — On what evidence? Has this specific pattern preceded incidents before? "Probably" is not data.

- **"Nobody else is worried about it."** — Consensus is not evidence. If a metric is trending badly and nobody is concerned, the gap is in awareness, not in the metric.

- **"We will get to it when we have time."** — When has that ever happened? If there is no scheduled time to investigate, the statement is a polite way of saying "never."

- **"The alert has been firing for weeks and nothing happened."** — Survival bias. The alert has been firing because the condition exists. One week of non-failure does not mean the condition is safe.

- **"The dashboard looked fine."** — Did it, or did nobody look at the trend line instead of the current value? Most catastrophic signals are invisible at the last data point.

{{< figure src="dont-look-away.svg" alt="A person turning their head away from a blinking red dashboard light" caption="Looking away does not make the signal stop. It just delays the response." >}}

## Moving Forward Together

Every significant incident I have been part of had a precursor. A metric that drifted. A ticket that sat. An alert that fired but was auto-acked. The signal was almost never missing. The response was.

Feedback loops are the nervous system of an engineering organization. When they work, the organization detects and corrects before users notice. When they break, the organization operates blind until something crashes hard enough to be visible through the noise.

Closing the loop is not a technical problem. It is a practice problem. It requires the discipline to look at the data, the courage to act on incomplete information, and the honesty to admit when a dashboard has become decoration.

What signals is your organization ignoring right now? What metric has been trending in the wrong direction for weeks that nobody has escalated? The answer to that question might be the incident you prevent tomorrow.

## References

- [The DevOps Handbook](https://itrevolution.com/devops-handbook/) by Gene Kim, Patrick Debois, John Willis, and Jez Humble
- [Accelerate: The Science of Lean Software and DevOps](https://itrevolution.com/accelerate/) by Nicole Forsgren, Jez Humble, and Gene Kim
- [Google SRE Workbook — Monitoring Distributed Systems](https://sre.google/workbook/monitoring/)
- [DORA: Generative organizational culture](https://dora.dev/devops-capabilities/cultural/generative-organizational-culture)
- [The Three Ways: Principles Underpinning DevOps](https://itrevolution.com/articles/the-three-ways-principles-underpinning-devops/)
- [Honeycomb: Observability 101](https://www.honeycomb.io/observability)
- [Etsy's Debriefing Facilitation Guide](https://extfiles.etsy.com/DebriefingFacilitationGuide.pdf)
