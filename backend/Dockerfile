FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: curl for healthchecks + chromium runtime libs for headless verify.
# (python:3.11-slim is Debian; playwright's --with-deps assumes Ubuntu and fails, so
#  we install the chromium runtime libraries explicitly and run `playwright install`
#  WITHOUT --with-deps.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl openssh-client \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
        libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libx11-6 \
        libxcb1 libxcb-dri3-0 libgtk-3-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Headless browser binary for typed verification (deps installed above)
RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
