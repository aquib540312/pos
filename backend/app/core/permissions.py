"""Coarse resource:action permission strings used throughout the system.

Keeping these as a flat registry (rather than scattering literal strings
across routers) makes it possible to enumerate all permissions for role
management UI and to catch typos at import time.
"""


class Perm:
    USERS_MANAGE = "users:manage"
    ROLES_MANAGE = "roles:manage"

    CATALOG_VIEW = "catalog:view"
    CATALOG_MANAGE = "catalog:manage"

    INVENTORY_VIEW = "inventory:view"
    INVENTORY_ADJUST = "inventory:adjust"

    PARTY_MANAGE = "party:manage"

    PURCHASE_CREATE = "purchase:create"
    PURCHASE_RECEIVE = "purchase:receive"

    SALES_CREATE = "sales:create"
    SALES_RETURN = "sales:return"
    QUOTATION_CREATE = "quotation:create"

    SHIFT_MANAGE = "shift:manage"

    REPORTS_VIEW = "reports:view"

    ORG_MANAGE = "org:manage"

    SYNC_MANAGE = "sync:manage"

    ALL_PERMISSIONS = [
        USERS_MANAGE, ROLES_MANAGE, CATALOG_VIEW, CATALOG_MANAGE,
        INVENTORY_VIEW, INVENTORY_ADJUST, PARTY_MANAGE, PURCHASE_CREATE,
        PURCHASE_RECEIVE, SALES_CREATE, SALES_RETURN, QUOTATION_CREATE,
        SHIFT_MANAGE, REPORTS_VIEW, ORG_MANAGE, SYNC_MANAGE,
    ]


# Default role -> permission bundles used by the seed script.
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": Perm.ALL_PERMISSIONS,
    "manager": [
        Perm.CATALOG_VIEW, Perm.CATALOG_MANAGE, Perm.INVENTORY_VIEW,
        Perm.INVENTORY_ADJUST, Perm.PARTY_MANAGE, Perm.PURCHASE_CREATE,
        Perm.PURCHASE_RECEIVE, Perm.SALES_CREATE, Perm.SALES_RETURN,
        Perm.QUOTATION_CREATE, Perm.SHIFT_MANAGE, Perm.REPORTS_VIEW,
        Perm.SYNC_MANAGE,
    ],
    "cashier": [
        Perm.CATALOG_VIEW, Perm.INVENTORY_VIEW, Perm.PARTY_MANAGE,
        Perm.SALES_CREATE, Perm.SALES_RETURN, Perm.QUOTATION_CREATE,
        Perm.SHIFT_MANAGE,
    ],
}
