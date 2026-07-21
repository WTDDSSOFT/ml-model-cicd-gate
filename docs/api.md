# API contract

Base URL (local): `http://localhost:8000`. Source: [`api/serve.py`](../api/serve.py).

## `GET /health`

Liveness/readiness probe. Used by [`scripts/health_check.py`](../scripts/health_check.py) (Jenkins smoke test) and by [`ansible/deploy.yml`](../ansible/deploy.yml)'s blue-green health gate. Always returns `200` -- it reports model status in the body rather than failing the HTTP call, so callers can distinguish "process is up but model didn't load" from "process is down".

**Response `200`**

```json
{
  "status": "ok",
  "model_version": "a1b2c3d",
  "model": "loaded"
}
```

`model` is `"loaded"` or `"missing"` depending on whether `model/artifacts/model.pt` was found at startup.

## `POST /predict`

Classifies an uploaded grayscale digit image. Multipart form upload, field name `file`.

Rate-limited (`PREDICT_RATE_LIMIT`, default `20/minute`, keyed by client IP) and size-limited (`PREDICT_MAX_UPLOAD_BYTES`, default 2 MiB). Input is validated before the model is touched, so a bad upload always gets `400` regardless of whether a model is currently loaded.

**Request**

```bash
curl -X POST -F "file=@digit.png" http://localhost:8000/predict
```

**Response `200`**

```json
{
  "prediction": "7",
  "confidence": 0.9821,
  "model_version": "a1b2c3d"
}
```

| Field | Type | Notes |
|---|---|---|
| `prediction` | string | One of `"0"`-`"9"` |
| `confidence` | float | Top-1 softmax probability, `0.0`-`1.0` |
| `model_version` | string | Same value as `/health`'s `model_version` |

**Error responses**

| Status | Cause |
|---|---|
| `400` | Uploaded file isn't a decodable image |
| `413` | Uploaded file exceeds `PREDICT_MAX_UPLOAD_BYTES` |
| `429` | Rate limit exceeded for this client |
| `503` | No model artifact loaded (`model/artifacts/model.pt` missing) |

## `GET /metrics`

Prometheus exposition format (`text/plain`), scraped by [`monitoring/prometheus.yml`](../monitoring/prometheus.yml). See the [Grafana dashboard section of the README](../README.md#grafana-dashboard) for what each custom metric means.

Open by default (matches the local docker-compose demo, where Prometheus sends no auth header). If `METRICS_TOKEN` is set, requires a matching `X-Metrics-Token` header and returns `401` otherwise -- see the environment variable table below for when to set it.

## Environment variables

| Variable | Default | Used by | Purpose |
|---|---|---|---|
| `MODEL_VERSION` | `dev` | `api/serve.py`, `Dockerfile` | Reported in `/health` and `/predict`; set to the commit hash at build/deploy time |
| `PREDICT_RATE_LIMIT` | `20/minute` | `api/serve.py` | slowapi rate limit spec for `POST /predict` |
| `PREDICT_MAX_UPLOAD_BYTES` | `2097152` (2 MiB) | `api/serve.py` | Max accepted upload size for `POST /predict` |
| `METRICS_TOKEN` | unset | `api/serve.py` | When set, requires `X-Metrics-Token: <value>` on `GET /metrics` |
| `TRAIN_SEED` | `42` | `model/train.py` | Seed for `random`/`numpy`/`torch`; see the README's [reproducibility section](../README.md#training-reproducibility) |
| `REGISTRY_URL` | unset | `Jenkinsfile`, `ansible/deploy.yml` (as `app_registry`) | Container registry to push to / pull from; no-op when unset |
| `SLACK_WEBHOOK_URL` | unset | `scripts/notify.py` | When set, posts pipeline stage notifications there instead of just printing them |
| `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` / `GF_AUTH_ANONYMOUS_ENABLED` | `admin` / `admin` / `true` | `docker-compose.yml` | Grafana credentials for the local demo; see `.env.example` |
