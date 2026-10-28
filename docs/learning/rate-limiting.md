I read through the backend, the deploy doc, and the frontend client. Here's the full picture, grounded in NorthStar.
1. What "rate limiting" actually means
Rate limiting = deciding, before doing expensive work, whether this caller is allowed to do it right now.
The word gets used for five different mechanisms. They solve different problems and you'll probably want several:
Mechanism	Question it answers	Example in NorthStar
Request rate limit	"How many requests per minute?"	POST /chat/message max 12/min per user
Concurrency limit	"How many requests in flight at once?"	Max 2 chats per user; max 8 LLM calls per worker process
Quota / budget	"How much total this day/month?"	300k Gemini tokens/day/user; 3 summary generations/hour
Queue depth / backpressure	"How much work is already waiting?"	Max 5 notes processing per user before 429
Load shedding	"Is the system too sick to accept anything?"	Global budget exhausted → 503, not 429
Your app needs all five because the cost driver isn't requests — it's Gemini tokens and wall-clock time. One chat message can trigger intent classification, retrieval rewriting, answer generation, and grounding: several LLM calls taking 5–20s each. One POST /notes triggers extraction + embeddings in the worker. One accept-batch (up to 100 candidates, frontend/src/shared/api/httpClient.ts:1112) can issue one answer-generation LLM call per candidate.
A naive "100 requests/min per user" limit would happily let a single user spend your whole Gemini budget in one bulk-accept.
2. Why you want it here, specifically
Concrete reasons, ranked by impact for NorthStar:
1. Cost. Gemini is billed per token, per project. POST /chat/message, POST /notes, POST /summaries/*/generate, PATCH /notes/{id}/recall, POST /retrieval/query, POST /recall/candidates/{id}/answer, and accept-batch all reach Gemini. One user + one loop = your monthly budget.
2. Availability for everyone else. Gemini quotas are per project, not per user. When one user exhausts RPM/TPM, every user gets 429 ResourceExhausted.
3. Capacity, not just cost. You run uvicorn --workers 2 (docs/ec2_deployment.md:707). Each worker has a bounded threadpool, and routes like create_note are sync def (threadpool), while chat.py:21 uses asyncio.to_thread. A handful of 20-second LLM calls can saturate both workers with ~2 users, and then even GET /health is slow. Nginx returns 502s and CloudWatch shows nothing useful.
4. Auth abuse. POST /auth/login and /auth/register (backend/app/api/routes/auth.py:59,74) have no throttling, no lockout. That's credential stuffing, plus free-account creation to get around your per-user limits.
5. Noisy neighbours & polling. The frontend polls GET /notes/{id} while a note is processing. That's legitimate, so it needs a generous limit — but it should still be capped.
6. Bug amplification. A retry loop in the UI (or a double-click) creates two notes = two extraction jobs = two bills. Rate limiting is a backstop for bugs, not a substitute for idempotency.
3. The algorithms (and when each is right)
Algorithm	How it works	Pros	Cons	Use for
Fixed window	Counter per clock minute, reset at boundary	Trivial, cheap	2× burst at the boundary (100 at 0:59, 100 at 1:00)	Login attempts, cheap endpoints
Sliding window log	Store every timestamp, drop old ones	Exact	Memory grows with traffic	Very low-volume, high-value (login)
Sliding window counter	Weighted blend of current + previous window	Near-exact, O(1) memory	Slight approximation	General API limits
Token bucket ⭐	Bucket of capacity tokens, refills at rate; each request spends cost	Allows bursts, smooth long-run rate, supports cost weighting	Two params to tune	Almost everything here
Leaky bucket	Queue drains at constant rate	Perfectly smooths output	Adds latency / drops	Protecting Gemini from bursts
Concurrency semaphore	Count in-flight requests	Directly protects threadpool/upstream	Not a rate limit	LLM endpoints
GCRA	Token bucket expressed as "theoretical arrival time"	One number of state, exact	Harder to explain	Redis-backed implementations
Recommendation: token bucket, weighted by endpoint cost. It naturally expresses "bursts are fine, sustained load is not" — which matches human usage (someone writes 3 notes in a row, then nothing for an hour). A pure N per minute rule punishes exactly the behaviour you want to encourage.
Nginx uses leaky-bucket semantics for limit_req, which is why it's good at the edge and less good as your primary fairness mechanism.
4. Where to put the limiter (three layers, different jobs)
browser → Nginx (per-IP, cheap, no app)  →  FastAPI dependency (per-user, shared store)  →  Gemini client (retry/backoff + global budget)
Layer	Sees	Strengths	Weaknesses
Nginx	IP only	Stops floods before Python; free; already deployed	IP ≠ user (NAT, mobile); no cost awareness; coarse
FastAPI (per-user)	JWT sub	Fair, survives IP changes, can weight by cost	Needs shared storage across 2 workers; adds a hop
Gemini client	Token usage	Ground truth on cost; handles upstream 429	Too late — the request already happened
A crucial gotcha for your setup: if you add per-IP limiting inside FastAPI behind Nginx without correct X-Forwarded-For handling, every request appears to come from 127.0.0.1 and all users share one bucket. Key on user_id from the JWT and this problem disappears.
5. Libraries and providers
Python / FastAPI
Option	What it is	Fit for NorthStar
slowapi	Port of Flask-Limiter; @limiter.limit("5/minute"), storage via limits (memory, Redis, memcached, Mongo)	Fastest to ship; needs a custom key_func to decode your JWT; no cost weighting
fastapi-limiter	Redis + Depends(RateLimiter(times=..., seconds=...))	Clean DI, but Redis-only and fixed-window
limits (used by slowapi)	Storage/strategy library: fixed-window, moving-window, sliding-window-counter	Good if you want strategies without slowapi's decorators
asgi-ratelimit	Pure ASGI middleware, Redis/memory	Good for global/per-route, awkward per-user
tenacity / backoff	Retry with exponential backoff + jitter	Essential for Gemini 429/ResourceExhausted
asyncio.Semaphore / anyio.CapacityLimiter	Concurrency caps	Needed around LLM calls regardless
Storage backends
Backend	Latency	Ops cost	Notes
In-process dict	~0	none	Per uvicorn worker. With --workers 2, effective limit is 2×. Fine for tests/local only
Postgres/Supabase table + RPC	5–20ms	none new	Atomic via a plpgsql function; you already have this. Adds writes to the hot path
Redis (Upstash, ElastiCache)	<1ms	new service	Upstash gives a plain TLS rediss:// URL + free tier, no VPC. ElastiCache needs VPC/subnets/security groups
DynamoDB atomic counter	few ms	low	Fine but you're not otherwise in DynamoDB
Edge / provider options
- Nginx limit_req_zone + limit_conn_zone — already yours. Cheapest win, do this first.
- Cloudflare Rate Limiting / WAF — only if you front the site with Cloudflare; gives bot management + IP reputation for free-ish.
- AWS WAF rate-based rules — needs ALB or CloudFront. You're Nginx-fronted on EC2, so it's not currently in the path.
- API Gateway usage plans/API keys — would require moving the API; not worth it.
- Gemini's own quotas — Google Cloud console sets per-model RPM/TPM/RPD. Treat as the last line, not your strategy: it's project-wide and hits everyone.
- LLM gateway (LiteLLM proxy, Portkey, Helicone) — centralises provider quota, budgets, retries, and spend tracking across keys. Overkill today; worth knowing if you add more providers.
6. How I'd implement it in NorthStar (phased)
The design fits the hexagonal structure you already have (domain/ports.py, infrastructure/*). Rate limiting is a domain policy with a storage adapter — not middleware soup.
Phase 0 — Instrument first (half a day)
You already have observability.py logging JSON timing events. Add user_id and a rate_limit event (bucket, allowed, remaining, cost). Without this you'll tune blind, and you'll never know whether a limit is protecting you or just annoying users.
Also decide your numbers from data: loadtest/k6-read.js exists; add a k6 scenario that hammers /chat/message from one account to find the real saturation point.
Phase 1 — Edge + auth (no new dependencies)
Nginx is your cheapest and most reliable layer:
# http {} block
limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=api:10m  rate=30r/s;
limit_conn_zone $binary_remote_addr zone=conn:10m;

# server {}
location ~ ^/auth/(login|register)$ {
    limit_req zone=auth burst=5 nodelay;
    limit_req_status 429;
    add_header Retry-After 30 always;
    proxy_pass http://127.0.0.1:8000;
}
location / {
    limit_conn conn 20;
    limit_req  zone=api burst=40 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8000;
}
If Cloudflare ever sits in front, $binary_remote_addr becomes a Cloudflare IP — configure real_ip_header CF-Connecting-IP + set_real_ip_from ranges, or the limit is meaningless.
For login specifically, also add per-email backoff in the app (IP limits don't stop distributed credential stuffing, and don't stop one attacker rotating IPs against one account). Argon2 verification is expensive — you're also DoSing your own CPU.
Phase 2 — Per-user token bucket in the app (the main event)
The port (add to backend/app/domain/ports.py, next to your existing Clock protocol):
@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: float
    retry_after_seconds: int

class RateLimiter(Protocol):
    def consume(self, key: str, *, cost: int = 1) -> RateLimitDecision: ...
The policies — one table, easy to review and tune:
# backend/app/domain/rate_limit/policies.py
@dataclass(frozen=True)
class Policy:
    capacity: int          # burst size, in cost units
    refill_per_second: float
    default_cost: int = 1

POLICIES = {
    # sustained messages/min ≈ refill*60 / cost
    "chat_message":    Policy(capacity=40, refill_per_second=0.20, default_cost=5),   # ~8 burst, 2.4/min sustained
    "note_create":     Policy(capacity=30, refill_per_second=0.10, default_cost=3),   # ~10 burst, 2/min
    "summary_generate":Policy(capacity=20, refill_per_second=0.01, default_cost=20),  # 1 burst, 3/hour
    "recall_answer":   Policy(capacity=60, refill_per_second=0.50, default_cost=2),
    "auth_attempt":    Policy(capacity=5,  refill_per_second=0.05, default_cost=1),   # 5 burst, 3/min
}
Note summary_generate: capacity=20, cost=20 means one in the bucket, refilling at 0.01/s = one every ~100s. That's how you express "expensive, rare" in the same mechanism as "cheap, frequent".
The in-memory adapter (for tests and local dev — inject the clock, like your Clock port):
class InMemoryRateLimiter:
    def __init__(self, policies, clock=time.monotonic):
        self._policies, self._clock = policies, clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def consume(self, key: str, *, cost: int | None = None) -> RateLimitDecision:
        policy = self._policies[key.split(":", 1)[0]]
        cost = cost or policy.default_cost
        now = self._clock()
        with self._lock:
            tokens, updated = self._buckets.get(key, (float(policy.capacity), now))
            tokens = min(policy.capacity, tokens + (now - updated) * policy.refill_per_second)
            if tokens >= cost:
                self._buckets[key] = (tokens - cost, now)
                return RateLimitDecision(True, tokens - cost, 0)
            self._buckets[key] = (tokens, now)
            wait = (cost - tokens) / policy.refill_per_second
            return RateLimitDecision(False, tokens, math.ceil(wait))
The shared adapter (Supabase) — atomic token bucket in one RPC. This is the part people get wrong: read-then-write across two HTTP calls is a race, and with 2 workers it will race.
create table if not exists rate_limit_buckets (
  key         text primary key,
  tokens      double precision not null,
  updated_at  timestamptz not null default now()
);

create or replace function consume_rate_limit(
  p_key text, p_capacity double precision,
  p_refill_per_second double precision, p_cost double precision
) returns table (allowed boolean, remaining double precision, retry_after_seconds double precision)
language plpgsql as $$
declare
  v_now    timestamptz := clock_timestamp();   -- DB clock, not app clock
  v_tokens double precision;
begin
  insert into rate_limit_buckets as b (key, tokens, updated_at)
  values (p_key, p_capacity, v_now)
  on conflict (key) do update
    set tokens = least(p_capacity,
                       b.tokens + extract(epoch from (v_now - b.updated_at)) * p_refill_per_second),
        updated_at = v_now
  returning tokens into v_tokens;

  if v_tokens >= p_cost then
    update rate_limit_buckets set tokens = tokens - p_cost where key = p_key;
    return query select true, v_tokens - p_cost, 0::double precision;
  end if;
  return query select false, v_tokens,
                      ceil((p_cost - v_tokens) / p_refill_per_second);
end; $$;
The row lock taken by ON CONFLICT DO UPDATE is held until the transaction ends, so concurrent callers serialise on the key and the follow-up UPDATE is safe. Use clock_timestamp() inside the DB, not a timestamp passed from Python — two workers' clocks drift, and a request can arrive "before" the stored updated_at.
The FastAPI integration — a dependency, not a decorator. This matters: dependencies run after get_current_user_id, so you get the real user without decoding the JWT twice.
# backend/app/api/rate_limit.py
def rate_limit(bucket: str, cost: int | None = None):
    def dependency(user_id: str = Depends(get_current_user_id)) -> None:
        decision = get_rate_limiter().consume(f"{bucket}:{user_id}", cost=cost)
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail="rate_limited",
                headers={
                    "Retry-After": str(decision.retry_after_seconds),
                    "RateLimit-Limit": str(POLICIES[bucket].capacity),
                    "RateLimit-Remaining": str(int(decision.remaining)),
                },
            )
    return Depends(dependency)
Usage on the expensive routes:
@router.post("/message", response_model=ChatMessageResponse)
async def send_chat_message(
    payload: ChatMessageRequest,
    user_id: str = Depends(get_current_user_id),
    _: None = rate_limit("chat_message"),
): ...
And the weighted case, where cost comes from the payload:
_: None = rate_limit("recall_answer", cost=min(len(payload.candidate_ids), 20))
This is the single most important detail for your codebase: accept-batch must charge per candidate, otherwise it's a free pass to N LLM calls.
Phase 3 — Protect Gemini and the workers
Rate limiting per user doesn't protect you if 100 users each stay under their limit. Add:
1. Concurrency semaphore per user for chat: 2 simultaneous messages, else 429 "one at a time". Per-process (asyncio.Semaphore), so with 2 workers it's really 4 — acceptable, or move it to Redis if you care.
2. Global per-worker LLM semaphore (e.g. 8) sized to your threadpool. This is what stops GET /health from timing out when 30 chats arrive.
3. Upstream 429 handling:
from google.api_core.exceptions import ResourceExhausted
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

@retry(retry=retry_if_exception_type(ResourceExhausted),
       wait=wait_exponential_jitter(initial=2, max=30),
       stop=stop_after_attempt(3), reraise=True)
def _call_gemini(...): ...
Then map final failure to 503 + Retry-After, not 500 — it's not the client's fault and the client shouldn't retry immediately.
4. Daily token budget. Gemini responses carry usage_metadata (prompt_token_count / candidates_token_count), available on LangChain AIMessage.usage_metadata. Debit a per-user daily bucket with real token counts after the call. This is the only limit that tracks actual cost, and it's the one you'll want when the bill arrives. Order matters: pre-check the request-cost estimate, post-debit the real usage.
5. Queue depth for notes. This is where I'd not use 429 as the first response. You already have SQS + a worker. The right behaviour is "accept and queue" until the user's backlog is unreasonable, then 429. Add a processing-count check before send_note_job in notes.py:98. Rejecting note creation at 2/min when each note takes 40s is fine; rejecting the third note a user writes in a burst is hostile.
Phase 4 — Client + observability
Frontend gap: requestJson in frontend/src/shared/api/httpClient.ts:589 turns every non-OK into new Error(detail). A 429 shows the user "rate_limited" with no countdown, and — worse — the note-status poller keeps firing, so a throttled user generates a retry storm that keeps them throttled. Fix:
if (response.status === 429) {
  const retryAfter = Number(response.headers.get("Retry-After") ?? 30);
  throw new RateLimitedError(readErrorMessage, retryAfter);  // carries seconds
}
Then in ChatPage / note composer: disable submit, show "You're going a bit fast — try again in 12s", and stop polling status on 429. Without this, your limiter creates a worse experience than the problem it solves.
Tests (deterministic, no Redis needed — this is why the clock is injectable):
- bucket refills at the right rate, burst then deny;
- cost=20 denies the second summary but allows one after refill;
- 429 carries Retry-After and the standard headers;
- fail-open behaviour when the store raises (see below);
- accept-batch charges per candidate.
7. Tradeoffs — the honest list
Tradeoff	What it means here	How to decide
Latency	Redis ~0.5ms; Supabase RPC ~5–20ms per protected request, on a path that already takes 5–20s for LLM calls	Negligible vs LLM time. Don't over-optimise
Availability of the limiter	If Supabase/Redis is down, do you block everyone or let everyone through?	Fail open for read endpoints, fail closed only for auth and expensive LLM calls. Log every fail-open
Accuracy vs. complexity	--workers 2 + in-memory = 2× your intended limit; restarts reset buckets	Use a shared store for anything you actually care about
False positives	NAT/office IPs, multiple tabs, mobile retries, a user legitimately writing 5 notes after a meeting	Key on user, generous burst, count cost not requests, make limits visible
Burst vs. smoothness	Too strict = broken UX; too loose = pointless	Token bucket, tune from logs, don't guess
Fairness vs. revenue	A hard limit on a paying user is a churn event	Tiers (free/paid) later; keep policy per-user, not per-IP
DB load	Supabase connection limits (pooler!) + a write per request	At your scale, fine. If rate_limit_buckets grows, purge rows older than a day on a schedule
Nginx + app double-limiting	Two limits, two failure modes, confusing 429s	Use Nginx for floods/auth, app for fairness/cost. Don't duplicate the same rule
Complexity budget	You're a single-EC2, single-tenant-ish app	Don't build a quota service on day one. Phase 1 + 2 covers 90%
Security theatre	Rate limiting ≠ bot prevention. Attackers rotate IPs and make accounts	Pair with email verification / CAPTCHA on register, and per-email lockout on login
Observability debt	Limits you can't measure are limits you'll remove in frustration	Log allowed/denied per bucket, alert when a bucket denies >X% of traffic
Failure modes to avoid, all of which I've seen in this exact shape:
- Clock skew → use the store's clock (clock_timestamp(), Redis TIME), never datetime.now() from two workers.
- Read-then-write → the TOCTOU race. One atomic operation.
- Cost blindness → 100 requests/min that each cost $0.10 is not a limit.
- 429 without Retry-After → clients retry instantly and make it worse.
- 429 for a global outage → use 503; 429 tells the user they did something wrong.
- Throttling the status poller → the UI spins forever; exempt or generously limit GET /notes/{id}.
- No idempotency on POST /notes / /chat/message → double-click = double spend, and rate limiting can't tell the two apart. A client-supplied Idempotency-Key (or a natural key like user_id:thread_id:client_msg_id) is the real fix; rate limiting is just the backstop.
8. What I'd recommend, concretely
Do this, in order:
1. Nginx limit_req on /auth/* + a global limit_conn. ~20 lines, blocks the worst abuse today, zero new dependencies.
2. A RateLimiter port + Supabase RPC adapter, keyed on user_id, token bucket, cost-weighted, wired as a Depends. This gives you fair per-user limits that survive the 2-worker topology, with no new infrastructure and no new vendor.
3. Semaphore around LLM calls + tenacity retry on Gemini 429. This is what actually keeps /health alive.
4. Cost-weighted accept-batch and summary generation, plus post-hoc token debit from usage_metadata.
5. Frontend 429 handling with Retry-After, and stop polling when throttled.
6. Log and tune. Start generous, tighten based on deny rates, not vibes.
Skip for now: Redis/ElastiCache (adds a service and a failure mode for <20ms of savings), Cloudflare/WAF (not in your path), an LLM gateway (only worth it when you add a second provider or a second product), tiered plans (no paying tiers yet).
One caveat on the Supabase adapter: you're already sensitive to PostgREST/Supabase latency and connection limits (supabase_http_client.py was written to paper over dropped HTTP/2 connections). A per-request RPC adds load to a dependency that has already shown flakiness. So: implement it, but behind the RateLimiter port, with a circuit-breaker/fail-open path, so swapping to Upstash Redis later is a one-file change. That's the real reason to use a port here, not ceremony.
Two things worth deciding before this becomes an implementation plan:
1. Scope: (a) just auth + edge protection, (b) per-user limits on the LLM endpoints, or (c) b + token budgets and concurrency control. I'd do (b), then (c) once you've seen real usage.
2. Storage: Supabase RPC (no new infra, adds DB writes) vs. Upstash Redis (fastest, new vendor). I lean Supabase first behind the port, because your scale is small and you already have the dependency.
Tell me which you want and I'll write it up as a phased plan with the exact files touched — then switch out of Plan mode to implement. (I haven't modified anything; this is discussion only.)