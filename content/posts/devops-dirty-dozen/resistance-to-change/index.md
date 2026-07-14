+++
title = "The Drag Of Yesterday: The DevOps Resistance To Change Anti-Pattern"
date = 2026-06-27T00:00:00-05:00
draft = false
description = "Part 10 of the DevOps Dirty Dozen series: how resistance to change preserves outdated processes, increases hidden risk, and what teams can do to evolve safely."
tags = ["devops", "sre", "change-management", "legacy-systems", "platform-engineering", "culture"]
categories = ["DevOps Dirty Dozen"]
series = ["The DevOps Dirty Dozen"]
+++

Part 10 of the DevOps Dirty Dozen Series: *Cui resistitur, crescere videtur* — what is resisted appears to grow.

**Insight:** Suggests that resisting change only amplifies the challenges.

Change resistance is easy to misread as stubbornness. Sometimes it is. More often, it is a signal that the organization has not made change safe enough, clear enough, or valuable enough for people to trust it.

In DevOps, resistance to change shows up as old deployment processes nobody wants to touch, manual approvals that outlived their original risk, legacy tools kept alive by fear, and infrastructure patterns everyone complains about but nobody replaces. The team knows the system is aging. The work to improve it keeps getting deferred.

The irony is that avoiding change does not preserve stability. It usually preserves fragility.

{{< figure src="legacy-anchor.svg" alt="A delivery pipeline chained to a heavy anchor labeled legacy process" caption="Stability is not the same as immobility. Some anchors look like process." >}}

## The Anatomy Of Resistance To Change

Resistance to change appears in many forms. Some are cultural. Some are technical. Most are both.

1. **The Sacred Manual Step:** A manual approval, spreadsheet, or checklist remains mandatory because it once prevented a real problem. Nobody can explain whether it still reduces risk, but removing it feels dangerous.

2. **The Untouchable Tool:** A legacy system remains central because everyone is afraid to migrate away from it. It is brittle, poorly understood, and increasingly expensive, but it is familiar.

3. **The Frozen Architecture:** Teams work around old design decisions instead of revisiting them. New services inherit old constraints because changing the foundation would require coordination.

4. **The Fear-Based No:** New practices are rejected before they are evaluated. Infrastructure as code, GitOps, automated testing, progressive delivery, or better observability are dismissed because the first imagined failure ends the conversation.

5. **The Permanent Pilot:** A new approach is tested forever but never adopted. The pilot succeeds technically, but the organization never commits to changing the default path.

{{< figure src="permanent-pilot.svg" alt="A small pilot project circling endlessly beside a blocked main road" caption="A pilot that never changes the default path is just a sandbox with better press." >}}

## The Cost Of Standing Still

Staying with familiar tools and processes may feel safe, but the cost compounds.

1. **Operational Risk Grows Quietly:** Unsupported versions, manual runbooks, undocumented exceptions, and fragile integrations accumulate. The system becomes riskier while appearing unchanged.

2. **Delivery Slows Down:** Teams spend more time navigating old process than delivering value. The friction becomes normal, so nobody counts it.

3. **Talent Burns Out Or Leaves:** Engineers who repeatedly propose improvements and see them deferred eventually stop trying. Some disengage. Some leave. The organization loses the people most capable of helping it evolve.

4. **Security Posture Degrades:** Old tooling may lack modern auditability, encryption defaults, policy enforcement, or identity integration. Avoiding migration becomes a security decision, even when nobody labels it that way.

5. **Change Eventually Arrives As Crisis:** The migration that could have been planned over months becomes a forced upgrade after end-of-life, audit finding, outage, or vendor deprecation.

{{< figure src="risk-compounds.svg" alt="Small risks stacking into a leaning tower labeled deferred change" caption="Deferred change does not disappear. It compounds." >}}

## A Real-World Example: The Approval That Became Theater

I have seen release processes where every production deployment required a manual approval meeting. The process began after a serious incident, and at the time it made sense. The organization needed more visibility and control.

Years later, the meeting remained. The systems had changed. The deployment tooling had improved. Automated tests existed. Rollback paths were clearer. But the approval meeting persisted because nobody wanted to be the person who removed a control associated with safety.

The meeting no longer caught meaningful risk. Engineers summarized changes already reviewed in pull requests. Approvers nodded through systems they did not operate. Emergency fixes bypassed the meeting anyway. The process created delay without real control.

The breakthrough came when the team stopped arguing about whether approval was good or bad and started asking what risk the approval was supposed to reduce. Some changes still needed review: database migrations, network changes, permission expansions, irreversible operations. Many routine deployments did not.

The new process did not remove control. It moved control closer to the risk: automated checks for low-risk changes, explicit review for high-risk changes, and post-deployment verification for everything.

Resistance softened when the change was framed as better risk management, not less governance.

## Why Teams Resist Change

Teams resist change for reasons that often make sense locally.

1. **Past Change Hurt:** If previous migrations caused outages, people remember. Skepticism is not irrational when experience taught the team that change is painful.

2. **The Current System Is Understood:** A flawed system with known failure modes can feel safer than an improved system with unknown ones.

3. **Incentives Favor Avoidance:** If teams are punished for failed change but not rewarded for reducing future risk, the safest career move is to leave things alone.

4. **Migration Work Is Invisible:** Leadership sees feature delivery. It may not see the operational debt paid down by modernization work until the avoided incident never happens.

5. **No One Owns The Transition:** Everyone agrees the future state is better, but nobody owns the bridge from current state to future state. Without ownership, change remains an idea.

{{< figure src="fear-map.svg" alt="A map from current state to future state with fear, unclear ownership, and unknown rollback marked as hazards" caption="People rarely resist the destination. They resist the unsafe path to get there." >}}

## Making Change Safer

The answer is not to force change harder. The answer is to make change smaller, clearer, and more reversible.

1. **Define The Risk Being Reduced:** Every change should explain what risk, toil, cost, or constraint it addresses. Change for its own sake creates fatigue.

2. **Start With Reversible Moves:** Prefer changes that can be rolled back, toggled off, or run in parallel. Reversibility lowers fear.

3. **Use Incremental Migration Paths:** Replace big migrations with expand-and-contract patterns, compatibility windows, and side-by-side operation where possible.

4. **Create A Retirement Plan:** New tools and processes should include what they replace. Otherwise the organization adds change without removing complexity.

5. **Measure Friction:** Track lead time, approval wait time, manual handoffs, failed changes, and repeated incidents. Data helps show when the old way is no longer safe.

6. **Protect Time For Modernization:** If improvement work only happens after feature work, it never happens. Reserve explicit capacity for reducing operational debt.

{{< figure src="safe-bridge.svg" alt="A bridge from current state to future state with small checkpoints and rollback points" caption="The safest change is the one with checkpoints, evidence, and a way back." >}}

## Applying The Scientific Method

Change resistance decreases when improvement is treated as an experiment instead of a mandate.

1. **Ask:** What problem are we trying to solve, and what evidence shows it matters?

2. **Hypothesize:** "If we replace the manual deployment meeting with automated policy checks for low-risk changes, lead time will decrease without increasing change failure rate."

3. **Test:** Apply the new approach to one service, one team, or one class of low-risk change.

4. **Observe:** Measure lead time, failed changes, rollback frequency, and team confidence.

5. **Iterate:** Expand, adjust, or stop based on evidence. A failed experiment is still progress if it teaches the team what risk remains.

## Carl Sagan's Baloney Detection Kit

When resistance appears, challenge both sides of the argument.

- **"We have always done it this way."** — Why was the process created? Does that reason still exist?

- **"The new way is better."** — Better by what evidence? Faster? Safer? Cheaper? Easier to audit?

- **"Changing it is too risky."** — Compared to what? What is the risk of leaving it unchanged for another year?

- **"We will migrate later."** — When exactly? Who owns it? What trigger moves it from intention to work?

- **"The pilot worked."** — Did it change the default path, or did it remain an exception?

{{< figure src="change-evidence.svg" alt="A decision board comparing evidence for staying still versus changing safely" caption="The debate should not be old versus new. It should be evidence versus assumption." >}}

## Moving Forward Together

Resistance to change is not always the enemy. Sometimes it is the organization asking for proof, safety, and a better migration path. Listen to that signal. Then do the work to make change trustworthy.

The real anti-pattern is not caution. Caution is healthy. The anti-pattern is allowing caution to harden into permanent inertia while risk grows underneath.

Healthy DevOps culture does not chase every new tool or trend. It also does not cling to yesterday because yesterday is familiar. It creates a disciplined path for evaluating change, reducing risk, and evolving before crisis forces the issue.

What process, tool, or architecture is your team defending because it is safe — and what evidence would prove whether it actually still is?

## References

- [The DevOps Handbook](https://itrevolution.com/devops-handbook/) by Gene Kim, Patrick Debois, John Willis, and Jez Humble
- [Accelerate: The Science of Lean Software and DevOps](https://itrevolution.com/product/accelerate/) by Nicole Forsgren, Jez Humble, and Gene Kim
- [Team Topologies](https://teamtopologies.com/) by Matthew Skelton and Manuel Pais
- [Google SRE Workbook — Non-Abstract Large System Design](https://sre.google/workbook/non-abstract-design/)
- [DORA: Generative organizational culture](https://dora.dev/devops-capabilities/cultural/generative-organizational-culture)
- [Martin Fowler: Strangler Fig Application](https://martinfowler.com/bliki/StranglerFigApplication.html)
