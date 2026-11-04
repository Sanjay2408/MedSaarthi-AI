# MedSaarthi AI, for Hugging Face Spaces (Docker SDK, free CPU tier: 2 vCPU, 16 GB RAM).
# Set GROQ_API_KEY as a Space secret. It is never baked into the image.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 app
WORKDIR /home/app/medsaarthi
ENV HF_HOME=/home/app/hf EASYOCR_MODULE_PATH=/home/app/easyocr PYTHONUNBUFFERED=1 \
    MEDSAARTHI_PUBLIC=1 HF_HUB_DISABLE_TELEMETRY=1
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt
COPY config.yaml ./
COPY src ./src
COPY api ./api
COPY data ./data
COPY --from=web /web/dist ./web/dist
RUN mkdir -p logs .cache /home/app/hf /home/app/easyocr && chown -R app:app /home/app
USER app
# Bake the models in so the first patient doesn't wait for a 3 GB download.
RUN python -c "from transformers import AutoModelForSeq2SeqLM as M, AutoTokenizer as T; n='facebook/nllb-200-distilled-600M'; T.from_pretrained(n); M.from_pretrained(n, use_safetensors=False)"
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False)"
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips", "*"]
