import datetime as dt
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func, or_, text
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.auth.services import check_unique, register_user, validate_complexity
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
    OrderItem,
)
from app.sponsor.services import update_sponsor_organization
from app.models.enums import RoleType, PasswordChangeType, DriverStatus, DriverApplicationStatus, OrderStatus
from werkzeug.security import generate_password_hash


PLATFORM_FEE_RATE = Decimal('0.01')
MONEY_QUANTIZER = Decimal('0.01')


def format_money(value: Decimal | int | float | None) -> str:
    amount = Decimal(str(value or 0)).quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)
    return f'{amount:.2f}'


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
            .select_from(Order)
            .join(Order.organization)
            .join(Order.driver)
            .join(Driver.user)
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
    sponsor_id: int | None = None,
):
    if detail:
        query = (
            db.session.query(
                User.username.label('driver_username'),
                Order.points.label('amount'),
                Order.create_time.label('sale_time'),
                SponsorOrganization.name.label('sponsor_name'),
            )
            .select_from(Order)
            .join(Order.driver)
            .join(Driver.user)
            .join(Order.organization)
        )

        query = _apply_driver_search(query, search)
        query = _apply_order_date_range(query, start_date, end_date)

        if sponsor_id:
            query = query.filter(Order.organization_id == sponsor_id)

        return query.order_by(
            User.username.asc(),
            Order.create_time.desc()
        ).all()

    query = (
        db.session.query(
            User.username.label('driver_username'),
            func.count(Order.order_id).label('sale_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .select_from(Order)
        .join(Order.driver)
        .join(Driver.user)
    )

    if search:
        query = query.filter(User.username.ilike(f"%{search}%"))

    return query.group_by(
        User.username
    ).order_by(
        User.username.asc()
    ).all()


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
        .select_from(Order)
        .join(Order.driver)
        .join(Driver.user)
        .filter(Order.create_time >= start_dt, Order.create_time < end_dt)
    )
    query = _apply_driver_search(query, search)
    return query.group_by(User.username).order_by(User.username.asc()).all()


def _display_user_name(user: User) -> str:
    name_parts = []
    for raw_part in [user.first_name, user.last_name]:
        clean_part = (raw_part or '').strip()
        if clean_part and clean_part.lower() != 'none':
            name_parts.append(clean_part)

    display_name = ' '.join(name_parts).strip()
    if display_name:
        return display_name
    return user.username


def _money(value: Decimal | int | float | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def get_invoice_report(
    *,
    sponsor_id: int | None,
    start_date: dt.date,
    end_date: dt.date,
    search: str = '',
) -> list[dict]:
    start_dt = dt.datetime.combine(start_date, dt.time.min)
    end_dt = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min)

    query = (
        Order.query.options(
            joinedload(Order.organization),
            joinedload(Order.driver).joinedload(Driver.user),
            joinedload(Order.order_items).joinedload(OrderItem.catalog_item),
        )
        .filter(
            Order.order_status.in_([OrderStatus.PENDING, OrderStatus.COMPLETED]),
            Order.create_time >= start_dt,
            Order.create_time < end_dt,
        )
        .order_by(Order.organization_id.asc(), Order.create_time.asc(), Order.order_id.asc())
    )

    if sponsor_id is not None:
        query = query.filter(Order.organization_id == sponsor_id)

    query = _apply_driver_search(query.join(Order.driver).join(Driver.user), search)

    invoices_by_sponsor: dict[int, dict] = {}
    for order in query.all():
        organization = order.organization
        if not organization:
            continue

        invoice = invoices_by_sponsor.setdefault(
            organization.organization_id,
            {
                'sponsor': organization,
                'start_date': start_date,
                'end_date': end_date,
                'invoice_date': dt.date.today(),
                'driver_rows': {},
                'detail_rows': [],
                'total_purchase_amount': Decimal('0.00'),
                'total_purchase_count': 0,
                'total_fee_due': Decimal('0.00'),
            },
        )

        point_value = organization.point_value or Decimal('0.01')
        purchase_amount = _money(Decimal(order.points) * Decimal(point_value))
        fee_amount = _money(purchase_amount * PLATFORM_FEE_RATE)
        driver_user = order.driver.user
        driver_key = order.driver_id
        driver_row = invoice['driver_rows'].setdefault(
            driver_key,
            {
                'driver_name': _display_user_name(driver_user),
                'driver_username': driver_user.username,
                'purchase_count': 0,
                'total_points': 0,
                'total_purchase_amount': Decimal('0.00'),
                'fee_generated': Decimal('0.00'),
            },
        )
        driver_row['purchase_count'] += 1
        driver_row['total_points'] += order.points
        driver_row['total_purchase_amount'] = _money(
            driver_row['total_purchase_amount'] + purchase_amount
        )
        driver_row['fee_generated'] = _money(driver_row['fee_generated'] + fee_amount)

        invoice['total_purchase_count'] += 1
        invoice['total_purchase_amount'] = _money(
            invoice['total_purchase_amount'] + purchase_amount
        )
        invoice['total_fee_due'] = _money(invoice['total_fee_due'] + fee_amount)

        if order.order_items:
            for item in order.order_items:
                line_amount = _money(Decimal(item.price) * Decimal(item.quantity) * Decimal(point_value))
                invoice['detail_rows'].append(
                    {
                        'order_id': order.order_id,
                        'order_status': order.order_status.value.title(),
                        'purchase_date': order.create_time,
                        'driver_name': _display_user_name(driver_user),
                        'driver_username': driver_user.username,
                        'product_name': item.catalog_item.product_name if item.catalog_item else 'Unknown product',
                        'quantity': item.quantity,
                        'purchase_amount': line_amount,
                        'fee_amount': _money(line_amount * PLATFORM_FEE_RATE),
                    }
                )
        else:
            invoice['detail_rows'].append(
                {
                    'order_id': order.order_id,
                    'order_status': order.order_status.value.title(),
                    'purchase_date': order.create_time,
                    'driver_name': _display_user_name(driver_user),
                    'driver_username': driver_user.username,
                    'product_name': 'Order total',
                    'quantity': 1,
                    'purchase_amount': purchase_amount,
                    'fee_amount': fee_amount,
                }
            )

    invoices = list(invoices_by_sponsor.values())
    for invoice in invoices:
        invoice['driver_rows'] = sorted(
            invoice['driver_rows'].values(),
            key=lambda row: (row['driver_name'].lower(), row['driver_username'].lower()),
        )

    return sorted(invoices, key=lambda invoice: invoice['sponsor'].name.lower())


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


def get_all_drivers(username: str = ''):
    clean_username = (username or '').strip()

    query = db.session.query(User).filter(User.role_type == RoleType.DRIVER)
    if clean_username:
        query = query.filter(User.username.ilike(f'%{clean_username}%'))

    return query.order_by(User.username.asc()).all()


def get_all_drivers_for_impersonation(username: str = ''):
    clean_username = (username or '').strip()

    query = (
        db.session.query(User)
        .join(User.driver)
        .options(joinedload(User.driver).joinedload(Driver.sponsorships))
        .filter(
            User.role_type == RoleType.DRIVER,
            User.is_user_active.is_(True),
            User.is_login_locked.is_(False),
        )
    )
    if clean_username:
        query = query.filter(User.username.ilike(f'%{clean_username}%'))

    return query.order_by(User.username.asc()).all()


def get_driver_for_impersonation(user_id: int) -> User:
    user = (
        db.session.query(User)
        .join(User.driver)
        .options(joinedload(User.driver).joinedload(Driver.sponsorships))
        .filter(
            User.user_id == user_id,
            User.role_type == RoleType.DRIVER,
            User.is_user_active.is_(True),
            User.is_login_locked.is_(False),
        )
        .first()
    )
    if user is None:
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


def get_all_sponsor_users_for_impersonation(username: str = ''):
    clean_username = (username or '').strip()

    query = (
        db.session.query(User)
        .join(User.sponsor_user)
        .options(joinedload(User.sponsor_user).joinedload(SponsorUser.organization))
        .filter(
            User.role_type == RoleType.SPONSOR,
            User.is_user_active.is_(True),
            User.is_login_locked.is_(False),
        )
    )
    if clean_username:
        query = query.filter(User.username.ilike(f'%{clean_username}%'))

    return query.order_by(User.username.asc()).all()


def get_sponsor_user_for_impersonation(user_id: int) -> User:
    user = (
        db.session.query(User)
        .join(User.sponsor_user)
        .options(joinedload(User.sponsor_user).joinedload(SponsorUser.organization))
        .filter(
            User.user_id == user_id,
            User.role_type == RoleType.SPONSOR,
            User.is_user_active.is_(True),
            User.is_login_locked.is_(False),
        )
        .first()
    )
    if user is None:
        raise ValueError('Sponsor user is not available for impersonation')
    return user


def create_sponsor_account(
    username: str,
    email: str,
    sponsor_organization_id: int | None,
    new_sponsor_organization_name: str,
    password: str,
    confpass: str,
) -> User:
    clean_username = (username or '').strip()
    clean_email = (email or '').strip()
    clean_org_name = (new_sponsor_organization_name or '').strip()

    if not clean_username:
        raise ValueError('Username is required')
    if not password:
        raise ValueError('Password is required')
    if not clean_email:
        raise ValueError('Email is required')

    valid, msg = validate_complexity(password, confpass)
    if not valid:
        raise ValueError(msg)

    valid, msg = check_unique(clean_username, clean_email)
    if not valid:
        raise ValueError(msg)

    if sponsor_organization_id and clean_org_name:
        raise ValueError('Choose an existing sponsor organization or enter a new one, not both')

    organization_id = None
    if sponsor_organization_id:
        organization = SponsorOrganization.query.get(sponsor_organization_id)
        if organization is None:
            raise ValueError('Selected sponsor organization was not found')
        organization_id = organization.organization_id
    elif clean_org_name:
        organization = SponsorOrganization(name=clean_org_name, point_value=0.01)
        db.session.add(organization)
        db.session.flush()
        organization_id = organization.organization_id
    else:
        raise ValueError('Sponsor organization is required for sponsor users')

    user = User(
        username=clean_username,
        password=generate_password_hash(password),
        role_type=RoleType.SPONSOR,
        email=clean_email,
        first_name='',
        last_name='',
    )
    db.session.add(user)
    db.session.flush()

    sponsor_user = SponsorUser(
        user_id=user.user_id,
        organization_id=organization_id,
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


def get_all_audit_logs(*, event_type=None, start_date=None, end_date=None, organization_id=None):
    query = """
        SELECT 
            a.username,
            a.event_type,
            a.detail,
            a.event_time,
            a.organization_id,
            o.name AS organization_name
        FROM audit_log a
        LEFT JOIN sponsor_organization o
            ON a.organization_id = o.organization_id
        WHERE 1=1
    """

    params = {}

    if event_type:
        query += " AND a.event_type COLLATE utf8mb4_unicode_ci = :event_type"
        params["event_type"] = event_type

    if start_date:
        query += " AND a.event_time >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND a.event_time < :end_date"   # note: < because we added +1 day
        params["end_date"] = end_date

    if organization_id:
        query += " AND a.organization_id = :org_id"
        params["org_id"] = organization_id

    query += " ORDER BY a.event_time DESC"

    rows = db.session.execute(text(query), params).fetchall()

    return [{
        "username": row[0],
        "event_type": row[1],
        "detail": row[2],
        "event_time": row[3],
        "organization_name": row[5] or "None"
    } for row in rows]


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
