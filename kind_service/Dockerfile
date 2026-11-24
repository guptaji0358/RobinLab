FROM python:3.12-slim

# A bold TTF for the watermark text (falls back to Pillow's built-in font without it).
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# Hugging Face Spaces expects the app on port 7860.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
