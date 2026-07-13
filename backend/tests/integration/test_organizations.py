def test_list_branches_includes_warehouses(client, seeded_org):
    resp = client.get("/api/v1/org/branches", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    branches = resp.json()
    assert len(branches) == 1
    assert branches[0]["id"] == str(seeded_org["branch"].id)
    assert branches[0]["warehouses"][0]["id"] == str(seeded_org["warehouse"].id)


def test_create_branch_then_appears_in_list(client, seeded_org):
    resp = client.post(
        "/api/v1/org/branches",
        headers=seeded_org["auth_headers"],
        json={"code": "NORTH", "name": "North Branch", "business_type": "grocery", "state_code": "27"},
    )
    assert resp.status_code == 201, resp.text
    branch = resp.json()
    assert branch["code"] == "NORTH"
    assert branch["warehouses"] == []

    list_resp = client.get("/api/v1/org/branches", headers=seeded_org["auth_headers"])
    assert any(b["id"] == branch["id"] for b in list_resp.json())


def test_create_branch_rejects_duplicate_code(client, seeded_org):
    resp = client.post(
        "/api/v1/org/branches",
        headers=seeded_org["auth_headers"],
        json={"code": "MAIN", "name": "Duplicate", "state_code": "27"},
    )
    assert resp.status_code == 409


def test_create_warehouse_under_branch(client, seeded_org):
    branch_resp = client.post(
        "/api/v1/org/branches",
        headers=seeded_org["auth_headers"],
        json={"code": "SOUTH", "name": "South Branch", "state_code": "27"},
    )
    branch_id = branch_resp.json()["id"]

    wh_resp = client.post(
        f"/api/v1/org/branches/{branch_id}/warehouses",
        headers=seeded_org["auth_headers"],
        json={"code": "WH1", "name": "South Warehouse", "is_default": True},
    )
    assert wh_resp.status_code == 201, wh_resp.text
    assert wh_resp.json()["is_default"] is True

    list_resp = client.get("/api/v1/org/branches", headers=seeded_org["auth_headers"])
    branch = next(b for b in list_resp.json() if b["id"] == branch_id)
    assert branch["warehouses"][0]["code"] == "WH1"


def test_create_warehouse_rejects_duplicate_code_in_same_branch(client, seeded_org):
    resp = client.post(
        f"/api/v1/org/branches/{seeded_org['branch'].id}/warehouses",
        headers=seeded_org["auth_headers"],
        json={"code": "WH1", "name": "Duplicate"},
    )
    assert resp.status_code == 409


def test_create_warehouse_404_for_unknown_branch(client, seeded_org):
    import uuid

    resp = client.post(
        f"/api/v1/org/branches/{uuid.uuid4()}/warehouses",
        headers=seeded_org["auth_headers"],
        json={"code": "WHX", "name": "Nowhere"},
    )
    assert resp.status_code == 404
