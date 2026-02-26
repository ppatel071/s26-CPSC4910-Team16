import datetime as dt
from sqlalchemy import func
from app.extensions import db
from app.models import SponsorOrganization, User, Order, LoginAttempt
from app.sponsor.services import update_sponsor_organization
from app.models.enums import RoleType


def get_all_sponsors():
    return SponsorOrganization.query.order_by(SponsorOrganization.name.asc()).all()


def get_sponsor_by_id(organization_id: int) -> SponsorOrganization:
    org = SponsorOrganization.query.get(organization_id)
    if org is None:
        raise ValueError('No organization exists for that id')
    return org


def admin_update_sponsor(organization_id: int, name: str, point_value: str) -> SponsorOrganization:
    org = get_sponsor_by_id(organization_id)
    return update_sponsor_organization(org, name, point_value)


def get_sales_by_sponsor(detail: bool):
    if detail:
        return (
            db.session.query(
                SponsorOrganization.name.label('sponsor_name'),
                Order.points.label('amount'),
                Order.create_time.label('sale_time'),
                User.username.label('driver_username'),
            )
            .join(Order.organization)
            .join(Order.placed_by_user)
            .order_by(SponsorOrganization.name.asc(), Order.create_time.desc())
            .all()
        )

    return (
        db.session.query(
            SponsorOrganization.name.label('sponsor_name'),
            func.count(Order.order_id).label('sale_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.organization)
        .group_by(SponsorOrganization.name)
        .order_by(SponsorOrganization.name.asc())
        .all()
    )


def get_sales_by_driver(detail: bool):
    if detail:
        return (
            db.session.query(
                User.username.label('driver_username'),
                Order.points.label('amount'),
                Order.create_time.label('sale_time'),
                SponsorOrganization.name.label('sponsor_name'),
            )
            .join(Order.placed_by_user)
            .join(Order.organization)
            .order_by(User.username.asc(), Order.create_time.desc())
            .all()
        )

    return (
        db.session.query(
            User.username.label('driver_username'),
            func.count(Order.order_id).label('sale_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.placed_by_user)
        .group_by(User.username)
        .order_by(User.username.asc())
        .all()
    )


def get_driver_purchase_summary(start_date: dt.date, end_date: dt.date):
    start_dt = dt.datetime.combine(start_date, dt.time.min)
    end_dt = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min)

    return (
        db.session.query(
            User.username.label('driver_username'),
            func.count(Order.order_id).label('purchase_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.placed_by_user)
        .filter(Order.create_time >= start_dt, Order.create_time < end_dt)
        .group_by(User.username)
        .order_by(User.username.asc())
        .all()
    )

def get_admin_users_with_logins():
    return (
        db.session.query(User)
        .join(LoginAttempt, LoginAttempt.user_id == User.user_id)
        .filter(User.role_type == RoleType.ADMIN, LoginAttempt.success.is_(True))
        .distinct()
        .order_by(User.username.asc())
        .all()
    )


def get_all_admin_users():
    return (
        db.session.query(User)
        .filter(User.role_type == RoleType.ADMIN)
        .order_by(User.username.asc())
        .all()
    )


def get_all_drivers():
    return (
        db.session.query(User)
        .filter(User.role_type == RoleType.DRIVER)
        .order_by(User.username.asc())
        .all()
    )


def get_driver_by_id(user_id: int) -> User:
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('No user exists for that id')
    if user.role_type != RoleType.DRIVER:
        raise ValueError('User is not a driver')
    return user


def admin_update_driver_user(
    user_id: int,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
):
    user = get_driver_by_id(user_id)

    clean_username = (username or '').strip()
    clean_email = (email or '').strip().lower()
    clean_first = (first_name or '').strip()
    clean_last = (last_name or '').strip()

    if not clean_username:
        raise ValueError('Username is required')
    if not clean_first:
        raise ValueError('First name is required')
    if not clean_last:
        raise ValueError('Last name is required')

    existing_username = (
        User.query.filter(User.username == clean_username, User.user_id != user.user_id).first()
    )
    if existing_username:
        raise ValueError('Username is already in use')

    if clean_email == '':
        clean_email = None
    if clean_email:
        existing_email = (
            User.query.filter(User.email == clean_email, User.user_id != user.user_id).first()
        )
        if existing_email:
            raise ValueError('Email is already in use')
    user.username = clean_username
    user.email = clean_email
    user.first_name = clean_first
    user.last_name = clean_last
    db.session.commit()
    return user
