"""IdP claim aliases — scheme 60 (Keycloak / Azure-friendly)."""

from aos_api.auth import (
    markings_from_claims,
    org_from_claims,
    project_from_claims,
    roles_from_claims,
)


def test_roles_from_realm_access():
    claims = {"realm_access": {"roles": ["admin", "developer"]}}
    assert roles_from_claims(claims) == ["admin", "developer"]


def test_roles_prefer_explicit():
    claims = {
        "roles": ["ops"],
        "realm_access": {"roles": ["admin"]},
    }
    assert roles_from_claims(claims) == ["ops"]


def test_org_project_aliases():
    claims = {"orgId": "o1", "projectId": "p1"}
    assert org_from_claims(claims, "fallback") == "o1"
    assert project_from_claims(claims, "fallback") == "p1"


def test_org_organization_id():
    assert org_from_claims({"organization_id": "acme"}, "x") == "acme"


def test_markings_default():
    assert markings_from_claims({}) == ["public"]
    assert markings_from_claims({"markings": "secret"}) == ["secret"]
