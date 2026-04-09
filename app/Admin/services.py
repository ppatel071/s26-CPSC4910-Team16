import datetime as dt
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.auth.services import register_user, validate_complexity
from app.models import (
    SponsorOrganization,
    SponsorUser,
    User,
    Order,
    LoginAttempt,
    PasswordChange,
    Driver,
    DriverApplication,
    DriverSponsorship,
    PointTransaction,
    Notification,
)
from app.sponsor.services import update_sponsor_organization
from app.models.enums import RoleType, PasswordChangeType, DriverStatus, DriverApplicationStatus
from werkzeug.security import generate_password_hash


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


def _apply_driver_search(query, search: str):
    clean_search = (search or '').strip()
    if not clean_search:
        return query

    search_term = f'%{clean_search}%'
    return query.filter(
        or_(
            User.username.ilike(search_term),
            User.first_name.ilike(search_term),
            User.last_name.ilike(search_term),
        )
    )


def _apply_sponsor_search(query, search: str):
    clean_search = (search or '').strip()
    if not clean_search:
        return query

    return query.filter(SponsorOrganization.name.ilike(f'%{clean_search}%'))


def _apply_order_date_range(query, start_date: dt.date | None, end_date: dt.date | None):
    if start_date is not None:
        start_dt = dt.datetime.combine(start_date, dt.time.min)
        query = query.filter(Order.create_time >= start_dt)

    if end_date is not None:
        end_dt = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min)
        query = query.filter(Order.create_time < end_dt)

    return query


def get_sales_by_sponsor(
    detail: bool,
    *,
    search: str = '',
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
):
    if detail:
        query = (
            db.session.query(
                SponsorOrganization.name.label('sponsor_name'),
                Order.points.label('amount'),
                Order.create_time.label('sale_time'),
                User.username.label('driver_username'),
            )
            .join(Order.organization)
            .join(Order.placed_by_user)
        )
        query = _apply_driver_search(query, search)
        query = _apply_order_date_range(query, start_date, end_date)
        return query.order_by(SponsorOrganization.name.asc(), Order.create_time.desc()).all()

    query = (
        db.session.query(
            SponsorOrganization.name.label('sponsor_name'),
            func.count(Order.order_id).label('sale_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.organization)
    )
    query = _apply_sponsor_search(query, search)
    return (
        query.group_by(SponsorOrganization.name)
        .order_by(SponsorOrganization.name.asc())
        .all()
    )


def get_sales_by_driver(
    detail: bool,
    *,
    search: str = '',
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
):
    if detail:
        query = (
            db.session.query(
                User.username.label('driver_username'),
                Order.points.label('amount'),
                Order.create_time.label('sale_time'),
                SponsorOrganization.name.label('sponsor_name'),
            )
            .join(Order.placed_by_user)
            .join(Order.organization)
        )
        query = _apply_driver_search(query, search)
        query = _apply_order_date_range(query, start_date, end_date)
        return query.order_by(User.username.asc(), Order.create_time.desc()).all()

    query = (
        db.session.query(
            User.username.label('driver_username'),
            func.count(Order.order_id).label('sale_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.placed_by_user)
    )
    query = _apply_driver_search(query, search)
    return query.group_by(User.username).order_by(User.username.asc()).all()


def get_driver_purchase_summary(
    start_date: dt.date,
    end_date: dt.date,
    *,
    search: str = '',
):
    start_dt = dt.datetime.combine(start_date, dt.time.min)
    end_dt = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min)

    query = (
        db.session.query(
            User.username.label('driver_username'),
            func.count(Order.order_id).label('purchase_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.placed_by_user)
        .filter(Order.create_time >= start_dt, Order.create_time < end_dt)
    )
    query = _apply_driver_search(query, search)
    return query.group_by(User.username).order_by(User.username.asc()).all()


def get_admin_users_with_logins():
    return (
        db.session.query(User)
        .join(LoginAttempt, LoginAttempt.user_id == User.user_id)
        .filter(User.role_type == RoleType.ADMIN, LoginAttempt.success.is_(True))
        .distinct()
        .order_by(User.username.asc())
        .all()
    )


def get_all_admin_users(username: str = ''):
    clean_username = (username or '').strip()

    query = db.session.query(User).filter(User.role_type == RoleType.ADMIN)
    if clean_username:
        query = query.filter(User.username.ilike(f'%{clean_username}%'))

    return query.order_by(User.username.asc()).all()


def get_all_drivers():
    return (
        db.session.query(User)
        .filter(User.role_type == RoleType.DRIVER)
        .order_by(User.username.asc())
        .all()
    )

def get_all_drivers_for_impersonation():
    return (
        db.session.query(User)
        .join(User.driver)
        .options(joinedload(User.driver).joinedload(Driver.sponsorships))
        .order_by(User.username.asc())
        .all()
    )


def get_driver_for_impersonation(user_id: int) -> User:
    user = (
        db.session.query(User)
        .join(User.driver)
        .options(joinedload(User.driver).joinedload(Driver.sponsorships))
        .filter(User.user_id == user_id)
        .first()
    )
    if user is None or user.role_type != RoleType.DRIVER:
        raise ValueError('Driver is not available for impersonation')
    return user


def get_driver_by_id(user_id: int) -> User:
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('No user exists for that id')
    if user.role_type != RoleType.DRIVER:
        raise ValueError('User is not a driver')
    return user


def count_active_sponsorships(driver: Driver) -> int:
    return sum(
        1 for sponsorship in driver.sponsorships if sponsorship.status == DriverStatus.ACTIVE
    )


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


def create_driver_account(
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    confpass: str,
) -> User:
    clean_username = (username or '').strip()
    clean_email = (email or '').strip().lower()
    clean_first = (first_name or '').strip()
    clean_last = (last_name or '').strip()

    if not clean_first:
        raise ValueError('First name is required')
    if not clean_last:
        raise ValueError('Last name is required')

    return register_user(
        username=clean_username,
        password=password,
        role=RoleType.DRIVER,
        email=clean_email,
        first_name=clean_first,
        last_name=clean_last,
        confpass=confpass,
    )


def admin_update_own_profile(
    user: User,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
):
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


def get_all_sponsor_users(username: str = ''):
    clean_username = (username or '').strip()

    query = (
        db.session.query(
            SponsorOrganization.name.label('sponsor_name'),
            User.username.label('username'),
            User.email.label('email'),
            User.first_name.label('first_name'),
            User.last_name.label('last_name'),
        )
        .select_from(SponsorUser)
        .join(
            SponsorOrganization,
            SponsorUser.organization_id == SponsorOrganization.organization_id,
        )
        .join(User, SponsorUser.user_id == User.user_id)
    )
    if clean_username:
        query = query.filter(User.username.ilike(f'%{clean_username}%'))

    return query.order_by(SponsorOrganization.name.asc(), User.username.asc()).all()


def create_sponsor_account(
    username: str,
    email: str,
    sponsor_organization_id: int | None,
    new_sponsor_organization_name: str,
    password: str,
) -> User:
    clean_username = (username or '').strip()
    clean_email = (email or '').strip()

    user = register_user(
        username=clean_username,
        password=password,
        role=RoleType.SPONSOR,
        email=clean_email,
        first_name='',
        last_name='',
    )

    sponsor_user = SponsorUser(
        user_id=user.user_id,
        organization_id=resolve_sponsor_organization_for_role_assignment(
            sponsor_organization_id=sponsor_organization_id,
            new_sponsor_organization_name=new_sponsor_organization_name,
        ),
    )
    db.session.add(sponsor_user)
    db.session.commit()

    return user


def get_users_for_removal_page(
    admin_username: str = '',
    sponsor_username: str = '',
    driver_username: str = '',
):
    clean_admin_username = (admin_username or '').strip()
    clean_sponsor_username = (sponsor_username or '').strip()
    clean_driver_username = (driver_username or '').strip()

    admin_query = db.session.query(User).filter(User.role_type == RoleType.ADMIN)
    if clean_admin_username:
        admin_query = admin_query.filter(User.username.ilike(f'%{clean_admin_username}%'))
    admin_users = admin_query.order_by(User.username.asc()).all()

    sponsor_query = (
        db.session.query(
            User.user_id.label('user_id'),
            User.username.label('username'),
            User.email.label('email'),
            User.is_user_active.label('is_user_active'),
            User.is_login_locked.label('is_login_locked'),
            SponsorOrganization.name.label('sponsor_name'),
        )
        .select_from(SponsorUser)
        .join(User, SponsorUser.user_id == User.user_id)
        .join(SponsorOrganization, SponsorUser.organization_id == SponsorOrganization.organization_id)
    )
    if clean_sponsor_username:
        sponsor_query = sponsor_query.filter(User.username.ilike(f'%{clean_sponsor_username}%'))
    sponsor_users = sponsor_query.order_by(SponsorOrganization.name.asc(), User.username.asc()).all()

    driver_query = db.session.query(User).filter(User.role_type == RoleType.DRIVER)
    if clean_driver_username:
        driver_query = driver_query.filter(User.username.ilike(f'%{clean_driver_username}%'))
    driver_users = driver_query.order_by(User.username.asc()).all()

    return admin_users, sponsor_users, driver_users


def deactivate_driver_user(user_id: int):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('Driver user not found')
    if user.role_type != RoleType.DRIVER:
        raise ValueError('Selected user is not a driver')
    if not user.is_user_active:
        raise ValueError('Driver user is already deactivated')

    user.is_user_active = False
    db.session.commit()
    return user


def reactivate_driver_user(user_id: int):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('Driver user not found')
    if user.role_type != RoleType.DRIVER:
        raise ValueError('Selected user is not a driver')
    if user.is_user_active:
        raise ValueError('Driver user is already active')

    user.is_user_active = True
    db.session.commit()
    return user


def deactivate_admin_user(user_id: int):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('Admin user not found')
    if user.role_type != RoleType.ADMIN:
        raise ValueError('Selected user is not an admin')
    if not user.is_user_active:
        raise ValueError('Admin user is already deactivated')

    user.is_user_active = False
    db.session.commit()
    return user


def reactivate_admin_user(user_id: int):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('Admin user not found')
    if user.role_type != RoleType.ADMIN:
        raise ValueError('Selected user is not an admin')
    if user.is_user_active:
        raise ValueError('Admin user is already active')

    user.is_user_active = True
    db.session.commit()
    return user


def deactivate_sponsor_user(user_id: int):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('Sponsor user not found')
    if user.role_type != RoleType.SPONSOR:
        raise ValueError('Selected user is not a sponsor user')
    if not user.is_user_active:
        raise ValueError('Sponsor user is already deactivated')

    user.is_user_active = False
    db.session.commit()
    return user


def reactivate_sponsor_user(user_id: int):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('Sponsor user not found')
    if user.role_type != RoleType.SPONSOR:
        raise ValueError('Selected user is not a sponsor user')
    if user.is_user_active:
        raise ValueError('Sponsor user is already active')

    user.is_user_active = True
    db.session.commit()
    return user


def unlock_user_login(user_id: int):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('User not found')
    if not user.is_user_active:
        raise ValueError('Deactivated users cannot be unlocked from login lock here')
    if not user.is_login_locked:
        raise ValueError('User is not locked for failed login attempts')

    user.is_login_locked = False
    user.failed_login_attempts = 0
    user.locked_at = None
    db.session.commit()
    return user


def get_all_system_users(username: str = ''):
    clean_username = (username or '').strip()

    query = db.session.query(User)
    if clean_username:
        query = query.filter(User.username.ilike(f'%{clean_username}%'))

    return query.order_by(User.role_type.asc(), User.username.asc()).all()


def user_has_driver_dependencies(user: User) -> bool:
    if not user.driver:
        return False

    driver_id = user.driver.driver_id
    return any(
        (
            DriverApplication.query.filter_by(driver_id=driver_id).first(),
            DriverSponsorship.query.filter_by(driver_id=driver_id).first(),
            PointTransaction.query.filter_by(driver_id=driver_id).first(),
            Notification.query.filter_by(driver_id=driver_id).first(),
            Order.query.filter_by(driver_id=driver_id).first(),
        )
    )


def reassign_user_role(user_id: int, new_role_raw: str, sponsor_organization_id: int | None):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('User not found')
    if not user.is_user_active:
        raise ValueError('Deactivated users cannot have their roles changed')
    if user.is_login_locked:
        raise ValueError('Locked users cannot have their roles changed')

    try:
        new_role = RoleType(new_role_raw)
    except ValueError as exc:
        raise ValueError('Invalid role selected') from exc

    if new_role == user.role_type:
        if new_role == RoleType.SPONSOR:
            if sponsor_organization_id is None:
                raise ValueError('Sponsor organization is required for sponsor users')
            sponsor_user = user.sponsor_user
            if sponsor_user is None:
                sponsor_user = SponsorUser(user_id=user.user_id, organization_id=sponsor_organization_id)
                db.session.add(sponsor_user)
            else:
                sponsor_user.organization_id = sponsor_organization_id
            db.session.commit()
            return user
        raise ValueError('User already has that role')

    if user.role_type == RoleType.DRIVER and user_has_driver_dependencies(user):
        raise ValueError(
            'This driver cannot be reassigned because they already have driver history.'
        )

    if user.role_type == RoleType.DRIVER and user.driver:
        db.session.delete(user.driver)

    if user.role_type == RoleType.SPONSOR and user.sponsor_user:
        db.session.delete(user.sponsor_user)
        db.session.flush()

    user.role_type = new_role

    if new_role == RoleType.DRIVER:
        db.session.add(Driver(user_id=user.user_id))
    elif new_role == RoleType.SPONSOR:
        if sponsor_organization_id is None:
            raise ValueError('Sponsor organization is required for sponsor users')
        db.session.add(
            SponsorUser(user_id=user.user_id, organization_id=sponsor_organization_id)
        )

    db.session.commit()
    return user


def resolve_sponsor_organization_for_role_assignment(
    sponsor_organization_id: int | None,
    new_sponsor_organization_name: str,
) -> int:
    clean_name = (new_sponsor_organization_name or '').strip()

    if sponsor_organization_id and clean_name:
        raise ValueError('Choose an existing sponsor organization or enter a new one, not both')

    if sponsor_organization_id:
        organization = SponsorOrganization.query.get(sponsor_organization_id)
        if organization is None:
            raise ValueError('Selected sponsor organization was not found')
        return organization.organization_id

    if clean_name:
        organization = SponsorOrganization(name=clean_name, point_value=0.01)
        db.session.add(organization)
        db.session.flush()
        return organization.organization_id

    raise ValueError('Sponsor organization is required for sponsor users')


def get_admin_password_reset_audit_entries(
    username: str = '',
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
):
    clean_username = (username or '').strip()

    query = (
        db.session.query(
            PasswordChange.pass_id.label('pass_id'),
            PasswordChange.change_time.label('change_time'),
            User.user_id.label('user_id'),
            User.username.label('username'),
            User.email.label('email'),
            User.role_type.label('role_type'),
        )
        .join(User, PasswordChange.user_id == User.user_id)
        .filter(PasswordChange.change_type == PasswordChangeType.ADMIN_RESET)
        .order_by(PasswordChange.change_time.desc(), PasswordChange.pass_id.desc())
    )

    if clean_username:
        query = query.filter(User.username.ilike(f'%{clean_username}%'))
    if start_date is not None:
        start_dt = dt.datetime.combine(start_date, dt.time.min)
        query = query.filter(PasswordChange.change_time >= start_dt)
    if end_date is not None:
        end_dt = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min)
        query = query.filter(PasswordChange.change_time < end_dt)

    return query.all()


def admin_reset_user_password(user_id: int, new_password: str, confirm_password: str):
    user = User.query.get(user_id)
    if user is None:
        raise ValueError('User not found')

    valid, msg = validate_complexity(new_password, confirm_password)
    if not valid:
        raise ValueError(msg)

    user.password = generate_password_hash(new_password)
    user.failed_login_attempts = 0
    user.is_login_locked = False
    user.must_notify_password_reset = True
    user.locked_at = None

    db.session.add(
        PasswordChange(
            user_id=user.user_id,
            change_type=PasswordChangeType.ADMIN_RESET,
        )
    )
    db.session.commit()
    return user

def get_available_organizations(driver_id: int) -> list[SponsorOrganization]:
    active_sponsorship_orgs = db.session.query(DriverSponsorship.organization_id).filter(
        DriverSponsorship.driver_id == driver_id,
        DriverSponsorship.status == DriverStatus.ACTIVE,
    )
    pending_application_orgs = db.session.query(DriverApplication.organization_id).filter(
        DriverApplication.driver_id == driver_id,
        DriverApplication.status == DriverApplicationStatus.PENDING,
    )

    return (
        SponsorOrganization.query.filter(
            ~SponsorOrganization.organization_id.in_(active_sponsorship_orgs)
        )
        .filter(~SponsorOrganization.organization_id.in_(pending_application_orgs))
        .order_by(SponsorOrganization.name.asc())
        .all()
    )
