from decimal import Decimal, InvalidOperation
from typing import Tuple, List
from sqlalchemy.orm import joinedload
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
    DriverApplicationStatus,
    PointTransaction,
    Notification,
    NotificationCategory,
)
from app.auth.services import register_user


def normalize_profile_fields(
    username: str, email: str | None, first_name: str, last_name: str
) -> tuple[str, str | None, str, str]:
    clean_username = (username or "").strip()
    clean_email = (email or "").strip().lower()
    clean_first = (first_name or "").strip()
    clean_last = (last_name or "").strip()

    if clean_email == "":
        clean_email = None

    return clean_username, clean_email, clean_first, clean_last


def validate_and_apply_user_profile_updates(
    user: User, username: str, email: str | None, first_name: str, last_name: str
) -> User:
    clean_username, clean_email, clean_first, clean_last = normalize_profile_fields(
        username, email, first_name, last_name
    )

    if not clean_username:
        raise ValueError("Username is required.")

    existing_username = User.query.filter(
        User.username == clean_username, User.user_id != user.user_id
    ).first()
    if existing_username:
        raise ValueError("Username is already in use.")

    if clean_email:
        existing_email = User.query.filter(
            User.email == clean_email, User.user_id != user.user_id
        ).first()
        if existing_email:
            raise ValueError("Email is already in use.")

    user.username = clean_username
    user.email = clean_email
    user.first_name = clean_first
    user.last_name = clean_last
    return user


def update_sponsor_organization(
    organization: SponsorOrganization, name: str, point_value: str
) -> SponsorOrganization:

    if not organization:
        raise ValueError("No sponsor organization found for this user")

    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Organization name is required")

    try:
        parsed_point_value = Decimal(point_value)
    except (InvalidOperation, TypeError):
        raise ValueError("Point value must be a valid number")

    if parsed_point_value < 0:
        raise ValueError("Point value must be non-negative")

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
    organization: SponsorOrganization,
) -> User:

    user = register_user(
        username, password, RoleType.SPONSOR, email, first_name, last_name
    )

    sponsor_user = SponsorUser(
        user=user,
        organization=organization,
    )
    db.session.add(sponsor_user)
    db.session.commit()
    return user


def get_driver_applications(
    org_id: int,
) -> Tuple[List[DriverApplication] | None, List[DriverApplication] | None]:
    pending_applications = (
        DriverApplication.query.filter_by(
            organization_id=org_id,
            status=DriverApplicationStatus.PENDING,
        )
        .order_by(DriverApplication.create_time.desc())
        .all()
    )
    historic_applications = (
        DriverApplication.query.filter(
            DriverApplication.organization_id == org_id,
            DriverApplication.status != DriverApplicationStatus.PENDING,
        )
        .order_by(DriverApplication.create_time.desc())
        .all()
    )
    return (pending_applications, historic_applications)


def approve_driver_for_sponsor(driver: Driver, organization_id: int):
    if not driver:
        raise ValueError("Driver does not exist")
    sponsorship = DriverSponsorship.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=organization_id,
    ).first()

    if sponsorship is None:
        sponsorship = DriverSponsorship(
            driver_id=driver.driver_id,
            organization_id=organization_id,
            status=DriverStatus.ACTIVE,
        )
        db.session.add(sponsorship)

    sponsorship.status = DriverStatus.ACTIVE
    return sponsorship


def get_organization_drivers(organization_id: int) -> List[DriverSponsorship]:
    sponsorships = (
        DriverSponsorship.query.join(DriverSponsorship.driver)
        .options(
            joinedload(DriverSponsorship.driver).joinedload(Driver.user),
            joinedload(DriverSponsorship.organization),
        )
        .filter(DriverSponsorship.organization_id == organization_id)
        .all()
    )
    return sorted(
        sponsorships,
        key=lambda sponsorship: (
            sponsorship.driver.user.first_name or "",
            sponsorship.driver.user.last_name or "",
            sponsorship.driver.user.username or "",
        ),
    )


def get_organization_driver_sponsorship(
    organization_id: int, driver_sponsorship_id: int
) -> DriverSponsorship:
    sponsorship = db.session.get(
        DriverSponsorship,
        driver_sponsorship_id,
        options=(
            joinedload(DriverSponsorship.driver).joinedload(Driver.user),
            joinedload(DriverSponsorship.organization),
        ),
    )
    if not sponsorship or sponsorship.organization_id != organization_id:
        raise ValueError("Driver was not found for your organization.")
    return sponsorship


def update_driver_profile_for_sponsor(
    organization_id: int,
    driver_sponsorship_id: int,
    username: str,
    email: str | None,
    first_name: str,
    last_name: str,
) -> DriverSponsorship:
    sponsorship = get_organization_driver_sponsorship(
        organization_id, driver_sponsorship_id
    )
    validate_and_apply_user_profile_updates(
        sponsorship.driver.user, username, email, first_name, last_name
    )
    db.session.commit()
    return sponsorship


def set_driver_status_for_sponsor(
    organization_id: int,
    driver_sponsorship_id: int,
    new_status: DriverStatus,
    acting_user,
) -> DriverSponsorship:
    sponsorship = get_organization_driver_sponsorship(
        organization_id, driver_sponsorship_id
    )
    sponsorship.status = new_status

    if new_status == DriverStatus.DROPPED:
        driver_user = sponsorship.driver.user
        actor_name = acting_user.username if acting_user else "A sponsor user"
        message = (
            f"{actor_name} dropped you from sponsor organization "
            f'"{sponsorship.organization.name}".'
        )
        db.session.add(
            Notification(
                driver_id=sponsorship.driver_id,
                issued_by_user_id=acting_user.user_id if acting_user else None,
                category=NotificationCategory.DRIVER_DROPPED,
                message=message,
            )
        )
        if driver_user:
            db.session.add(driver_user)

    db.session.commit()
    return sponsorship


def adjust_driver_points_for_sponsor(
    organization_id: int,
    driver_sponsorship_id: int,
    point_change: int,
    reason: str,
    acting_user: User,
) -> DriverSponsorship:
    driver_sponsorship = get_organization_driver_sponsorship(
        organization_id, driver_sponsorship_id
    )
    clean_reason = (reason or "").strip()

    if driver_sponsorship.status != DriverStatus.ACTIVE:
        raise ValueError("Only active drivers can have points adjusted.")

    if point_change == 0:
        raise ValueError("Point change must be a non-zero whole number.")

    if len(clean_reason) < 3:
        raise ValueError("Reason must be at least 3 characters long.")

    if len(clean_reason) > 255:
        raise ValueError("Reason must be 255 characters or fewer.")

    updated_balance = driver_sponsorship.point_balance + point_change
    if updated_balance < 0:
        raise ValueError("Point change would make the driver balance negative.")

    driver_sponsorship.point_balance = updated_balance

    db.session.add(
        PointTransaction(
            driver_id=driver_sponsorship.driver_id,
            organization_id=organization_id,
            performed_by_user_id=acting_user.user_id,
            point_change=point_change,
            reason=clean_reason,
        )
    )

    actor_name = acting_user.username if acting_user else "A sponsor user"
    direction = "added to" if point_change > 0 else "deducted from"
    message = (
        f"{actor_name} {abs(point_change)} points {direction} your balance"
        f' for "{clean_reason}". Your new balance is {updated_balance} points.'
    )
    db.session.add(
        Notification(
            driver_id=driver_sponsorship.driver_id,
            issued_by_user_id=acting_user.user_id if acting_user else None,
            category=NotificationCategory.POINT_CHANGE,
            message=message,
            is_read=False,
        )
    )

    db.session.commit()
    return driver_sponsorship
