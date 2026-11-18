import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '15s', target: 10 },
    { duration: '20s', target: 30 },
    { duration: '30s', target: 50 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<1500'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8888';

export default function () {
  const response = http.get(`${BASE_URL}/work?ms=20`, { tags: { ruta: 'work' } });
  check(response, {
    'HTTP 200': (r) => r.status === 200,
    'identifica backend': (r) => ["1", "2", "3"].includes(String(r.json('instancia'))),
  });
  sleep(0.2);
}
