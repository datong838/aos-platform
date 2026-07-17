"""S2 remainder / Ferry surface — scheme 49 + 53 MVP."""


def test_code_repos_and_ferry_mvp(client, auth_headers):
    repos = client.get("/v1/code-repos", headers=auth_headers)
    assert repos.status_code == 200
    body = repos.json()
    assert body["store"] == "dev-seed"
    assert len(body["items"]) >= 1

    st = client.get("/v1/apollo/ferry/status", headers=auth_headers)
    assert st.status_code == 200
    assert st.json()["deferred"] is False
    assert st.json()["mode"] == "mvp-hmac+images"

    ex = client.post("/v1/apollo/ferry/export", headers=auth_headers, json={})
    assert ex.status_code == 200
    assert ex.json()["contentBase64"]

    im = client.post(
        "/v1/apollo/ferry/import",
        headers=auth_headers,
        json={"contentBase64": ex.json()["contentBase64"]},
    )
    assert im.status_code == 200
    assert im.json()["ok"] is True
