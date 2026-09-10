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
