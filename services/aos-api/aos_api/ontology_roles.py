"""W1-17 · Ontology 角色体系。

四级角色（Owner/Editor/Viewer/Discoverer）+ 六种权限（元数据与数据分离）+
对象类型级授权。

详见 docs/palantier/20_tech/220tech_ontology-roles.md。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Role(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"
    DISCOVERER = "discoverer"


class Permission(str, Enum):
    READ_META = "read_meta"
    WRITE_META = "write_meta"
    READ_DATA = "read_data"
    WRITE_DATA = "write_data"
    DELETE_DATA = "delete_data"
    ADMIN = "admin"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: {
        Permission.READ_META, Permission.WRITE_META,
        Permission.READ_DATA, Permission.WRITE_DATA,
        Permission.DELETE_DATA, Permission.ADMIN,
    },
    Role.EDITOR: {
        Permission.READ_META, Permission.WRITE_META,
        Permission.READ_DATA, Permission.WRITE_DATA,
    },
    Role.VIEWER: {
        Permission.READ_META, Permission.READ_DATA,
    },
    Role.DISCOVERER: {
        Permission.READ_META,
    },
}


class RoleAssignment(BaseModel):
    object_type: str
    principal: str
    role: Role
    granted_at: str
    granted_by: str = ""


class OntologyRoleError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class OntologyRoleStore:
    def __init__(self) -> None:
        self._by_type: dict[str, dict[str, RoleAssignment]] = {}
        self._by_principal: dict[str, list[RoleAssignment]] = {}
        self._lock = threading.Lock()

    def assign(
        self, object_type: str, principal: str, role: Role, granted_by: str = ""
    ) -> RoleAssignment:
        if not object_type:
            raise OntologyRoleError("BAD_OBJECT_TYPE", "object_type 不能为空")
        if not principal:
            raise OntologyRoleError("BAD_PRINCIPAL", "principal 不能为空")
        if not isinstance(role, Role):
            raise OntologyRoleError("BAD_ROLE", f"未知 role {role!r}")
        with self._lock:
            type_map = self._by_type.setdefault(object_type, {})
            existing = type_map.get(principal)
            assignment = RoleAssignment(
                object_type=object_type,
                principal=principal,
                role=role,
                granted_at=_now(),
                granted_by=granted_by,
            )
            type_map[principal] = assignment
            plist = self._by_principal.setdefault(principal, [])
            if existing is None:
                plist.append(assignment)
            else:
                for i, a in enumerate(plist):
                    if a.object_type == object_type and a.principal == principal:
                        plist[i] = assignment
                        break
            return assignment

    def revoke(self, object_type: str, principal: str) -> bool:
        with self._lock:
            type_map = self._by_type.get(object_type)
            if type_map is None:
                return False
            if principal not in type_map:
                return False
            del type_map[principal]
            plist = self._by_principal.get(principal, [])
            self._by_principal[principal] = [
                a for a in plist if not (a.object_type == object_type and a.principal == principal)
            ]
            return True

    def get_roles(self, object_type: str) -> list[RoleAssignment]:
        type_map = self._by_type.get(object_type, {})
        return list(type_map.values())

    def get_assignments_for(self, principal: str) -> list[RoleAssignment]:
        return list(self._by_principal.get(principal, []))

    def check_permission(
        self, object_type: str, principal: str, permission: Permission
    ) -> bool:
        if not isinstance(permission, Permission):
            raise OntologyRoleError("BAD_PERMISSION", f"未知 permission {permission!r}")
        type_map = self._by_type.get(object_type, {})
        assignment = type_map.get(principal)
        if assignment is None:
            return False
        return permission in ROLE_PERMISSIONS[assignment.role]

    def list_principals(self, object_type: str) -> dict[str, str]:
        type_map = self._by_type.get(object_type, {})
        return {p: a.role.value for p, a in type_map.items()}

    def list_permissions(self) -> list[str]:
        return [p.value for p in Permission]


_store = OntologyRoleStore()


def get_store() -> OntologyRoleStore:
    return _store
