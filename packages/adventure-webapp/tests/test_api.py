from fastapi.testclient import TestClient

from adventure_webapp.app import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_choose_flow():
    # create
    r = client.post("/api/games", json={"template_id": "veiled-archive", "actor": "Elaria", "seed": 42})
    assert r.status_code == 200, r.text
    data = r.json()
    gid = data["game_id"]
    assert data["pending"]["choices"]["obvious"]

    # choose obvious -> roll determines outcome (could be success/partial/failure)
    r2 = client.post(f"/api/games/{gid}/choose", json={"pick": "obvious"})
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert "turn" in j2
    assert j2["turn"]["picked"] == "obvious"
    assert j2["turn"]["roll"]["outcome"] in ("success", "critical", "partial", "failure")

    # auto
    gid2 = client.post("/api/games", json={"template_id": "goblin-ambush", "seed": 99}).json()["game_id"]
    r3 = client.post(f"/api/games/{gid2}/auto", json={})
    assert r3.status_code == 200
    assert r3.json()["turn"]["picked"] in ("obvious", "option", "odd")


def test_invalid_pick_400():
    gid = client.post("/api/games", json={"seed": 1}).json()["game_id"]
    r = client.post(f"/api/games/{gid}/choose", json={"pick": "nonsense"})
    assert r.status_code == 400


def test_index_serves():
    r = client.get("/")
    assert r.status_code == 200
    assert "Choose Your Adventure" in r.text


def test_lonelog_views_and_clean_interface():
    gid = client.post("/api/games", json={"seed": 42}).json()["game_id"]
    data = client.get(f"/api/games/{gid}").json()
    assert data["lonelog_lines"][0].startswith("S1 ")
    assert data["lonelog"] == "```lonelog\n" + "\n".join(data["lonelog_lines"]) + "\n```"
    story = client.get(f"/api/games/{gid}/story").json()
    assert story["lonelog_lines"] == data["lonelog_lines"]

    html = client.get("/").text
    # story + debug view switchers present
    assert 'data-storyview="story"' in html
    assert 'data-storyview="lonelog"' in html
    assert 'data-storyview="raw"' in html
    assert 'data-debugview="state"' in html
    assert 'data-debugview="lonelog"' in html
    # interface is clean — no FUSE/JSONL jargon in served UI
    low = html.lower()
    assert "jsonl" not in low
    assert "fused" not in low
