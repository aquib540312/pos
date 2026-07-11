def test_list_branches_includes_warehouses(client, seeded_org):
    resp = client.get("/api/v1/org/branches", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    branches = resp.json()
    assert len(branches) == 1
    assert branches[0]["id"] == str(seeded_org["branch"].id)
    assert branches[0]["warehouses"][0]["id"] == str(seeded_org["warehouse"].id)
