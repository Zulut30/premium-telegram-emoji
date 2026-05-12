FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir aiogram

COPY bot.py .
COPY emoji-ids.txt .
COPY references/ references/

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

CMD ["python", "bot.py"]
