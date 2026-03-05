from flask import render_template, redirect, url_for, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.driver_workflow import DriverApplication, Order
from app.models.organization import SponsorOrganization
from app.models.enums import DriverApplicationStatus, OrderStatus
from app.driver import driver_bp
import datetime as dt


@driver_bp.route('/dashboard')
@login_required
def dashboard():
    driver = current_user.driver

    organizations = SponsorOrganization.query.all()
    transactions = driver.point_transactions if driver else []
    orders = driver.orders if driver else []

    return render_template(
        'driver/dashboard.html',
        organizations=organizations,
        transactions=transactions,
        orders=orders
    )


@driver_bp.route('/redeem', methods=['POST'])
@login_required
def redeem_points():
    driver = current_user.driver
    amount = int(request.form.get("points"))

    if amount <= 0:
        return redirect(url_for('driver.dashboard'))

    if driver.point_bal < amount:
        return redirect(url_for('driver.dashboard'))

    order = Order(
        driver_id=driver.driver_id,
        points=amount,
        order_status=OrderStatus.PENDING,
        create_time=dt.datetime.utcnow()
    )

    driver.point_bal -= amount

    db.session.add(order)
    db.session.commit()

    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/cancel/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)

    if order.order_status != OrderStatus.CANCELLED:
        order.order_status = OrderStatus.CANCELLED
        current_user.driver.point_bal += order.points
        db.session.commit()

    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/toggle-point-alert', methods=['POST'])
@login_required
def toggle_point_alert():
    driver = current_user.driver
    driver.point_change_alert = not driver.point_change_alert
    db.session.commit()
    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/apply/<int:organization_id>', methods=['POST'])
@login_required
def apply_to_organization(organization_id):
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


@driver_bp.route('/request-change/<int:organization_id>', methods=['POST'])
@login_required
def request_sponsor_change(organization_id):
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