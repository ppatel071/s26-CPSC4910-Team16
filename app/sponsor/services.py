from decimal import Decimal, InvalidOperation
from app.extensions import db
from app.models.users import SponsorOrganization



def update_sponsor_organization(organization: SponsorOrganization, name: str, point_value: str) -> SponsorOrganization:
    if not organization:
        raise ValueError('No sponsor organization found for this user')

    clean_name = name.strip()
    if not clean_name:
        raise ValueError('Organization name is required')

    try:
        parsed_point_value = Decimal(point_value)
    except (InvalidOperation, TypeError):
        raise ValueError('Point value must be a valid number')

    if parsed_point_value < 0:
        raise ValueError('Point value must be non-negative')

    organization.name = clean_name
    organization.point_value = parsed_point_value
    db.session.commit()
    return organization
