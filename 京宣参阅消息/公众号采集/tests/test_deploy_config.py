from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
COMPOSE = PROJECT_DIR / "compose.yml"
DOCKERFILE = PROJECT_DIR / "Dockerfile"


def test_compose_uses_existing_exporter_network_and_read_only_mounts():
    compose = COMPOSE.read_text(encoding="utf-8")

    assert compose.startswith("name: jingxuan-wechat-collector\n")
    assert "wechat-article-exporter_default" in compose
    assert "/opt/wechat-article-exporter/data/kv/cookie:/exporter-kv-cookie:ro" in compose
    assert "/opt/wechat-article-exporter/sync-state:/existing-sync-state:ro" in compose
    assert "GITHUB_TOKEN: ${GITHUB_TOKEN:?GITHUB_TOKEN is required}" in compose
    assert "./state:/state" in compose
    assert "user: \"10001:10001\"" in compose
    assert "install -d -o 10001 -g 10001 state" in compose


def test_dockerfile_runs_the_collector_as_a_non_root_python_312_image():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM docker.1ms.run/python:3.12-slim" in dockerfile
    assert "COPY requirements.txt ./" in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert "COPY collector.py config.py exporter.py github_feed.py models.py state.py ./" in dockerfile
    assert "groupadd --gid 10001 app" in dockerfile
    assert "useradd --uid 10001 --gid app" in dockerfile
    assert "USER app" in dockerfile
    assert 'CMD ["python", "/app/collector.py", "run"]' in dockerfile
