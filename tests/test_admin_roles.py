import pytest

from app.core.security import create_access_token


def auth(user):
    token = create_access_token(str(user["id"]), user["role"])
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_signin_accepts_admin_and_superadmin(
    api_client, user_factory
):
    for role in ("admin", "superadmin"):
        user = await user_factory(role=role)

        response = await api_client.post(
            "/api/v1/admin/auth/signin",
            json={"email": user["email"], "password": user["password"]},
        )

        assert response.status_code == 200, response.text
        assert response.json()["admin"]["role"] == role
        assert response.json()["token"]


@pytest.mark.asyncio
async def test_suspended_admin_cannot_sign_in(api_client, user_factory):
    user = await user_factory(role="admin", suspended=True)

    response = await api_client.post(
        "/api/v1/admin/auth/signin",
        json={"email": user["email"], "password": user["password"]},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_only_superadmin_can_view_and_create_staff(
    api_client, user_factory
):
    root = await user_factory(role="superadmin")
    admin = await user_factory(role="admin")
    normal_user = await user_factory(role="user")

    staff_url = "/api/v1/admin/staff"

    assert (
        await api_client.get(staff_url, headers=auth(admin))
    ).status_code == 403

    assert (
        await api_client.get(staff_url, headers=auth(normal_user))
    ).status_code == 403

    listing = await api_client.get(staff_url, headers=auth(root))
    assert listing.status_code == 200, listing.text

    listed_admins = listing.json()["admins"]
    assert all(item["role"] == "admin" for item in listed_admins)
    assert root["email"] not in {
        item["email"] for item in listed_admins
    }

    payload = {
        "email": f"created-{root['id']}@example.com",
        "password": "NewModerator!234",
        "f_name": "Created",
        "l_name": "Moderator",
    }

    denied = await api_client.post(
        staff_url, json=payload, headers=auth(admin)
    )
    assert denied.status_code == 403

    created = await api_client.post(
        staff_url, json=payload, headers=auth(root)
    )
    assert created.status_code == 201, created.text
    assert created.json()["admin"]["role"] == "admin"

    logs_denied = await api_client.get(
        f"{staff_url}/audit-logs", headers=auth(admin)
    )
    assert logs_denied.status_code == 403

    logs = await api_client.get(
        f"{staff_url}/audit-logs", headers=auth(root)
    )
    assert logs.status_code == 200, logs.text
    assert any(
        entry["action"] == "admin.created"
        and entry["targetEmail"] == payload["email"]
        for entry in logs.json()["auditLogs"]
    )


@pytest.mark.asyncio
async def test_superadmin_can_promote_and_demote_users(
    api_client, user_factory
):
    root = await user_factory(role="superadmin")
    target = await user_factory(role="user")

    url = f"/api/v1/admin/staff/{target['id']}/role"

    promoted = await api_client.patch(
        url, json={"role": "admin"}, headers=auth(root)
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["admin"]["role"] == "admin"

    demoted = await api_client.patch(
        url, json={"role": "user"}, headers=auth(root)
    )
    assert demoted.status_code == 200, demoted.text
    assert demoted.json()["admin"]["role"] == "user"


@pytest.mark.asyncio
async def test_superadmin_self_and_other_superadmin_are_protected(
    api_client, user_factory
):
    root = await user_factory(role="superadmin")
    second_root = await user_factory(role="superadmin")

    self_role = await api_client.patch(
        f"/api/v1/admin/staff/{root['id']}/role",
        json={"role": "admin"},
        headers=auth(root),
    )
    assert self_role.status_code == 400

    self_suspend = await api_client.patch(
        f"/api/v1/admin/staff/{root['id']}/suspension",
        json={"suspended": True},
        headers=auth(root),
    )
    assert self_suspend.status_code == 400

    other_role = await api_client.patch(
        f"/api/v1/admin/staff/{second_root['id']}/role",
        json={"role": "admin"},
        headers=auth(root),
    )
    assert other_role.status_code == 403

    other_suspend = await api_client.patch(
        f"/api/v1/admin/staff/{second_root['id']}/suspension",
        json={"suspended": True},
        headers=auth(root),
    )
    assert other_suspend.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_can_suspend_and_reactivate_admin(
    api_client, user_factory
):
    root = await user_factory(role="superadmin")
    moderator = await user_factory(role="admin")

    url = f"/api/v1/admin/staff/{moderator['id']}/suspension"

    suspended = await api_client.patch(
        url, json={"suspended": True}, headers=auth(root)
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["admin"]["suspended"] is True

    blocked = await api_client.get(
        "/api/v1/admin/stats", headers=auth(moderator)
    )
    assert blocked.status_code == 403

    denied_login = await api_client.post(
        "/api/v1/admin/auth/signin",
        json={
            "email": moderator["email"],
            "password": moderator["password"],
        },
    )
    assert denied_login.status_code == 403

    reactivated = await api_client.patch(
        url, json={"suspended": False}, headers=auth(root)
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["admin"]["suspended"] is False

    allowed_login = await api_client.post(
        "/api/v1/admin/auth/signin",
        json={
            "email": moderator["email"],
            "password": moderator["password"],
        },
    )
    assert allowed_login.status_code == 200


@pytest.mark.asyncio
async def test_admin_and_superadmin_share_operational_access(
    api_client, user_factory
):
    admin = await user_factory(role="admin")
    root = await user_factory(role="superadmin")
    normal_user = await user_factory(role="user")

    operational_get_routes = [
        "/api/v1/admin/stats",
        "/api/v1/admin/users",
        "/api/v1/admin/deposits",
        "/api/v1/admin/withdrawals",
        "/api/v1/admin/investments",
    ]

    for path in operational_get_routes:
        for staff in (admin, root):
            response = await api_client.get(path, headers=auth(staff))
            assert response.status_code == 200, (
                f"{staff['role']} could not access {path}: "
                f"{response.status_code} {response.text}"
            )

        denied = await api_client.get(
            path, headers=auth(normal_user)
        )
        assert denied.status_code == 403, (
            f"Normal user unexpectedly accessed {path}"
        )


@pytest.mark.asyncio
async def test_admin_user_listing_excludes_staff_accounts(
    api_client, user_factory
):
    admin = await user_factory(role="admin")
    root = await user_factory(role="superadmin")
    normal_user = await user_factory(role="user")

    response = await api_client.get(
        "/api/v1/admin/users", headers=auth(admin)
    )
    assert response.status_code == 200, response.text

    returned = response.json()["users"]
    assert all(item["role"] == "user" for item in returned)

    returned_emails = {item["email"] for item in returned}
    assert normal_user["email"] in returned_emails
    assert admin["email"] not in returned_emails
    assert root["email"] not in returned_emails


@pytest.mark.asyncio
async def test_regular_signin_is_for_users_only(api_client, user_factory):
    for role in ("admin", "superadmin"):
        staff = await user_factory(role=role)

        response = await api_client.post(
            "/api/v1/users/signin",
            json={
                "email": staff["email"],
                "password": staff["password"],
            },
        )

        assert response.status_code == 403, response.text

        admin_response = await api_client.post(
            "/api/v1/admin/auth/signin",
            json={
                "email": staff["email"],
                "password": staff["password"],
            },
        )
        assert admin_response.status_code == 200, admin_response.text

    normal_user = await user_factory(role="user")
    response = await api_client.post(
        "/api/v1/users/signin",
        json={
            "email": normal_user["email"],
            "password": normal_user["password"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["role"] == "user"
