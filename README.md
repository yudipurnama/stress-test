# py-stress-test
A tiny HTTP stress-testing API written in Python. It exposes a REST endpoint you can call with a target URL and concurrency settings; it returns a summary (and optionally per-request details).

## Features
- Concurrency with `ThreadPoolExecutor`
- Rotating Authorization tokens per request (Basic/Bearer)
- Latency stats: average, p50, p95, p99
- JSON body support for POST/PUT/PATCH
- Simple health endpoint
- Run locally with Python or as a Docker container

## Requirements
- Python 3.9+
- pip

## Install
```bash
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## Run Locally (Python)
Use the provided `main.py` to start the API server:
```bash
python3 main.py
HOST=0.0.0.0 PORT=8000 DEBUG=true python3 main.py
```

Alternatively, run with Flask CLI or Gunicorn:
```bash
FLASK_APP=stress_test flask run --host 0.0.0.0 --port 8000
gunicorn -b 0.0.0.0:8000 stress_test:app
```

## API

### Health
- GET `/health`
```bash
curl http://localhost:8000/health
```

### Stress Test
- POST `/stress-test`
- Body (JSON):
  - `url` (string, required) — target URL to test
  - `method` (string, default `GET`) — `GET|POST|PUT|PATCH|DELETE`
  - `total_requests` (int, default `100`)
  - `max_workers` (int, default `10`)
  - `headers` (object, optional) — additional headers to send
  - `body` (object, optional) — JSON body for non-GET methods
  - `tokens` (array[string], optional) — tokens to rotate per request for Authorization
  - `auth_scheme` (string, optional) — `basic` or `bearer` (used with `tokens`)
  - `timeout` (float, default `30`) — per-request timeout in seconds
  - `include_results` (bool, default `false`) — include per-request details in response

#### Examples
Basic GET:
```bash
curl -X POST http://localhost:8000/stress-test \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://httpbin.org/get",
    "total_requests": 10,
    "max_workers": 5
  }'
```

POST with JSON body:
```bash
curl -X POST http://localhost:8000/stress-test \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://httpbin.org/post",
    "method": "POST",
    "body": {"hello": "world"},
    "total_requests": 20,
    "max_workers": 5
  }'
```

Rotate Basic tokens per request:
```bash
curl -X POST http://localhost:8000/stress-test \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://example.com/api",
    "tokens": ["abc==", "def=="],
    "auth_scheme": "basic",
    "total_requests": 50,
    "max_workers": 10
  }'
```

Include detailed per-request results:
```bash
curl -X POST http://localhost:8000/stress-test \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://httpbin.org/get",
    "total_requests": 5,
    "include_results": true
  }'
```

## Docker
Build and run with Docker:
```bash
docker buildx create --use --name multi || docker buildx use multi

docker buildx build --platform linux/amd64 --no-cache -t docker pull ghcr.io/yudipurnama/py-stress-test:v1.0.0 .

docker run --rm -p 8000:8000 py-stress-test

curl http://localhost:8000/health
```
The Docker image uses Gunicorn to serve `stress_test:app`.

### Push to GitHub Container Registry (GHCR)

Manual push from your machine (requires a GHCR PAT):
```bash
echo $GHCR_PAT | docker login ghcr.io -u <github-username> --password-stdin

docker buildx create --use --name multi || docker buildx use multi
docker buildx build \
  --platform linux/amd64 \
  --no-cache \
  -t ghcr.io/yudipurnama/stress-test:latest \
  -t ghcr.io/yudipurnama/stress-test:$(git rev-parse --short HEAD) \
  --push .
```

CI/CD via GitHub Actions:
- Workflow at `.github/workflows/docker.yml` builds on push to `main` and publishes to `ghcr.io/<owner>/stress-test`.
- Tags: `latest` (on default branch) and the commit `sha`.
- Uses the repository `GITHUB_TOKEN` with `packages: write` permission; no extra secrets needed.

Steps:
1. Push this repo to GitHub: `git@github.com:yudipurnama/stress-test.git`.
2. Ensure Actions are enabled for the repo.
3. After a push to `main`, the image will be available at:
   `https://github.com/yudipurnama/stress-test/pkgs/container/stress-test`.

## Notes
- This app is intended for test environments; be mindful not to overload real services.
- For higher throughput or precise RPS control, consider using an async client or a purpose-built tool (k6, Vegeta, Locust), or extend this app to schedule requests at a target rate.
- If you need job IDs and async retrieval for long runs, open an issue or request that enhancement.
