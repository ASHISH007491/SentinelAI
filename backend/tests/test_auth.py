def _register_and_token(client, email="a@b.com", pw="pw12345"):
    client.post("/api/v1/auth/register", json={"email": email, "password": pw})
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _login(client, email, pw="pw12345"):
    return client.post(
        "/api/v1/auth/login", data={"username": email, "password": pw}
    ).json()


def test_register_login_me(client):
    token = _register_and_token(client)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "a@b.com"


def test_duplicate_register_rejected(client):
    client.post("/api/v1/auth/register", json={"email": "x@y.com", "password": "pw12345"})
    r = client.post("/api/v1/auth/register", json={"email": "x@y.com", "password": "pw12345"})
    assert r.status_code == 400


def test_runs_require_auth(client):
    assert client.get("/api/v1/runs").status_code == 401


def test_create_and_list_runs(client):
    token = _register_and_token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/v1/runs", json={"workflow": "vuln"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["workflow"] == "vuln"
    assert r.json()["architecture"] == "multi"
    runs = client.get("/api/v1/runs", headers=h).json()
    assert len(runs) == 1 and runs[0]["status"] == "queued"


def test_refresh_returns_new_access_token(client):
    client.post("/api/v1/auth/register", json={"email": "r@b.com", "password": "pw12345"})
    tokens = _login(client, "r@b.com")
    assert "refresh_token" in tokens
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_refresh_rejects_access_token(client):
    client.post("/api/v1/auth/register", json={"email": "r2@b.com", "password": "pw12345"})
    tokens = _login(client, "r2@b.com")
    # passing an ACCESS token to /refresh must be rejected (wrong token type)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401


def test_new_user_defaults_to_analyst(client):
    client.post("/api/v1/auth/register", json={"email": "role@b.com", "password": "pw12345"})
    tokens = _login(client, "role@b.com")
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.json()["role"] == "analyst"


def test_logout(client):
    client.post("/api/v1/auth/register", json={"email": "lo@b.com", "password": "pw12345"})
    tokens = _login(client, "lo@b.com")
    r = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200 and r.json()["message"]
