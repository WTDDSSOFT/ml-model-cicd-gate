# --- Stage 1: train the model -------------------------------------------
FROM python:3.12-slim AS trainer

WORKDIR /build
COPY model/requirements.txt model/requirements.txt
RUN pip install --no-cache-dir -r model/requirements.txt

COPY model/ model/
RUN python model/train.py

# --- Stage 2: runtime image, only what serve.py needs --------------------
FROM python:3.12-slim AS runtime

ARG MODEL_VERSION=unknown
ENV MODEL_VERSION=${MODEL_VERSION} \
    PYTHONUNBUFFERED=1

RUN groupadd --system appuser && useradd --system --gid appuser --home /app --no-create-home appuser

WORKDIR /app
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY --chown=appuser:appuser model/common.py model/common.py
COPY --chown=appuser:appuser api/serve.py api/serve.py
COPY --chown=appuser:appuser --from=trainer /build/model/artifacts/ model/artifacts/

USER appuser

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "api.serve:app", "--host", "0.0.0.0", "--port", "8000"]
