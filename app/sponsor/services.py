from decimal import Decimal, InvalidOperation
from app.extensions import db
from app.models import (
    SponsorOrganization,
    SponsorUser,
    User,
    RoleType,
    Driver,
    DriverSponsorship,
    DriverStatus,
    DriverApplication,
    DriverApplicationStatus
)
from app.auth.services import register_user
from typing import Tuple, List


def update_sponsor_organization(
        organization: SponsorOrganization,
        name: str,
        point_value: str) -> SponsorOrganization:

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


def create_sponsor_user(
        username: str,
        password: str,
        email: str,
        first_name: str,
        last_name: str,
        organization: SponsorOrganization) -> User:

    user = register_user(
        username,
        password,
        RoleType.SPONSOR,
        email,
        first_name,
        last_name
    )

    sponsor_user = SponsorUser(
        user=user,
        organization=organization,
    )
    db.session.add(sponsor_user)
    db.session.commit()
    return user


def get_driver_applications(org_id: int) -> Tuple[List[DriverApplication] | None, List[DriverApplication] | None]:
    pending_applications = (
        DriverApplication.query
        .filter_by(
            organization_id=org_id,
            status=DriverApplicationStatus.PENDING,
        )
        .order_by(DriverApplication.create_time.desc())
        .all()
    )
    historic_applications = (
        DriverApplication.query
        .filter(
            DriverApplication.organization_id == org_id,
            DriverApplication.status != DriverApplicationStatus.PENDING,
        )
        .order_by(DriverApplication.create_time.desc())
        .all()
    )
    return (pending_applications, historic_applications)


def approve_driver_for_sponsor(driver: Driver, organization_id: int):
    if not driver:
        raise ValueError('Driver does not exist')
    sponsorship = DriverSponsorship.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=organization_id,
    ).first()

    if sponsorship is None:
        sponsorship = DriverSponsorship(
            driver_id=driver.driver_id,
            organization_id=organization_id,
            status=DriverStatus.ACTIVE
        )
        db.session.add(sponsorship)

    sponsorship.status = DriverStatus.ACTIVE
    return sponsorship
