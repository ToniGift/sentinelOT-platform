# GitLab Duo Agent Platform in AlarmOps

The hackathon requires every project to use GitLab Duo Agent Platform (agents, flows or MCP
clients). Stage 1 judging is pass/fail on this. AlarmOps is designed around **flows**. So far only GitLab's built-in Fix CI/CD Pipeline flow
has run (once, on merge request !1); the four custom flows below are designs, not built.

## Honest status

| Part | Status |
|---|---|
| CI/CD pipeline, gate, scanners, deploy, monitor | Built and tested locally (see README) |
| GitLab built-in Fix CI/CD Pipeline flow | Ran once on merge request !1 (demo A), started by a person |
| Duo flow YAML | **To be built in the GitLab UI.** Its detailed syntax was not confirmed when this was written, so it is deliberately not guessed here |
| `.gitlab/duo/agent-config.yml` | Written using only the keys the docs list; needs checking on first run |

Update the status column in `README.md` as each flow starts working. Do not claim a flow that
has not run.

## What the GitLab docs confirm

- Custom flows are created in the UI: in the project, **AI > Flows**, then create a flow and
  enter the YAML in the *Configuration* editor.
- A flow is a single YAML file in the "flow registry v1" format. Top-level fields: `version`
  (always `"v1"`), `environment` (only `ambient` is allowed in custom flows), `components`,
  `prompts`, `routers`, `flow`.
- Custom flows reject the `name`, `description` and `product_group` fields, and the `model`
  field inside prompts.
- Triggers that pass a goal to the flow:
  - a user **mentions** the flow's service account in a comment (goal = the comment text plus
    resource context);
  - the service account is assigned as **reviewer** on a merge request (goal = the MR IID);
  - a **pipeline event** (goal = the webhook payload).
- To run a flow, Duo Agent Platform must be turned on for the project and you need at least
  the Developer role. Each enabled flow gets a service account user (named like
  `ai-<flow>-<group>`).
- Custom flows were listed as available on the Free tier on GitLab.com with GitLab Credits.
  Confirm this for the hackathon-provisioned project.
- `.gitlab/duo/agent-config.yml` configures the flow execution environment. Documented keys:
  `image`, `setup_script`, `network_policy` (`allowed_domains`, `denied_domains`,
  `include_recommended_allowed`, `allow_all_unix_sockets`). It is read **only from the default
  branch**.

Sources:
- https://docs.gitlab.com/user/duo_agent_platform/flows/custom_flows_schema/
- https://docs.gitlab.com/user/duo_agent_platform/flows/execution/agent-config-yaml/
- https://docs.gitlab.com/user/get_started/get_started_agent_platform/
- A worked example flow: https://handbook.gitlab.com/handbook/customer-success/professional-services-engineering/education-services/ilt-labs/gitlabdaphandsonlab4/

## Not confirmed (find out on day one)

- The syntax of `components`, `prompts`, `routers` and `flow` entries.
- Which tools an agent in a flow can use: reading MR diffs and comments, posting comments,
  applying labels, creating issues, and above all **running shell commands** (needed if the
  agent itself should run the replay).
- Whether pipeline artifacts are visible to an agent.
- Whether the flows are available under the hackathon-provisioned tier.

## Day-1 gate: one flow running on a merge request

Goal: get *any* flow to run and comment on an MR before building more.

1. Merge `.gitlab/duo/agent-config.yml` to the default branch.
2. In the project: **AI > Flows**, create a new flow. Start from the worked example above and
   change it; do not write the YAML from memory.
3. Paste the prompt for flow 1 (below) into the prompt section.
4. Enable the flow for the project. Note the service account name it creates.
5. Open the `demo-change-a` merge request. Assign the service account as **reviewer** (or
   mention it in a comment).
6. Confirm the flow runs and posts a comment.
7. Copy the working YAML into this repo as `duo/flows/mr_review.yml` and delete
   `duo/flows/mr_review_flow.PLACEHOLDER.yml`. The rules treat agent config YAML as part of
   the submission, so it must be in the repository.

If this fails, stop and diagnose before building anything else. If it cannot be made to work,
tell the hackathon manager (email on the Devpost page) and ask.

## Flow designs

Each flow below is a design plus a draft prompt. Paste the prompt text into the flow's prompt
section. Prompts are written so the agent quotes numbers only from what it can read and never
invents them.

### 1. MR review flow (priority, the day-1 gate)

- **Lifecycle stage:** Create
- **Trigger:** service account assigned as reviewer on a merge request (goal = MR IID)
- **Reads:** the MR diff of `alarms.yaml` and the `AlarmOps replay gate` comment that CI posts
- **Writes:** one review comment on the MR
- **Success looks like:** a short comment that restates the measured result, names the risk,
  and recommends approve / request changes.

Draft prompt:

```
You are the AlarmOps merge request reviewer. The goal is a merge request ID.
1. Read the merge request diff. Identify which alarm settings changed (tag, setting, old
   value, new value).
2. Find the comment that starts with "AlarmOps replay gate". It contains measured
   fault-detection and false-alarm numbers.
3. Write ONE comment of at most 150 words: what changed; the measured detection rate and
   false-alarm change, quoted exactly from that comment; whether the gate passed; the single
   biggest operational risk; and a recommendation (approve or request changes).
Rules: never invent or estimate numbers. If the replay comment does not exist yet, say so and
do not guess. This is a simulation; do not claim real-plant safety.
```

Fallback if the agent cannot read the CI comment: ask it to read only the diff and describe
the change qualitatively, while CI keeps posting the numbers.

### 2. Issue triage flow

- **Lifecycle stage:** Plan
- **Trigger:** mention of the service account in an issue comment (an issue-creation trigger
  was not confirmed)
- **Writes:** a classification comment and labels, if the platform allows label changes

Draft prompt:

```
You triage alarm-limit change requests. The goal is an issue comment and its context.
Classify the request as one of: tighten-limit, widen-limit, add-tag, remove-tag, other.
Extract the tag name, the proposed values and the stated reason. If the reason is missing,
ask for it. Reply with a short summary and apply the label matching the classification.
Flag any widen-limit request as higher risk. Do not approve or reject changes.
```

### 3. Pipeline summary flow (security and test)

- **Lifecycle stage:** Secure, Verify
- **Trigger:** pipeline event (goal = webhook payload)
- **Writes:** a summary comment on the merge request

Draft prompt:

```
The goal is a GitLab pipeline event payload. Summarise in under 120 words: which stages
passed or failed, which job failed first, and in plain words why (replay gate, secret
detection, tests). If a secret was detected, name the file but never print the secret value.
End with the next step the author should take. Do not invent job names or results.
```

### 4. Monitoring diagnosis flow

- **Lifecycle stage:** Monitor
- **Trigger:** mention of the service account on a monitoring issue (`monitor_alarm_rate` can open one when an API token is configured)
- **Writes:** a diagnosis comment

Draft prompt:

```
The goal is a monitoring issue created by AlarmOps. It contains baseline and recent alarm
rates per tag. Explain in under 120 words which tag drove the increase and give two to three
hypotheses (for example, a recent limit change, sensor chatter, or a process change), clearly
marked as hypotheses. Recommend checking the latest change record and considering a rollback.
Do not state causes as facts.
```

### 5. Compliance narrative (optional)

The `change_record` job already produces the change record deterministically. An agent could
add a plain-language summary, but this is optional. Do not build it before flows 1 to 4 work.

## Autonomy level

AlarmOps is entered at the **Supervised** level: the automation reviews, tests, scans,
documents, deploys to staging and validates on its own; a human approves only the production
deployment (`deploy_production`, a manual job on the default branch).

## Verification checklist before submitting

- [ ] At least one flow ran on a real merge request and its comment is visible
- [ ] The working YAML is committed under `duo/flows/` and the placeholder is deleted
- [ ] `README.md` status column matches reality
- [ ] The demo video shows a flow running
