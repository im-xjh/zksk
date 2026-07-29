FROM docker.1ms.run/python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir /state \
    && chown app:app /state

COPY collector.py config.py exporter.py github_feed.py models.py state.py ./

USER app

CMD ["python", "/app/collector.py", "run"]
