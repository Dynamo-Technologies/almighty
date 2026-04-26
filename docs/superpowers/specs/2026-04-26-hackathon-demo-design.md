---
title: Hackathon demo — PyRapide-assisted Gemma agents on edge GPUs
date: 2026-04-26
status: design
---

# Hackathon demo design

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

## 1. Headline

> **PyRapide's causal DAG closes the loop on agent reasoning.** Gemma 4 reads
> the scenario's causal graph as its situation report, decides, and commits
> events whose `causal_predecessors` cite the precise prior events the LLM
> reasoned over. The DAG is both *input* (assist) and *output* (audit). The
> agents physically run on edge GPUs (NVIDIA Sparks) reachable from an
> AWS-hosted control plane via Tailscale.

The wow shot: one click in the browser, both Sparks' GPUs spike, events
stream back into the EXCON sidebar with visible parent-child causal links,
the Cumberland River map fills in the resulting effects.

## 2. Three-minute demo outline (one click, voice-tracked)

| t        | On screen                                                                 | Voice track beat                                                                                                                                |
|----------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| 0:00–0:30 | Architecture slide: AWS EC2 ↔ Tailscale ↔ two Sparks. EXCON tab open.    | "Almighty is a multi-tenant war sim. Cloud orchestrates. Inference runs on edge GPUs. PyRapide stitches it together."                            |
| 0:30–0:35 | EXCON: Cumberland River map, single button "Advance turn 1" highlighted. | "Scenario, profiles, override policies pre-loaded by the white cell. One click."                                                                 |
| 0:35      | Click.                                                                   | (silent click)                                                                                                                                  |
| 0:35–1:20 | `nvidia-smi -l 1` panels on both Sparks spike. vLLM logs scroll.          | "Gemma 4 26-B-A4B on Spark 1 is the blue battalion S3. Gemma 4 31-B on Spark 2 is the red S3. Each gets a situation report built from PyRapide." |
| 1:20–2:30 | Events stream into right sidebar (drip-fed). CZML packets render on map. | "Notice each event card cites its causal parents. S3's order links back to the specific S2 detect event that triggered it. That's PyRapide making the agent's reasoning auditable — not narrated, structural."  |
| 2:30–2:50 | Click an `issue_order` event card. Causal chain panel expands.            | "Click any event, get the full provenance — every prior event the agent saw before deciding."                                                    |
| 2:50–3:00 | Both GPU panels back to idle. Map at end-of-turn-1 state.                 | "Cloud orchestration. Edge inference. Auditable causality. Every turn, every decision, end to end."                                              |

If anything stalls past 1:30, the recovery line is: *"vLLM is loading; in
production this is a warmed model"* — and skip ahead to the static fixture
in the AAR. (The spec ships a fallback; see §9.)

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│   Presenter laptop (on Dynamo tailnet)                                       │
│   Browser → https://app.almightyengine.com/excon (single page)           │
└────────┬─────────────────────────────────────────────────────────────────────┘
         │ HTTPS over Tailscale (DNS resolves publicly via Route 53;             
         │  only tailnet members can route to the 100.x.y.z target)              
         ▼                                                                       
┌──────────────────────────────────────────────────────────────────────────────┐
│   AWS Route 53 — public hosted zone app.almightyengine.com                              │
│     A record  app.almightyengine.com  →  EC2 Tailscale IP (100.x.y.z)     │
│   IAM (small policy on the app.almightyengine.com zone, used by Caddy DNS-01 only)      │
└────┬─────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│   AWS EC2 (t3.medium, x86_64) in us-east-1, Tailscale-only ingress           │
│   docker-compose:                                                            │
│     • caddy (real LE cert via DNS-01 against Route 53; reverse-proxies       │
│              /api → control-plane, /ws → websocket, / → web build)           │
│     • control-plane (Node.js, port 4000, internal)                           │
│     • websocket-service (port 4001, internal)                                │
│     • czml-adapter (port 4002, internal)                                     │
│     • tailscaled (host network)                                              │
│   No Redis. No Celery. No public 80/443. Caddy listens only on tailnet IP.   │
└────┬──────────────────────────────────────────────────┬──────────────────────┘
     │ POST /run-turn over Tailscale                    │ pg over TLS
     ▼                                                  ▼
┌────────────────────────────────────┐    ┌────────────────────────────────────┐
│   spark-763d  (100.106.123.5)       │    │   Supabase Postgres                │
│   Ubuntu 24.04, GB10, 119 GiB       │    │   (managed, cloud)                 │
│   docker:                            │    │   • events                         │
│     • vllm-agent  :8001              │    │   • scenarios                      │
│         google/gemma-4-26B-A4B-it    │    │   • turn_snapshots                 │
│         tool-call: gemma4 ✓          │    │   • override_policies              │
│     • crewai-worker (NEW shim)       │    │   • override_decisions             │
│         FastAPI :7000                │    │                                    │
│         POST /run-turn               │    │   psql reachable via tailnet       │
│         binds → almighty/agents/+    │    │   (or via Supabase dashboard for   │
│                  almighty/kernel/    │    │    presenter inspection if asked)  │
└────┬────────────────────────────────┘    └────────────────────────────────────┘
     │ HTTP over Spark-to-Spark cable (private)
     ▼
┌─────────────────────────────────────┐
│   spark-3fe3  (100.112.216.53)      │
│   docker:                           │
│     • vllm-gemma  :8000             │
│         google/gemma-4-31B-it       │
│         tool-call: gemma4 ✓         │
│   (untouched — inference only)      │
└─────────────────────────────────────┘
```

## 4. Components and responsibilities

| Component                               | Where                | New / Existing              | Responsibility                                                                                                |
|-----------------------------------------|----------------------|-----------------------------|---------------------------------------------------------------------------------------------------------------|
| `crewai-worker` FastAPI shim            | spark-763d           | **New** (small)             | `POST /run-turn` → run blue + red crews, return all committed events with `causal_predecessors` populated     |
| `almighty_blue_crew.crew.run_blue_crew` | spark-763d (mounted) | **Modified**                | S2/CO A/B/C/S6 stay deterministic. S3 step flipped to `Crew.kickoff()` with situation report from PyRapide DAG |
| `almighty_red_crew.crew.run_red_crew`   | spark-763d (mounted) | **Modified**                | Same pattern: red S3 LLM-driven against `http://100.112.216.53:8000/v1`. Other red roles deterministic        |
| `OfficerToolBase`                        | spark-763d (mounted) | **Modified**                | Accept `causal_predecessors` argument; pass through to `KernelEvent`. Default empty preserves existing tests   |
| `control-plane`                          | EC2                  | Existing + small fix        | Expose existing `/events` and `/turns/advance`. Advance handler now POSTs to spark worker over Tailscale       |
| `EventLog.tsx`                           | EC2 (web build)      | **Modified**                | Render `causal_predecessors` inline (parent verbs as chips); click → highlight parent in same list             |
| EXCON console                            | EC2 (web build)      | Existing                    | Single visible action: "Advance turn 1" button                                                                 |
| Supabase project                         | Cloud                | **New**                     | Postgres for the demo tenant. Schemas imported from `services/control-plane/src/db/`                            |
| Tailscale on EC2                         | EC2                  | **New (cloud-init)**        | EC2 joins Dynamo tailnet via ephemeral auth key. Outbound to spark IPs. Ingress via tailnet only                |
| Route 53 A record                         | AWS                  | **New**                     | `app.almightyengine.com` → EC2 Tailscale IP. Public DNS, private routing                                     |
| IAM (Route 53 DNS-01)                     | AWS                  | **New**                     | Tiny scoped policy: `route53:ListHostedZones` + `route53:ChangeResourceRecordSets` + `route53:GetChange` on app.almightyengine.com. Used by Caddy only                                                      |
| Caddy (TLS termination + reverse proxy)   | EC2                  | **New (replaces nginx)**    | Caddy w/ `caddy-dns/route53` plugin. Auto Let's Encrypt via DNS-01 (no public 80/443 needed). Reverse-proxies internal services on the tailnet IP only                                  |
| nvidia-smi side terminals                | Both Sparks          | **New (operator-run)**      | Two SSH terminals, `nvidia-smi dmon -s u`, projected next to browser. Pure visual stage element                  |

## 5. Data flow — one click to events on screen

```
[user clicks Advance turn 1]
    │
    ▼
[control-plane POST /tenants/.../scenarios/.../turns/advance]
    │
    ▼
[control-plane fetches turn_snapshot for turn 0 from Supabase]
    │
    ▼
[control-plane POSTs http://spark-763d.tailnet:7000/run-turn
   { tenant_id, scenario_id, turn: 1, snapshot_in: {…} }]
    │
    ▼
[spark worker:
   1. Construct fresh NamespacedDag for the run.
   2. Run blue crew:
      - Deterministic S2.detect → commits event E1 (causal_predecessors=[])
      - Deterministic S2.classify → commits E2 (causal_predecessors=[])
      - LLM-driven S3:
          a. Build situation report from kernel_dag.read(causal_order=True)
             → "Recent events: E1 (RADAR detect, conf 0.85), E2 (classify UAS, conf 0.78)"
          b. Crew.kickoff() against http://127.0.0.1:8001/v1
             Gemma 4 26-B-A4B emits issue_order tool call
          c. Tool commits E3 with causal_predecessors=[E1.id, E2.id]
          d. Repeat for s3.request_support → E4 with same predecessors
      - Deterministic CO A.assume_posture → E5
      - … (rest of script unchanged)
   3. Run red crew (parallel asyncio task):
      - Deterministic R2 events
      - LLM-driven R3 against http://100.112.216.53:8000/v1
      - … (rest deterministic)
   4. Collect all committed events, return as JSON]
    │
    ▼
[control-plane writes events to Supabase events table
   (causal_predecessors as text[] column — already in schema)]
    │
    ▼
[control-plane fans events to websocket clients]
    │
    ▼
[renderer drip-feeds events into EventLog with
   staggered animation; CzmlLoader plays packets via
   Cesium clock]
```

## 6. PyRapide as protagonist — the two edits that earn the headline

### 6a. Situation report from the DAG (the assist)

Add a helper in `agents/runtime/`:

```python
def build_situation_report(dag: NamespacedDag, *, tenant_id, scenario_id) -> str:
    events = dag.read(tenant_id=tenant_id, scenario_id=scenario_id, causal_order=True)
    # Format as terse role-readable text. One line per event.
    return "\n".join(
        f"- [{e.event_id}] {e.action_verb} by {e.source_officer_type} "
        f"(turn {e.turn}): {summarize_payload(e.payload)}"
        for e in events
    )
```

The blue/red S3 step instantiates a `crewai.Crew` with the agent + a single
task whose description embeds this report. `Crew.kickoff()` returns Gemma's
chosen tool call (e.g., `issue_order` with arguments). The tool's `_run`
gets called with the LLM args.

### 6b. Causal predecessors on commit (the audit)

`OfficerToolBase._run` gains an optional `causal_predecessors` keyword:

```python
def _run(self, *, causal_predecessors: list[UUID] | None = None, **kwargs):
    ...
    event = KernelEvent(
        ...,
        causal_predecessors=causal_predecessors or [],
    )
```

The LLM-driven S3 step wraps the tool call with the situation-report event
ids:

```python
predecessors = [e.event_id for e in dag.read(tenant_id=..., scenario_id=...)]
result = s3_role.tools["issue_order"]._run(
    **gemma_chosen_args,
    causal_predecessors=predecessors,
)
```

Auto-link, not Gemma-driven citation. The audit story is the same and we
avoid an entire class of "Gemma cited a wrong UUID" failure modes.

### 6c. Visual surfacing — the EventLog change

`web/renderer/src/components/EventLog.tsx`: under each event row, when
`causal_predecessors.length > 0`, render a "← caused by" chip group with
each parent's verb (resolved by looking up event_id in the same `events`
prop). Click a chip → scroll-into-view + 1-second highlight on the parent
row. Pure CSS / scroll-behavior; no graph library needed.

## 7. Cuts vs. existing Nashville WS-601 scenario

What we **remove** for the 3-minute demo (NOT remove from code, just from
the live demo path):

- 5 of 6 turns. Demo runs only turn 1.
- Manual override policy authoring. All policies seeded as auto-approve in
  the DB before the demo.
- White-cell adjudicator stage. Adjudicator code stays untouched but is
  not in the critical path — review queue stays empty.
- Operator-driven EXCON verbs. No live operator decisions during the 3 min.
- AAR export to S3 + summary.pdf. AAR route still works post-demo for any
  audience question; not on the critical path.
- Effect-family coverage. Today's deterministic crews emit 3 of 9 spatial
  families; the demo does not pretend otherwise. The audit story is about
  *causality*, not coverage.

What we **keep**:

- Full kernel + control-plane + websocket + czml-adapter pipeline
- Real Cesium map + real CZML packet rendering
- Real DB-backed event table
- Real Tailscale-bridged hybrid topology
- Real Gemma 4 inference on real edge GPUs

## 8. Build order

Coarse phases for the implementation plan to expand. Detail goes in the plan,
not the spec.

1. **AWS + Tailscale + Supabase + Route 53 plumbing.** EC2 up, joined
   to tailnet, Supabase project created, schemas imported, Caddy
   issuing a real Let's Encrypt cert for `app.almightyengine.com`
   via Route 53 DNS-01, A record live, control-plane reachable from
   the presenter laptop browser. Validation: `curl -v
   https://app.almightyengine.com/healthz` from the laptop returns
   200 with a green padlock; `tailscale ping spark-763d` from EC2;
   `psql` from EC2 to Supabase.
2. **Spark worker shim.** FastAPI in `agents/runtime/`, dockerized into
   the existing `crewai:stig-hardened-boto3` container via bind-mount and
   CMD override. Validation: `curl http://spark-763d:7000/healthz` from EC2.
3. **PyRapide-assist + causal-predecessors edits.** `OfficerToolBase` arg,
   blue S3 LLM flip, red S3 LLM flip, situation-report helper. Validation:
   unit test that asserts an LLM-driven event has non-empty
   `causal_predecessors`.
4. **EventLog UI change.** Render `causal_predecessors` inline. Validation:
   visual test against fixture data (`fixtureEvents` in `aar.ts` already
   exists; backfill `causal_predecessors` in fixtures for QA).
5. **Demo-mode wiring.** Single-button EXCON view, scenario + override
   seeds in Supabase, web build deployed to nginx. Validation: end-to-end
   click through from presenter laptop → events on screen.
6. **Dress rehearsal.** Three full run-throughs. Lock recovery line. Lock
   the architecture slide.

If we run out of time, drop in this order: (6) becomes 1 rehearsal, (4)
becomes a CSS-only diff, (3)'s red-side LLM is the first cut (fall back to
deterministic red, narrate "the same pattern extends to red on Spark 2").

## 9. Risk register

| Risk                                                                           | Likelihood | Mitigation                                                                                                                              |
|--------------------------------------------------------------------------------|-----------|------------------------------------------------------------------------------------------------------------------------------------------|
| Gemma emits malformed tool call → CrewAI raises                                | Medium    | `--enable-auto-tool-choice --tool-call-parser gemma4` is on. Wrap S3 in try/except → fall back to deterministic. Log the malformed reply  |
| LLM call exceeds 30s, demo feels slow                                          | Medium    | Pre-warm both vLLMs by issuing a dummy completion 30 min before showtime. Run blue + red crews concurrently (asyncio)                     |
| Tailscale flap mid-demo                                                         | Low       | Both EC2 and Sparks already on tailnet. Pre-flight: `tailscale ping` from EC2 to both Sparks 5 min before                                  |
| Supabase rate limit during seed                                                 | Very low  | Free tier handles this trivially                                                                                                          |
| spark-3fe3 OOM (it's at 7.7 GiB free steady)                                    | Low       | We add zero load to spark-3fe3 — only inference requests, which fit in existing KV cache budget                                            |
| Eventlog UI animation slower than CZML clock → events appear after map effects | Medium    | Tune renderer drip rate to match Cesium clock pace. Test in rehearsal                                                                      |
| Gemma references an event_id that doesn't exist in `caused_by`                 | N/A       | We use auto-link (§6b), not Gemma-cited predecessors. Failure mode eliminated by design                                                   |
| First-touch vLLM latency on cold model                                         | Medium    | Pre-warm. If still cold, the recovery line in §2 buys 30s of voice track to skip ahead                                                    |
| Demo machine drops off Wi-Fi                                                    | Low       | Bring an Ethernet cable. Have a backup hotspot                                                                                            |
| Caddy DNS-01 fails (IAM creds, zone id wrong, LE rate limit)                   | Medium    | Test the issuer once during build phase 1, well before showtime. LE staging environment for first attempt to avoid the 5-cert/week prod limit. Recovery: fall back to a self-signed cert; warn audience to click through |
| Tailscale ACL rejects EC2 → Spark traffic                                      | Low       | Test `tailscale ping spark-763d` and `curl http://100.106.123.5:8001/v1/models` from EC2 immediately after cloud-init                       |

## 10. Voice track — the lines that earn the talk

Memorize these four. The rest is improvisation around them:

1. **Setup line:** "Almighty is a multi-tenant war sim. The cloud orchestrates. Inference runs on edge GPUs. PyRapide stitches it together."
2. **Click line:** "One click. Six officer roles split across two GPUs. Gemma 4 reasons over the situation report PyRapide hands it."
3. **Causality line:** "Each event card cites its parents. Click any one — the full causal chain expands. That's PyRapide making the agent's reasoning auditable, not narrated, structural."
4. **Closer:** "Cloud orchestration. Edge inference. Auditable causality. End to end."

## 11. Operator prep — Tailscale + Route 53 + IAM

These are the manual steps the operator (admin access required) does
*before* the implementation work begins. They take ~10 minutes total.

### 11a. Tailscale auth key for EC2

In the Tailscale admin console (login.tailscale.com → Settings → Keys):

- Click **Generate auth key**
- **Reusable**: yes (so re-running cloud-init during testing doesn't burn a key per attempt)
- **Ephemeral**: yes (the EC2 device auto-deletes from the tailnet when the instance stops — clean teardown)
- **Pre-approved**: yes (skips manual approval in the admin UI)
- **Tags**: `tag:demo-server` if your ACLs use tags; otherwise leave blank
- **Expiry**: 24 hours
- Copy the key (`tskey-auth-...`) — paste it into the EC2 cloud-init userdata in step 11d

If you use tags: confirm in `Access Controls` that `tag:demo-server` is
allowed to reach `100.106.123.5:8001` (spark-763d vLLM) and
`100.112.216.53:8000` (spark-3fe3 vLLM). If you don't use tags, your
default ACL likely already permits this. Quick test from EC2 once it's
up: `curl http://100.106.123.5:8001/v1/models`.

### 11b. Route 53 hosted zone check

Confirm `app.almightyengine.com` is a public hosted zone in the AWS account
(`aws route53 list-hosted-zones | grep app.almightyengine.com`). The A record
will be created automatically by the Caddy DNS-01 issuer or via
Terraform/aws-cli in step 1 of the build order. No manual A record
needs to be pre-created — but the zone must exist.

### 11c. IAM for Caddy DNS-01

Create a small IAM user (or instance role attached to EC2) with this
policy. Scope to the app.almightyengine.com hosted zone ID, not `*`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "route53:ListHostedZones",
        "route53:GetChange"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "route53:ChangeResourceRecordSets",
      "Resource": "arn:aws:route53:::hostedzone/<DYNAMO_WORKS_ZONE_ID>"
    }
  ]
}
```

Capture the access key id + secret. If you used an instance role
instead, no creds to capture — Caddy picks them up from EC2 metadata.

### 11d. EC2 launch checklist

When we provision the EC2 instance in step 1 of the build order, the
cloud-init userdata will:

```bash
#!/bin/bash
set -euxo pipefail

# 1. Tailscale install + join
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up \
  --auth-key=<PASTE_TSKEY_FROM_STEP_11a> \
  --hostname=almighty-demo \
  --ssh \
  --advertise-tags=tag:demo-server   # omit this line if you skipped tags

# 2. Get the Tailscale IP and write it into a file the rest of the
#    bootstrap reads
tailscale ip -4 > /etc/almighty/tailscale-ip

# 3. Docker + docker-compose-plugin
apt-get update
apt-get install -y docker.io docker-compose-plugin awscli

# 4. Clone almighty and bring up the stack
git clone https://github.com/Dynamo-Technologies/almighty /opt/almighty
cd /opt/almighty
# (compose file written in step 1 of build order; secrets come from
#  AWS SSM Parameter Store or .env file we drop in)
docker compose up -d

# 5. Create / update the Route 53 A record pointing at our tailscale IP
TS_IP=$(cat /etc/almighty/tailscale-ip)
ZONE_ID=<DYNAMO_WORKS_ZONE_ID>
aws route53 change-resource-record-sets --hosted-zone-id $ZONE_ID \
  --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"app.almightyengine.com\",\"Type\":\"A\",\"TTL\":60,\"ResourceRecords\":[{\"Value\":\"$TS_IP\"}]}}]}"
```

After cloud-init finishes (~3-5 min), Caddy boots, requests its
Let's Encrypt cert via DNS-01 (the IAM creds let it write the
`_acme-challenge.almightyengine.com` TXT record), and serves
the React app on `https://app.almightyengine.com`. Reachable only
from devices on the tailnet because the A record points at a 100.x.y.z
address with no public route.

### 11e. Pre-flight test from presenter laptop

Once cloud-init reports done:

```bash
# DNS resolves publicly
dig +short app.almightyengine.com
# Expect: a 100.x.y.z address

# Without tailscale up, this hangs — that's the point
nc -z -w 2 app.almightyengine.com 443; echo $?

# With tailscale up, this returns 200
curl -v https://app.almightyengine.com/healthz
# Expect: green cert chain, 200 OK
```

If the laptop hangs *with* tailnet membership, the EC2 likely lost
its tailscale connection — `tailscale status` from EC2 will show.

## 12. Out of scope (explicit)

- Multi-tenant isolation (one demo tenant)
- Authentication beyond a hardcoded JWT (a single dev token suffices for
  the demo's lifecycle)
- AAR export to S3 (route exists, not on demo path)
- White-cell override policy authoring UI (seeded in DB)
- Operator-driven EXCON verbs (`destroy`, `disable`, `jam` as live actions)
- Server-sent-events streaming of LLM tokens (would extend audit story,
  but a 2-hour feature with integration risk; deferred)
- Persistence of the worker's in-memory `NamespacedDag` between turns
  (turn-1-only demo doesn't need persistence; the snapshot pattern that
  WS-302 designed for is overkill for a single turn)
- Performance tuning (`--enforce-eager` stays on; ~25% throughput hit is
  acceptable for the load)
