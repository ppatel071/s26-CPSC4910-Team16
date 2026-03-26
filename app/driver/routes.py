from flask import render_template, request, redirect, url_for, flash, session, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from typing import Tuple
from functools import wraps
from app.catalog_api.utils import get_catalog_products_for_organization
from app.extensions import db
from app.driver import driver_bp
from app.models import (
    Driver,
    DriverApplication,
    DriverSponsorship,
    Order,
    PointTransaction,
    SponsorOrganization,
    User,
    Notification,
    OrderItem,
)
from app.models.enums import (
    DriverApplicationStatus,
    OrderStatus,
    DriverStatus,
    NotificationCategory,
    RoleType
)

ACTIVE_SPONSORSHIP_SESSION_KEY = "active_driver_sponsorship_id"


# This is needed to ensure only drivers can access driver pages
def driver_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role_type != RoleType.DRIVER:
            abort(403)
        return f(*args, **kwargs)

    return wrapper


# This is just a helper
def _get_active_sponsorships_for_driver(driver_id: int) -> list[DriverSponsorship]:
    return (
        DriverSponsorship.query
        .options(joinedload(DriverSponsorship.organization))
        .filter_by(driver_id=driver_id, status=DriverStatus.ACTIVE)
        .all()
    )


# This is needed bc of RC#2 where a driver can belong to multiple sponsors
def _resolve_active_sponsorship(
    driver_id: int,
) -> Tuple[list[DriverSponsorship], DriverSponsorship | None]:
    sponsorships = _get_active_sponsorships_for_driver(driver_id)
    if not sponsorships:
        session.pop(ACTIVE_SPONSORSHIP_SESSION_KEY, None)
        return sponsorships, None

    requested_id = session.get(ACTIVE_SPONSORSHIP_SESSION_KEY)
    active_sponsorship = next(
        (s for s in sponsorships if s.driver_sponsorship_id == requested_id),
        None,
    )

    if active_sponsorship is None:
        sponsorships.sort(
            key=lambda s: (
                s.organization.name.lower() if s.organization else "",
                s.driver_sponsorship_id,
            )
        )
        active_sponsorship = sponsorships[0]
        session[ACTIVE_SPONSORSHIP_SESSION_KEY] = active_sponsorship.driver_sponsorship_id

    return sponsorships, active_sponsorship


# This gets orgs that the driver is not apart of
def _get_available_organizations(driver_id: int) -> list[SponsorOrganization]:
    active_sponsorship_orgs = (
        db.session.query(DriverSponsorship.organization_id)
        .filter(
            DriverSponsorship.driver_id == driver_id,
            DriverSponsorship.status == DriverStatus.ACTIVE,
        )
    )
    pending_application_orgs = (
        db.session.query(DriverApplication.organization_id)
        .filter(
            DriverApplication.driver_id == driver_id,
            DriverApplication.status == DriverApplicationStatus.PENDING,
        )
    )

    return (
        SponsorOrganization.query
        .filter(~SponsorOrganization.organization_id.in_(active_sponsorship_orgs))
        .filter(~SponsorOrganization.organization_id.in_(pending_application_orgs))
        .order_by(SponsorOrganization.name.asc())
        .all()
    )


# This injects sponsorship information into the templates automatically
@driver_bp.context_processor
def inject_driver_context():
    driver = getattr(current_user, "driver", None) if current_user.is_authenticated else None
    if not driver:
        return {"driver_sponsorships": [], "active_sponsorship": None}

    sponsorships, active_sponsorship = _resolve_active_sponsorship(driver.driver_id)
    return {
        "driver_sponsorships": sponsorships,
        "active_sponsorship": active_sponsorship,
    }


def _get_active_sponsorship(driver: Driver) -> DriverSponsorship | None:
    _, active_sponsorship = _resolve_active_sponsorship(driver.driver_id)
    return active_sponsorship


@driver_bp.route('/sponsorship/select', methods=['POST'])
@login_required
@driver_required
def set_active_sponsorship():
    driver = current_user.driver
    selected_id = request.form.get('driver_sponsorship_id', type=int)
    sponsorships, _ = _resolve_active_sponsorship(driver.driver_id)

    if selected_id and any(s.driver_sponsorship_id == selected_id for s in sponsorships):
        session[ACTIVE_SPONSORSHIP_SESSION_KEY] = selected_id

    next_url = request.form.get('next') or url_for('driver.dashboard')
    return redirect(next_url)


@driver_bp.route('/dashboard')
@login_required
@driver_required
def dashboard():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    active_sponsorship = _get_active_sponsorship(driver)
    available_organizations = _get_available_organizations(driver.driver_id)
    transactions = []
    organization = None
    sponsor_rules = None
    point_value = None

    if active_sponsorship:
        organization = active_sponsorship.organization
        sponsor_rules = organization.rules if organization else None
        point_value = organization.point_value if organization else None

        transactions = (
            PointTransaction.query
            .filter_by(
                driver_id=driver.driver_id,
                organization_id=active_sponsorship.organization_id,
            )
            .order_by(PointTransaction.create_time.desc())
            .all()
        )

    notifications_query = Notification.query.filter_by(driver_id=driver.driver_id)

    if not driver.point_change_alert:
        notifications_query = notifications_query.filter(
            Notification.category != NotificationCategory.POINT_CHANGE
        )

    if not driver.order_alert:
        notifications_query = notifications_query.filter(
            Notification.category != NotificationCategory.ORDER_PLACED
        )

    notifications = (
        notifications_query
        .order_by(Notification.create_time.desc())
        .all()
    )

    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()

    orders_query = Order.query.filter_by(driver_id=driver.driver_id)

    if search:
        orders_query = orders_query.filter(Order.order_id == int(search)) if search.isdigit() else orders_query.filter(db.false())

    if status:
        try:
            orders_query = orders_query.filter(Order.order_status == OrderStatus(status))
        except ValueError:
            orders_query = orders_query.filter(db.false())

    orders = orders_query.order_by(Order.create_time.desc()).all()

    return render_template(
        'driver/dashboard.html',
        active_sponsorship=active_sponsorship,
        available_organizations=available_organizations,
        organization=organization,
        transactions=transactions,
        sponsor_rules=sponsor_rules,
        point_value=point_value,
        orders=orders,
        notifications=notifications,
    )


@driver_bp.route('/catalog')
@login_required
@driver_required
def catalog():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    active_sponsorship = _get_active_sponsorship(driver)
    if not active_sponsorship or not active_sponsorship.organization:
        flash('You must have an active sponsorship to view the reward catalog.', 'error')
        return redirect(url_for('driver.dashboard'))

    organization = active_sponsorship.organization
    catalog_items = get_catalog_products_for_organization(organization.organization_id)

    return render_template(
        'driver/catalog.html',
        active_sponsorship=active_sponsorship,
        organization=organization,
        catalog_items=catalog_items,
    )


# ---------------------------------------------------------------------------
# Account settings
# ---------------------------------------------------------------------------

@driver_bp.route('/account', methods=['GET', 'POST'])
@login_required
@driver_required
def account_settings():
    user = current_user
    assert isinstance(user, User)

    if request.method == 'POST':
        user.first_name = request.form.get('first_name', '').strip()
        user.last_name = request.form.get('last_name', '').strip()
        user.email = request.form.get('email', '').strip()
        db.session.commit()
        flash('Account updated successfully.', 'success')
        return redirect(url_for('driver.account_settings'))

    return render_template('driver/account_settings.html', user=user)


# ---------------------------------------------------------------------------
# Driver application workflow
# ---------------------------------------------------------------------------

@driver_bp.route('/application')
@login_required
@driver_required
def application_form():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    available_organizations = _get_available_organizations(driver.driver_id)
    return render_template(
        'driver/application_form.html',
        available_organizations=available_organizations,
    )


@driver_bp.route('/application/submit', methods=['POST'])
@login_required
@driver_required
def submit_application():
    driver = current_user.driver
    organization_id = request.form.get('organization_id', type=int)

    if not organization_id:
        flash('Please select a sponsor organization.', 'error')
        return redirect(url_for('driver.application_form'))

    # Prevent duplicate pending applications to the same org
    existing = DriverApplication.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=organization_id,
        status=DriverApplicationStatus.PENDING,
    ).first()

    if existing:
        flash('You already have a pending application with this sponsor.', 'error')
        return redirect(url_for('driver.application_form'))

    application = DriverApplication(
        driver_id=driver.driver_id,
        organization_id=organization_id,
        status=DriverApplicationStatus.PENDING,
        full_name=request.form.get('full_name', '').strip() or None,
        phone_number=request.form.get('phone_number', '').strip() or None,
        address=request.form.get('address', '').strip() or None,
        experience=request.form.get('experience', '').strip() or None,
        reason=request.form.get('reason', '').strip() or None,
    )
    db.session.add(application)
    db.session.commit()
    flash('Application submitted successfully.', 'success')
    return redirect(url_for('driver.dashboard'))


# ---------------------------------------------------------------------------
# Redeem points / place order  (story 4048 / 18133)
# ---------------------------------------------------------------------------

@driver_bp.route('/redeem', methods=['POST'])
@login_required
@driver_required
def redeem_points():
    driver = current_user.driver
    sponsorship = _get_active_sponsorship(driver)

    if not sponsorship:
        flash('You must be affiliated with an active sponsor to redeem points.', 'error')
        return redirect(url_for('driver.dashboard'))

    catalog_id = request.form.get('catalog_id', type=int)
    if not catalog_id:
        flash('Invalid product selection.', 'error')
        return redirect(url_for('driver.dashboard'))

    # Find the catalog item and confirm it belongs to the driver's sponsor
    from app.models.organization import SponsorCatalogItem
    item = SponsorCatalogItem.query.filter_by(
        catalog_id=catalog_id,
        organization_id=sponsorship.organization_id,
    ).first()

    if not item:
        flash('Product not found in your sponsor\'s catalog.', 'error')
        return redirect(url_for('driver.dashboard'))

    cost = item.points_required

    if sponsorship.point_balance < cost:
        flash(f'Insufficient points. You need {cost} points but have {sponsorship.point_balance}.', 'error')
        return redirect(url_for('driver.dashboard'))

    # Deduct points from the sponsorship balance
    sponsorship.point_balance -= cost

    # Create the order
    order = Order(
        driver_id=driver.driver_id,
        organization_id=sponsorship.organization_id,
        placed_by_user_id=current_user.user_id,
        points=cost,
        order_status=OrderStatus.PENDING,
    )
    db.session.add(order)
    db.session.flush()  # get order_id before adding items

    order_item = OrderItem(
        order_id=order.order_id,
        catalog_id=item.catalog_id,
        quantity=1,
        price=cost,
    )
    db.session.add(order_item)

    # Create notification no matter preference to preserve data
    # Filtering based on preference is done during display
    notification = Notification(
        driver_id=driver.driver_id,
        issued_by_user_id=current_user.user_id,
        category=NotificationCategory.ORDER_PLACED,
        message=(
            f'Order placed: {item.product_name} for {cost} points. '
            f'Order #{order.order_id} is now pending.'
        ),
    )
    db.session.add(notification)

    db.session.commit()
    flash(f'Successfully redeemed {item.product_name} for {cost} points!', 'success')
    return redirect(url_for('driver.dashboard'))


# ---------------------------------------------------------------------------
# Toggle point-change alert  (story 4036 / 18132)
# ---------------------------------------------------------------------------

@driver_bp.route('/toggle-alert', methods=['POST'])
@login_required
@driver_required
def toggle_point_alert():
    driver = current_user.driver
    alert_type = request.form.get('alert_type', 'point')

    if alert_type == 'order':
        driver.order_alert = not driver.order_alert
        state = 'enabled' if driver.order_alert else 'disabled'
        flash(f'Order placement alerts {state}.', 'success')
    else:
        driver.point_change_alert = not driver.point_change_alert
        state = 'enabled' if driver.point_change_alert else 'disabled'
        flash(f'Point change alerts {state}.', 'success')

    db.session.commit()
    return redirect(url_for('driver.dashboard'))


# ---------------------------------------------------------------------------
# Cancel order
# ---------------------------------------------------------------------------

@driver_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
@driver_required
def cancel_order(order_id):
    driver = current_user.driver
    order = next((o for o in driver.orders if o.order_id == order_id), None)

    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('driver.dashboard'))

    if order.order_status == OrderStatus.CANCELLED:
        flash('Order is already cancelled.', 'error')
        return redirect(url_for('driver.dashboard'))

    if order.order_status == OrderStatus.COMPLETED:
        flash('Completed orders cannot be cancelled.', 'error')
        return redirect(url_for('driver.dashboard'))

    # Refund points back to the sponsorship balance
    sponsorship = _get_active_sponsorship(driver)
    if sponsorship and sponsorship.organization_id == order.organization_id:
        sponsorship.point_balance += order.points

    order.order_status = OrderStatus.CANCELLED
    db.session.commit()
    flash('Order cancelled and points refunded.', 'success')
    return redirect(url_for('driver.dashboard'))
