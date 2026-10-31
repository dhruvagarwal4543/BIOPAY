from rest_framework.permissions import BasePermission


def role_of(user):
    """Role comes from server-side records only. Staff outranks a linked account."""
    if not (user and user.is_authenticated and user.is_active):
        return None
    if user.is_staff:
        return "admin"
    if hasattr(user, "customer"):
        return "customer"
    if hasattr(user, "merchant"):
        return "merchant"
    return None


class HasRole(BasePermission):
    role = None

    def has_permission(self, request, view):
        user = request.user
        if self.role == "admin":
            return role_of(user) == "admin"
        return bool(role_of(user)) and hasattr(user, self.role)


class IsCustomer(HasRole):
    role = "customer"


class IsMerchant(HasRole):
    role = "merchant"


class IsAdmin(HasRole):
    role = "admin"
