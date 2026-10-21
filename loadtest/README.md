# Load tests

`k6` scripts for a reproducible API p95. They are not part of CI because they
need a running API, Supabase, and (for writes) SQS plus a worker.

Install k6 on your laptop or the EC2 host (`brew install k6`,
`winget install k6`, or your distribution's package), then run from the
repository root.

## Read scenario

```bash
k6 run -e API_BASE=https://api.example.com loadtest/k6-read.js
```

Defaults: 20 VUs for 2 minutes, hitting `GET /health`, `GET /recall/due`, and
`GET /recall/candidates?limit=5`. Requests are tagged (`health`, `recall_due`,
`recall_candidates`) so the thresholds expose per-endpoint p95. Override with
`VUS` and `DURATION`:

```bash
k6 run -e API_BASE=https://api.example.com -e VUS=10 -e DURATION=5m \
  loadtest/k6-read.js
```

The setup step registers a throwaway `k6+<timestamp>@example.com` account. To
use an existing account instead:

```bash
k6 run -e API_BASE=https://api.example.com \
  -e TEST_EMAIL=you@example.com -e TEST_PASSWORD='your-password1' \
  loadtest/k6-read.js
```

The password must contain a letter and a digit. Do not use a production
account for repeated load tests; test notes and throwaway users persist because
there is no cleanup endpoint.

## Write scenario

`POST /notes` returns `202` after writing the note and enqueueing the SQS job.
This script measures that enqueue path only:

```bash
k6 run -e API_BASE=https://api.example.com -e ITERATIONS=10 \
  loadtest/k6-note-write.js
```

**Cost warning:** every note still triggers Gemini extraction and embedding
work in the worker, even with `recall_enabled=false`. Keep `ITERATIONS` small.

Worker processing time is measured separately by the `note_processing` timing
events; see `docs/ec2_deployment.md` section 11.

## Reading the result

k6 reports client-observed latency, which includes TLS, your network, and
Nginx:

```text
http_req_duration........: avg=... p(90)=... p(95)=... p(99)=... max=...
http_req_failed..........: ...%
```

The server-side p95 comes from the API's `request_timing` JSON logs:

```bash
cd /opt/northstar
sudo journalctl -u northstar-api -o cat --since "1 hour ago" \
  | python3 backend/scripts/p95_latency.py --event request_timing
```

For a resume or report, state the conditions rather than only the number:

| Field | Example |
|---|---|
| Endpoints | `GET /health`, `GET /recall/due`, `GET /recall/candidates` |
| Load | 20 VUs, 2 minutes |
| Client p95 | e.g. `118 ms` |
| Server p95 | e.g. `74 ms` |
| Instance | e.g. `t3.medium` |
| Region / client | e.g. `us-east-1`, same-region EC2 |

Run k6 from EC2 or a nearby region if you want a number close to server-side
latency. From a home network, label the result "client-observed p95".

A p95 needs enough samples to be meaningful. The read scenario produces
hundreds to thousands of requests. For worker processing, wait until enough
notes have completed; with only a handful, report p50 and sample size instead.

The scripts include starter thresholds (p95 under 500 ms for reads, 1 s for
`POST /notes`). A threshold failure makes k6 exit nonzero but still prints the
summary; adjust the thresholds after your first baseline.
