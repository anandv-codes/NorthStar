# EC2 Deployment Guide — NorthStar Backend

Context: analysis in [docs/latency_improvements.md](latency_improvements.md) and
the Lambda-vs-EC2 discussion concluded EC2 (or an equivalent long-running
container host) is the right fit today, primarily because:
- [backend/app/infrastructure/vector/vectorstore.py](../backend/app/infrastructure/vector/vectorstore.py)
  uses a **local-disk Chroma `PersistentClient`** — incompatible with
  Lambda's ephemeral, non-shared `/tmp` across invocations/containers.
- The retrieval pipeline depends on `sentence-transformers` (CrossEncoder
  reranker + optional local embeddings), which pulls in `torch` — large,
  slow to cold-start, and best amortized by a long-running warm process
  (matches the singleton-caching patterns already in the codebase:
  `get_hybrid_retriever()`, `get_embeddings()`, `_get_chat_llm()`, etc.).
- `backend/deploy_lambda.ps1` and `requirements_lambda.txt` are confirmed
  stale/broken (wrong handler import path, missing `chromadb` /
  `sentence-transformers` / `rank_bm25`) — not blockers for this decision,
  but ruled out "just fix the zip" as a quick alternative.

This doc covers deploying the FastAPI backend (`backend/app/main.py`) to a
single EC2 instance now, with an explicit path toward SQS-driven background
processing and EventBridge later, without over-building for scale you don't
have yet (YAGNI — start simple, call out exactly where it'll need to change).

---

## 1. Current state (as of this writing)

- Web process: FastAPI app, run via `uvicorn` (see `.vscode`/task
  `Start Backend` → `python -m uvicorn backend.app.main:app`).
- CORS is wide open (`allow_origins=["*"]` in
  [backend/app/main.py](../backend/app/main.py#L24)) — fine for local dev,
  **must be restricted to the real frontend origin(s) before internet-facing
  deployment**.
- Note ingestion: `POST /notes` always writes to Supabase, then either:
  - sends an SQS job (`send_note_job`) — the production-shaped path, or
  - processes inline and synchronously if `PROCESS_NOTES_INLINE=true` — a
    local debugging convenience only ([backend/app/api/routes/notes.py](../backend/app/api/routes/notes.py#L45)).
- SQS consumption today is a manual `POST /notes/poll/process-jobs`
  endpoint that polls once and processes whatever it finds
  ([backend/app/api/routes/notes.py](../backend/app/api/routes/notes.py#L113)) —
  this is a stand-in, not a real consumer loop. Treat replacing it as part
  of this deployment, not optional polish (see §6).
- Vector store: Chroma, local disk, path from `CHROMA_PATH`
  (default `./chroma_data`) — must live on durable, backed-up storage, and
  there can only be **one** process/instance that owns it unless/until it's
  moved to something shared (see §3 and §7).

---

## 2. Instance sizing

The CPU-bound cost center is `sentence-transformers` (cross-encoder rerank
on every retrieval + optional local embeddings) plus a per-request
rebuilt in-memory BM25 index (`rank_bm25`, rebuilt from Supabase on every
call — see [backend/app/domain/query_retrieval/strategies/sparse.py](../backend/app/domain/query_retrieval/strategies/sparse.py)).
Everything else (Gemini calls, Supabase calls) is I/O-bound, not CPU-bound.

**Recommendation to start:** `t3.medium` (2 vCPU / 4 GB) or, if available in
your region and you want ~20% better price/performance for this CPU-bound
inference workload, the Graviton (ARM) equivalent `t4g.medium` — PyTorch and
`sentence-transformers` both ship ARM wheels, so this isn't exotic, just
confirm during setup that `pip install` pulls `manylinux2014_aarch64` wheels
and doesn't fall back to a source build.

- Start on a burstable (`t3`/`t4g`) instance and watch CPU-credit balance in
  CloudWatch — note processing is bursty (one request at a time locally),
  not sustained load, which is exactly what burstable instances are
  priced for.
- If CPU credits run out under real traffic, that's your signal to move to
  a fixed-performance type (`m7g`/`c7g` family) — don't pre-provision for
  that before you've measured it.
- Memory floor: `sentence-transformers` + model weights + FastAPI + Chroma
  in one process comfortably needs 4 GB; don't go below that.

---

## 3. Storage

- Root volume: `gp3` EBS (cheaper and faster than the old `gp2` default at
  the same size — always pick `gp3` explicitly in the console/CLI/Terraform).
- Put `CHROMA_PATH` on its own **separate EBS volume**, not the root volume:
  - Lets you snapshot/back up the vector index independently of the OS disk.
  - Lets you resize it without touching the root volume.
  - Makes a future "move this to a new instance" migration a volume
    detach/attach instead of a data copy.
- Take scheduled EBS snapshots (AWS Backup or a simple cron + `aws ec2
  create-snapshot`) of the Chroma volume — this is your only copy of the
  vector index; losing it means re-embedding every note.
- Logs: the pipeline trace log
  ([backend/app/infrastructure/llm/prompt_logger.py](../backend/app/infrastructure/llm/prompt_logger.py))
  writes to `backend/logs/` by default and grows unbounded with no
  rotation today. Either set `PROMPT_LOG_DIR` to a volume with lifecycle
  rules, add log rotation (`logrotate`), or ship it to CloudWatch Logs and
  stop relying on local disk retention entirely (see §8).

---

## 4. Networking & security

- Don't expose `uvicorn` directly to the internet. Put a reverse proxy
  (Nginx, or an ALB — see below) in front for TLS termination, and bind
  `uvicorn` to `127.0.0.1` or a private security-group-restricted interface.
- **Single instance now:** Nginx on the same box is simplest and cheapest
  (one less moving part, no extra monthly cost). Terminate TLS there
  (Let's Encrypt via `certbot`).
- **If/when you add a second instance** (see §7 scaling path): switch to an
  Application Load Balancer — it gives you health checks, zero-downtime
  deploys (register/deregister targets), and is the natural place to attach
  WAF later. Don't pay for an ALB before you need the second target.
- Security group: inbound 443 (and 80 for redirect) from `0.0.0.0/0`, SSH
  (22) restricted to your IP/VPN only — never `0.0.0.0/0` on 22.
- Restrict CORS (`main.py`) to your actual frontend origin(s) once deployed
  — the current `allow_origins=["*"]` is a dev-only setting.
- IAM: attach an **instance role** (not long-lived static AWS access keys
  baked into `.env`) granting only `sqs:SendMessage` /
  `sqs:ReceiveMessage` / `sqs:DeleteMessage` on the specific queue ARN, plus
  CloudWatch Logs write access. `boto3` picks up instance-role credentials
  automatically — no code change needed, just don't set
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars on the instance.

---

## 5. Secrets & configuration

- Don't ship a plaintext `.env` with real secrets as part of your deploy
  artifact (git pull of a private repo is *ok* if the repo itself is
  private and the `.env` is excluded — but prefer the option below as you
  mature).
- Preferred: AWS Systems Manager **Parameter Store** (free for standard
  parameters) holding `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`,
  `JWT_SECRET`, etc. as `SecureString`s, fetched into environment variables
  by the systemd unit's `ExecStartPre` or a small startup script. Secrets
  Manager is the fancier/paid option (automatic rotation) — not needed yet.
- Reference [backend/.env.example](../backend/.env.example) (already
  created as part of the latency work) for the full list of vars to
  provision, plus add: `SQS_QUEUE_URL`, `AWS_ENDPOINT_URL` (leave unset for
  real AWS), `CHROMA_PATH` (point at the dedicated EBS mount), `PROMPT_LOG_DIR`.

---

## 6. Process management: web process + background consumer

Run two long-lived systemd services on the instance, not one — they have
different scaling/restart/failure characteristics and you don't want a
burst of note-processing CPU usage to slow down chat/API responsiveness,
or an API redeploy to interrupt in-flight note processing.

**`northstar-api.service`** — the FastAPI web process:
```ini
[Unit]
Description=NorthStar FastAPI backend
After=network.target

[Service]
WorkingDirectory=/opt/northstar/backend
EnvironmentFile=/opt/northstar/backend/.env
ExecStart=/opt/northstar/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=5
User=northstar

[Install]
WantedBy=multi-user.target
```
`--workers 2` is a starting point for a 2 vCPU box (rule of thumb: workers
≈ vCPUs for a mixed I/O+CPU workload); watch CPU and tune. More workers
means more copies of the `sentence-transformers` model loaded in memory —
budget RAM accordingly (don't just crank workers up without checking memory
headroom).

**`northstar-note-worker.service`** — replaces the manual
`/poll/process-jobs` endpoint with a real consumer loop. This is the one
piece of actual code you need to add for this deployment:

```python
# backend/app/workers/sqs_consumer.py (new file)
"""Long-running SQS consumer loop — the EC2-native replacement for the
manual /notes/poll/process-jobs debug endpoint."""
import logging
import time

from .note_processor import process_sqs_message
from ..infrastructure.queue.sqs_poller import poll_sqs_messages, delete_sqs_message

logger = logging.getLogger(__name__)


def run_forever(max_messages: int = 5, wait_time_seconds: int = 20) -> None:
    while True:
        messages = poll_sqs_messages(max_messages=max_messages, wait_time_seconds=wait_time_seconds)
        for message in messages:
            try:
                process_sqs_message(message["body"])
                delete_sqs_message(message["receipt_handle"])
            except Exception:
                logger.exception("note job failed, leaving message for SQS retry/DLQ")


if __name__ == "__main__":
    run_forever()
```
Use `wait_time_seconds=20` (SQS long polling max) so the loop isn't busy-
polling — this is already supported by `poll_sqs_messages`'s signature, just
wasn't being used that way from the one-shot HTTP endpoint. Keep the
`poll/process-jobs` HTTP endpoint around only if you still want a manual
"kick the queue now" debug tool; it's no longer the primary consumption
path once this service exists.

```ini
[Unit]
Description=NorthStar note-processing SQS consumer
After=network.target

[Service]
WorkingDirectory=/opt/northstar/backend
EnvironmentFile=/opt/northstar/backend/.env
ExecStart=/opt/northstar/.venv/bin/python -m app.workers.sqs_consumer
Restart=always
RestartSec=5
User=northstar

[Install]
WantedBy=multi-user.target
```

**Configure a Dead Letter Queue (DLQ)** on the SQS queue now (small,
free-tier-friendly, and prevents a single poison-pill note from looping
forever): maxReceiveCount 3-5, DLQ visible in the console for manual
inspection/replay.

---

## 7. Scaling path & the Chroma trade-off (read before adding a 2nd instance)

Single instance is the right starting point — don't build an Auto Scaling
Group for a workload you haven't measured yet. But be aware of this
constraint **before** you reach for a second instance:

> Local-disk Chroma means at most **one** process/instance can own the
> vector store. This is the same fundamental issue that ruled out Lambda.

Two ways forward when you actually need to scale (don't do either
preemptively):
1. **Split roles, don't duplicate them**: run the API (stateless, safe to
   scale horizontally behind an ALB) on N instances, but keep exactly one
   dedicated instance running the note-worker + owning the Chroma volume.
   The API instances call retrieval functions that talk to that one
   worker's Chroma... except today retrieval happens in-process, not over
   the network, so this requires turning Chroma access into a small
   internal service (or moving it off local disk — option 2).
2. **Move to a shared/managed vector store** (bigger change, but the
   cleaner long-term fix): Supabase/Postgres + `pgvector` is the natural
   choice since you're already on Supabase — every instance reads/writes
   the same database, no shared-filesystem problem, no extra service to
   run. This removes the Chroma single-owner constraint entirely and is
   also what would eventually unblock a Lambda migration if you revisit
   that later.

Recommendation: stay on single-instance + local Chroma until you have
concrete evidence (CPU/memory/latency metrics) that one box can't keep up,
then prefer option 2 over option 1 — it's less operational complexity
long-term even though it's a bigger one-time migration.

---

## 8. Observability

- Install the CloudWatch agent and ship:
  - `backend/logs/gemini_prompt_response.txt` (pipeline/stage-timing trace
    log) → a CloudWatch Logs group. This turns the `elapsed_ms` lines added
    for latency work into something you can actually alarm/dashboard on
    instead of `Get-Content -Tail`.
  - systemd journal output for both services (`journalctl -u
    northstar-api`, `journalctl -u northstar-note-worker`).
- Add a lightweight `/health` route (not present today) for the ALB/Nginx
  health check and for your own uptime monitoring — trivial to add, do it
  before go-live rather than after an incident.
- CloudWatch alarms worth setting immediately: CPU credit balance (if on a
  `t3`/`t4g`), disk space on the Chroma EBS volume, SQS
  `ApproximateNumberOfMessagesVisible` (queue backing up = worker can't
  keep pace or is down), SQS DLQ depth > 0 (something is permanently
  failing).

---

## 9. Cost optimizations

- Burstable (`t3`/`t4g`) instance + `gp3` EBS is already the cheap default;
  the main lever beyond that is **right-sizing after measuring**, not
  guessing upfront.
- A **Compute Savings Plan or Reserved Instance** once you're confident
  this runs 24/7 long-term cuts the EC2 bill ~30-40% vs on-demand for the
  same commitment most teams are comfortable with (1-year, no upfront).
  Don't commit until you've settled on an instance size.
- The SQS consumer is a good Spot-instance candidate **if/when** it's split
  onto its own instance (per §7 option 1): it's a queue drain, naturally
  tolerant of interruption (message just becomes visible again after
  `VisibilityTimeout`), unlike the API tier which shouldn't be on Spot.
- CloudWatch Logs: set a retention period (e.g. 30-90 days) on the log
  groups — default is "never expire," which quietly accumulates cost.
- Stop (don't terminate) dev/staging instances outside working hours if you
  stand up a separate non-prod environment — EBS volumes persist while
  stopped, compute billing pauses.
- Data transfer: keep the EC2 instance, Supabase project, and users in/near
  the same region to minimize cross-region transfer costs and latency
  (compounds with the latency work already done elsewhere).

---

## 10. Looking ahead: SQS (solidify) and EventBridge (later)

**SQS** — already wired up ([backend/app/infrastructure/queue/](../backend/app/infrastructure/queue/)),
just needs the real consumer loop from §6 instead of the manual polling
endpoint, plus a DLQ. That's the only SQS work this deployment requires.

**EventBridge** — not needed yet; don't add it just because it's available.
Reach for it specifically when either of these becomes real:
- **Scheduled jobs**: e.g. periodic chat-thread summary refresh, stale
  "processing" note sweep/retry, nightly corpus re-embedding checks.
  EventBridge Scheduler (cron-like rules invoking a Lambda or hitting an
  internal endpoint) is simpler than a one-off `cron` entry buried on the
  EC2 instance, and survives instance replacement.
- **Multiple consumers for the same event**: today "note created" has
  exactly one consumer (the enrichment pipeline). If a second concern
  shows up later (e.g. analytics, notifications, a search-index sync) that
  also needs to react to note creation, that's the point to introduce an
  EventBridge **event bus** with `note.created`/`note.completed` events and
  let SQS become one of several subscribers, rather than fanning out
  manually from inside `note_processor.py`. Don't pre-build this fan-out
  for a second consumer that doesn't exist yet.

---

## 11. Decisions & trade-offs summary

| Decision | Choice | Why | Revisit when |
|---|---|---|---|
| Compute | EC2 (not Lambda) | Local-disk Chroma + heavy ML deps need a persistent, long-running process | Vector store moves to pgvector/managed store |
| Instance family | Burstable `t3`/`t4g.medium` | Workload is bursty, not sustained | CPU credits regularly exhausted under real traffic |
| Reverse proxy | Nginx (not ALB) | Single instance, avoid paying for ALB with one target | A second instance is actually needed |
| Vector store | Local Chroma on dedicated EBS | Matches current code, zero migration cost now | Need >1 instance, or durability concerns outgrow snapshots |
| Secrets | SSM Parameter Store | Free, simple, no plaintext `.env` secrets in the deploy artifact | Need automatic rotation (→ Secrets Manager) |
| Background jobs | SQS consumer systemd service | Replaces the placeholder HTTP poll endpoint with a real always-on loop | — |
| Fan-out / scheduling | Not yet (plain SQS only) | No second consumer or cron need exists today | A second consumer or recurring scheduled job is actually needed (→ EventBridge) |

---

## 12. Open items / explicit TODOs before go-live

- [ ] Restrict `CORSMiddleware` origins in `main.py` (currently `"*"`).
- [ ] Add a `/health` endpoint.
- [ ] Add the SQS Dead Letter Queue + `maxReceiveCount`.
- [ ] Write `backend/app/workers/sqs_consumer.py` (sketch provided in §6)
      and its systemd unit; retire reliance on the manual poll endpoint.
- [ ] Move AWS credentials off static keys onto an EC2 instance role.
- [ ] Set CloudWatch Logs retention policy.
- [ ] Confirm `pip install` on the instance resolves ARM wheels correctly
      if you choose `t4g` (Graviton) — verify no source builds are
      triggered for `torch`/`sentence-transformers`.



```mermaid

flowchart TB
    subgraph Client["Client"]
        FE["Frontend SPA (Vite/React)"]
    end

    subgraph AWS["AWS"]
        subgraph Edge["Edge / Entry"]
            ALB["ALB (future, 2+ instances)<br/>or Nginx (now, single instance)"]
        end

        subgraph APITier["API Tier - EC2 Auto Scaling Group"]
            direction TB
            API1["EC2: FastAPI (uvicorn)<br/>systemd: northstar-api"]
            API2["EC2: FastAPI (uvicorn)<br/>scale-out, future"]
        end

        subgraph Queueing["Async Processing"]
            SQSQ["SQS: note-jobs queue"]
            DLQ["SQS: DLQ<br/>maxReceiveCount 3-5"]
        end

        subgraph WorkerTier["Worker Tier - EC2 single owner"]
            Worker["EC2: note-processor<br/>systemd: northstar-note-worker<br/>long-poll SQS consumer"]
            Chroma["Chroma vector store<br/>local EBS volume"]
        end

        subgraph Future["Future - not built yet"]
            EB["EventBridge<br/>scheduled jobs / multi-consumer fan-out"]
        end

        subgraph Obs["Observability"]
            CW["CloudWatch<br/>Logs + Metrics + Alarms"]
        end

        SSM["SSM Parameter Store<br/>secrets, SecureString"]
    end

    subgraph External["External Services"]
        Supabase["Supabase<br/>Postgres: notes, memory, auth"]
        Gemini["Gemini API<br/>embeddings, rewrite, chat, extraction"]
    end

    FE -->|"HTTPS"| ALB
    ALB --> API1
    ALB -.->|"future target"| API2

    API1 -->|"POST /notes: write + enqueue"| Supabase
    API1 -->|"send_note_job"| SQSQ
    API1 -->|"chat / retrieval calls"| Gemini
    API1 -->|"read/write"| Supabase

    SQSQ -->|"long-poll receive"| Worker
    SQSQ -.->|"maxReceiveCount exceeded"| DLQ

    Worker -->|"extraction, rewrite"| Gemini
    Worker -->|"insert tasks/facts/etc"| Supabase
    Worker <-->|"embed/query/upsert"| Chroma

    API1 -.->|"query_related_notes - single-owner constraint"| Chroma

    API1 -.->|"instance role fetches"| SSM
    Worker -.->|"instance role fetches"| SSM

    API1 --> CW
    Worker --> CW
    SQSQ -.->|"queue depth metric"| CW

    EB -.->|"later: scheduled summary refresh, multi-consumer fan-out"| SQSQ