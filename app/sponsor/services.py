from decimal import Decimal, InvalidOperation
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import SponsorOrganization, User, SponsorUser, RoleType
from app.auth.services import validate_complexity


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


def create_sponsor_user(username: str, password: str, email: str, organization: SponsorOrganization):
    if not organization:
        raise ValueError('Organization is required')
    username = username.strip().lower()
    email = email.strip().lower()
    if not username:
        raise ValueError('Username is required')
    if not password:
        raise ValueError('Password is required')
    if not email:
        raise ValueError('Email is required')

    existing_username = User.query.filter_by(username=username).first()
    if existing_username:
        raise ValueError('Username is already in use')

    existing_email = User.query.filter_by(email=email).first()
    if existing_email:
        raise ValueError('Email is already in use')

    valid_password, password_msg = validate_complexity(password)
    if not valid_password:
        raise ValueError(password_msg)

    user = User(
        username=username,
        password=generate_password_hash(password),
        email=email,
        role_type=RoleType.SPONSOR,
    )
    db.session.add(user)
    db.session.flush()

    sponsor_user = SponsorUser(
        user=user,
        organization=organization,
    )
    db.session.add(sponsor_user)
    db.session.commit()
    return user
