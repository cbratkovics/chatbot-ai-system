"""Permission and role management for authorization."""

from enum import Enum


class Permission(str, Enum):
    """System permissions."""

    # Chat permissions
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    CHAT_STREAM = "chat:stream"

    # Conversation permissions
    CONVERSATION_READ = "conversation:read"
    CONVERSATION_WRITE = "conversation:write"
    CONVERSATION_DELETE = "conversation:delete"

    # Tenant permissions
    TENANT_READ = "tenant:read"
    TENANT_WRITE = "tenant:write"
    TENANT_ADMIN = "tenant:admin"

    # User permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"

    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_METRICS = "system:metrics"
    SYSTEM_HEALTH = "system:health"

    # Cost permissions
    COST_READ = "cost:read"
    COST_EXPORT = "cost:export"

    # Cache permissions
    CACHE_READ = "cache:read"
    CACHE_INVALIDATE = "cache:invalidate"


class Role(str, Enum):
    """User roles with associated permissions."""

    USER = "user"
    PREMIUM_USER = "premium_user"
    TENANT_ADMIN = "tenant_admin"
    SYSTEM_ADMIN = "system_admin"
    VIEWER = "viewer"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    Role.VIEWER: {
        Permission.CHAT_READ,
        Permission.CONVERSATION_READ,
        Permission.SYSTEM_HEALTH,
    },
    Role.USER: {
        Permission.CHAT_READ,
        Permission.CHAT_WRITE,
        Permission.CHAT_STREAM,
        Permission.CONVERSATION_READ,
        Permission.CONVERSATION_WRITE,
        Permission.USER_READ,
        Permission.SYSTEM_HEALTH,
    },
    Role.PREMIUM_USER: {
        Permission.CHAT_READ,
        Permission.CHAT_WRITE,
        Permission.CHAT_STREAM,
        Permission.CONVERSATION_READ,
        Permission.CONVERSATION_WRITE,
        Permission.CONVERSATION_DELETE,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.COST_READ,
        Permission.CACHE_READ,
        Permission.SYSTEM_HEALTH,
        Permission.SYSTEM_METRICS,
    },
    Role.TENANT_ADMIN: {
        Permission.CHAT_READ,
        Permission.CHAT_WRITE,
        Permission.CHAT_STREAM,
        Permission.CONVERSATION_READ,
        Permission.CONVERSATION_WRITE,
        Permission.CONVERSATION_DELETE,
        Permission.TENANT_READ,
        Permission.TENANT_WRITE,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_DELETE,
        Permission.COST_READ,
        Permission.COST_EXPORT,
        Permission.CACHE_READ,
        Permission.CACHE_INVALIDATE,
        Permission.SYSTEM_HEALTH,
        Permission.SYSTEM_METRICS,
    },
    Role.SYSTEM_ADMIN: {
        # System admin has all permissions
        *[p for p in Permission]
    },
}


def get_role_permissions(role: Role) -> set[Permission]:
    """Get permissions for a role."""
    return ROLE_PERMISSIONS.get(role, set())


def check_permission(user_permissions: list[str], required_permission: Permission) -> bool:
    """Check if user has required permission."""
    return required_permission.value in user_permissions


def check_any_permission(
    user_permissions: list[str], required_permissions: list[Permission]
) -> bool:
    """Check if user has any of the required permissions."""
    user_perms_set = set(user_permissions)
    required_perms_set = {p.value for p in required_permissions}

    return bool(user_perms_set & required_perms_set)


def check_all_permissions(
    user_permissions: list[str], required_permissions: list[Permission]
) -> bool:
    """Check if user has all required permissions."""
    user_perms_set = set(user_permissions)
    required_perms_set = {p.value for p in required_permissions}

    return required_perms_set.issubset(user_perms_set)


def expand_roles_to_permissions(roles: list[str]) -> set[str]:
    """Expand roles to their associated permissions."""
    permissions = set()

    for role_str in roles:
        try:
            role = Role(role_str)
            role_permissions = get_role_permissions(role)
            permissions.update(p.value for p in role_permissions)
        except ValueError:
            # Invalid role, skip
            continue

    return permissions
