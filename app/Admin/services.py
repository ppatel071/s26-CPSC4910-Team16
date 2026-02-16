from app.models.users import SponsorOrganization

def get_all_sponsors():
    return SponsorOrganization.query.order_by(SponsorOrganization.name.asc()).all()
