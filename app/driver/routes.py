from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.driver import driver_bp
from app.models.users import User, DriverSponsorship
from app.models.organization import SponsorOrganization
from app.models.enums import OrderStatus, DriverStatus, NotificationCategory
from app.models.system import Notification
from app.models.driver_workflow import Order, OrderItem, DriverApplication
from app.models.enums import DriverApplicationStatus
from app.models.products import Product



def _get_active_sponsorship(driver):
    """Return the single ACTIVE DriverSponsorship for this driver, or None."""
    if driver is None:
        return None
    return next(
        (s for s in driver.sponsorships if s.status == DriverStatus.ACTIVE),
        None
    )




@driver_bp.route('/dashboard')
@login_required
def dashboard():
    driver = current_user.driver
    sponsorship = _get_active_sponsorship(driver)
    organization = sponsorship.organization if sponsorship else None

    # -- Point history with reason  (story 4035 / 18130) --------------------
    transactions = driver.point_transactions if driver else []
    # Filter to only this sponsor's transactions if we have an active sponsor
    if sponsorship:
        transactions = [
            t for t in transactions
            if t.organization_id == sponsorship.organization_id
        ]
    # Sort newest first
    transactions = sorted(transactions, key=lambda t: t.create_time, reverse=True)

    # -- Catalog products for the driver's sponsor  (story 4048 / 18133) ----
    catalog_items = organization.catalog_items if organization else []

    # -- Sponsor rules  (story 4078 / 18136) ---------------------------------
    sponsor_rules = organization.rules if organization else None
    point_value = organization.point_value if organization else None

    # -- Orders with search / filter ----------------------------------------
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    orders = driver.orders if driver else []

    if search_query:
        orders = [o for o in orders if search_query.lower() in str(o.order_id).lower()]
    if status_filter:
        orders = [o for o in orders if o.order_status.value == status_filter]
    orders = sorted(orders, key=lambda o: o.create_time, reverse=True)

    # -- Notifications (story 4036 / 18132) ----------------------------------
    notifications = sorted(
        driver.notifications if driver else [],
        key=lambda n: n.create_time,
        reverse=True
    )

    # -- All orgs available to apply to -------------------------------------
    organizations = SponsorOrganization.query.all()

    return render_template(
        'driver/dashboard.html',
        sponsorship=sponsorship,
        organization=organization,
        transactions=transactions,
        catalog_items=catalog_items,
        sponsor_rules=sponsor_rules,
        point_value=point_value,
        orders=orders,
        notifications=notifications,
        organizations=organizations,
    )


# ---------------------------------------------------------------------------
# Account settings
# ---------------------------------------------------------------------------

@driver_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account_settings():
    user: User = current_user

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
def application_form():
    organizations = SponsorOrganization.query.all()
    return render_template('driver/application_form.html', organizations=organizations)


@driver_bp.route('/application/submit', methods=['POST'])
@login_required
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

    # Notify the driver if their alert preference is on  (story 4036 / 18132)
    if driver.order_alert:
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