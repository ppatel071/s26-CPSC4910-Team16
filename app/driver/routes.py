from flask import render_template, redirect, request, session, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.driver import driver_bp
import datetime as dt
from typing import List, Tuple
from functools import wraps
from app.models import (
    DriverApplication,
    Order,
    PointTransaction,
    SponsorOrganization,
    DriverSponsorship,
    Driver
)
from app.models.enums import DriverApplicationStatus, DriverStatus, OrderStatus, RoleType

ACTIVE_SPONSORSHIP_SESSION_KEY = 'active_driver_sponsorship_id'


def driver_required(f):
    '''Simple wrapper to ensure driver role for driver routes'''
    @wraps(f)
    def wrapper(*args, **kwargs):
        # impersonation logic may work well here
        if current_user.role_type != RoleType.DRIVER:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def _get_active_sponsorships_for_driver(driver_id: int) -> List[DriverSponsorship]:
    return (
        DriverSponsorship.query
        .options(joinedload(DriverSponsorship.organization))
        .filter_by(driver_id=driver_id, status=DriverStatus.ACTIVE)
        .all()
    )


def _resolve_active_sponsorship(driver_id: int) -> Tuple[List[DriverSponsorship], DriverSponsorship | None]:
    sponsorships = _get_active_sponsorships_for_driver(driver_id)
    if not sponsorships:
        session.pop(ACTIVE_SPONSORSHIP_SESSION_KEY, None)
        return sponsorships, None

    requested_id = session.get(ACTIVE_SPONSORSHIP_SESSION_KEY)
    active_sponsorship = next(
        (s for s in sponsorships if s.driver_sponsorship_id == requested_id),
        None
    )

    if active_sponsorship is None:
        sponsorships.sort(
            key=lambda s: (s.organization.name.lower() if s.organization else '', s.driver_sponsorship_id)
        )
        active_sponsorship = sponsorships[0]
        session[ACTIVE_SPONSORSHIP_SESSION_KEY] = active_sponsorship.driver_sponsorship_id

    return sponsorships, active_sponsorship


@driver_bp.context_processor
def inject_driver_context():
    # Inject driver_sponsorships and active_sponsorship automatically into templates
    driver = getattr(current_user, 'driver', None) if current_user.is_authenticated else None
    if not driver:
        return {'driver_sponsorships': [], 'active_sponsorship': None}
    sponsorships, active_sponsorship = _resolve_active_sponsorship(driver.driver_id)
    return {
        'driver_sponsorships': sponsorships,
        'active_sponsorship': active_sponsorship
    }


@driver_bp.route('/dashboard')
@login_required
@driver_required
def dashboard():
    driver = current_user.driver
    assert isinstance(driver, Driver)
    transactions = []
    orders = []
    active_sponsorship = None
    sponsorships, active_sponsorship = _resolve_active_sponsorship(driver.driver_id)
    sponsored_organization_ids = {s.organization_id for s in sponsorships}

    if sponsored_organization_ids:
        available_organizations = SponsorOrganization.query.filter(
            ~SponsorOrganization.organization_id.in_(sponsored_organization_ids)
        ).all()
    else:
        available_organizations = SponsorOrganization.query.all()
    # Might be nice to filter out pending applications from available_organizations

    if active_sponsorship:
        transactions = (
            PointTransaction.query
            .filter_by(
                driver_id=driver.driver_id,
                organization_id=active_sponsorship.organization_id
            )
            .order_by(PointTransaction.create_time.desc())
            .all()
        )
        orders = (
            Order.query
            .filter_by(
                driver_id=driver.driver_id,
                organization_id=active_sponsorship.organization_id
            )
            .order_by(Order.create_time.desc())
            .all()
        )
    breadcrumbs = [
        ("Driver Dashboard", None)
    ]

    return render_template(
        'driver/dashboard.html',
        available_organizations=available_organizations,
        transactions=transactions,
        orders=orders,
        breadcrumbs=breadcrumbs
    )


@driver_bp.route('/set-active-sponsorship', methods=['POST'])
@login_required
@driver_required
def set_active_sponsorship():
    driver = current_user.driver
    if not driver:
        return redirect(url_for('driver.dashboard'))

    sponsorship_id_str = (request.form.get('driver_sponsorship_id') or '').strip()
    next_url = request.form.get('next')
    if not next_url:
        next_url = url_for('driver.dashboard')

    sponsorships = _get_active_sponsorships_for_driver(driver.driver_id)

    if not sponsorships:
        session.pop(ACTIVE_SPONSORSHIP_SESSION_KEY, None)
        return redirect(next_url)

    try:
        sponsorship_id = int(sponsorship_id_str)
    except ValueError:
        return redirect(next_url)

    if any(s.driver_sponsorship_id == sponsorship_id for s in sponsorships):
        session[ACTIVE_SPONSORSHIP_SESSION_KEY] = sponsorship_id

    return redirect(next_url)


@driver_bp.route('/redeem', methods=['POST'])
@login_required
@driver_required
def redeem_points():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    _, active_sponsorship = _resolve_active_sponsorship(driver.driver_id)
    if not active_sponsorship:
        return redirect(url_for('driver.dashboard'))

    # TODO: Implement point redemption
    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/cancel/<int:order_id>', methods=['POST'])
@login_required
@driver_required
def cancel_order(order_id):
    driver = current_user.driver
    assert isinstance(driver, Driver)

    order = Order.query.filter_by(order_id=order_id, driver_id=driver.driver_id).first()
    if not order or order.order_status == OrderStatus.CANCELLED:
        return redirect(url_for('driver.dashboard'))

    sponsorship = DriverSponsorship.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=order.organization_id,
        status=DriverStatus.ACTIVE
    ).first()
    if not sponsorship:
        return redirect(url_for('driver.dashboard'))

    order.order_status = OrderStatus.CANCELLED
    sponsorship.point_balance += order.points
    db.session.add(PointTransaction(
        driver_id=driver.driver_id,
        organization_id=order.organization_id,
        performed_by_user_id=current_user.user_id,
        point_change=order.points,
        reason=f'Order cancellation refund #{order.order_id}'
    ))
    db.session.commit()

    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/toggle-point-alert', methods=['POST'])
@login_required
@driver_required
def toggle_point_alert():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    driver.point_change_alert = not driver.point_change_alert
    db.session.commit()
    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/apply/<int:organization_id>', methods=['POST'])
@login_required
@driver_required
def apply_to_organization(organization_id):
    driver = current_user.driver
    assert isinstance(driver, Driver)

    existing = DriverApplication.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=organization_id
    ).first()

    if existing:
        return redirect(url_for('driver.dashboard'))

    application = DriverApplication(
        driver_id=driver.driver_id,
        organization_id=organization_id,
        status=DriverApplicationStatus.PENDING,
        create_time=dt.datetime.utcnow()
    )

    db.session.add(application)
    db.session.commit()

    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/request-change/<int:organization_id>', methods=['POST'])
@login_required
def request_sponsor_change(organization_id):
    # With the new requirements, is this route still needed?
    driver = current_user.driver

    existing = DriverApplication.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=organization_id
    ).first()

    if existing:
        return redirect(url_for('driver.dashboard'))

    application = DriverApplication(
        driver_id=driver.driver_id,
        organization_id=organization_id,
        status=DriverApplicationStatus.PENDING,
        create_time=dt.datetime.utcnow()
    )

    db.session.add(application)
    db.session.commit()

    return redirect(url_for('driver.dashboard'))
