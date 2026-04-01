import json
from pathlib import Path


def test_grafana_datasources_and_dashboard_assets_exist():
    repo_root = Path(__file__).resolve().parents[2]
    datasources_path = repo_root / "ops" / "grafana" / "provisioning" / "datasources" / "datasources.yaml"
    dashboards_path = repo_root / "ops" / "grafana" / "provisioning" / "dashboards" / "dashboards.yaml"
    dashboard_json_path = repo_root / "ops" / "grafana" / "dashboards" / "fan-experience-observability.json"

    datasources = datasources_path.read_text()
    dashboards = dashboards_path.read_text()
    dashboard = json.loads(dashboard_json_path.read_text())

    assert "name: Prometheus" in datasources
    assert "uid: prometheus" in datasources
    assert "url: http://prometheus:9090" in datasources
    assert "name: Tempo" in datasources
    assert "uid: tempo" in datasources
    assert "url: http://tempo:3200" in datasources
    assert "folder: Observability" in dashboards
    assert "path: /var/lib/grafana/dashboards" in dashboards
    assert dashboard["title"] == "Fan Experience Observability"
    assert dashboard["uid"] == "fan-experience-observability"

    panel_titles = {panel["title"] for panel in dashboard["panels"]}
    assert "HTTP Request Rate" in panel_titles
    assert "HTTP P95 Latency" in panel_titles
    assert "Plan Generation Outcomes" in panel_titles
    assert "Trace Usage" in panel_titles
