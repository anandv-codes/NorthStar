import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = (__ENV.API_BASE || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const PASSWORD = __ENV.TEST_PASSWORD || 'NorthStarLoad1';

export const options = {
  vus: Number(__ENV.VUS || 20),
  duration: __ENV.DURATION || '2m',
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{name:recall_due}': ['p(95)<500'],
    'http_req_duration{name:recall_candidates}': ['p(95)<500'],
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

  const email = `k6+${Date.now()}@example.com`;
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
  const headers = { Authorization: `Bearer ${data.token}` };

  const health = http.get(`${BASE}/health`, {
    tags: { name: 'health' },
  });
  check(health, { 'health 200': (response) => response.status === 200 });

  const due = http.get(`${BASE}/recall/due`, {
    headers,
    tags: { name: 'recall_due' },
  });
  check(due, { 'due 200': (response) => response.status === 200 });

  const candidates = http.get(`${BASE}/recall/candidates?limit=5`, {
    headers,
    tags: { name: 'recall_candidates' },
  });
  check(candidates, {
    'candidates 200': (response) => response.status === 200,
  });

  if (__ENV.NOTE_ID) {
    const note = http.get(`${BASE}/notes/${__ENV.NOTE_ID}`, {
      headers,
      tags: { name: 'note_get' },
    });
    check(note, { 'note 200': (response) => response.status === 200 });
  }

  sleep(Math.random() + 0.5);
}
