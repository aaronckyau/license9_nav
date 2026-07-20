from .models import OrganizationSettings


def organization(request):
    if not request.user.is_authenticated:
        return {"organization_settings": None}
    return {"organization_settings": OrganizationSettings.load()}
