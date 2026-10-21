import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = (__ENV.API_BASE || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const PASSWORD = __ENV.TEST_PASSWORD || 'NorthStarLoad1';

export const options = {
  scenarios: {
    writes: {
      executor: 'shared-iterations',
      vus: Number(__ENV.VUS || 2),
      iterations: Number(__ENV.ITERATIONS || 10),
      maxDuration: __ENV.MAX_DURATION || '5m',
    },
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{name:notes_create}': ['p(95)<1000'],
  },
};

export function setup() {
  if (__ENV.TEST_EMAIL) {
    const response = http.post(
      `${BASE}/auth/login`,
      JSON.stringify({ email: __ENV.TEST_EMAIL, password: PASSWORD }),
      { headers: { 'Content-Type': 'application/json' } },
    );
    if (response.status !== 200) {
      throw new Error(`login failed: ${response.status} ${response.body}`);
    }
    return { token: response.json().access_token };
  }

  const email = `k6-write+${Date.now()}@example.com`;
  const response = http.post(
    `${BASE}/auth/register`,
    JSON.stringify({ email, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  if (response.status !== 201) {
    throw new Error(`register failed: ${response.status} ${response.body}`);
  }
  return { token: response.json().access_token };
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };
  const response = http.post(
    `${BASE}/notes`,
    JSON.stringify({
      text: `k6 load test note ${Date.now()}-${__ITER}`,
      metadata: { source: 'k6' },
      recall_enabled: __ENV.RECALL_ENABLED === 'true',
    }),
    {
      headers,
      tags: { name: 'notes_create' },
    },
  );
  check(response, { 'note accepted 202': (result) => result.status === 202 });
  sleep(Number(__ENV.SLEEP || 2));
}
