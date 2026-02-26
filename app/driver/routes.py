from flask import render_template, redirect, url_for
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


@driver_bp.route('/cancel/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)

    if order.status != OrderStatus.CANCELLED:
        order.status = OrderStatus.CANCELLED
        current_user.driver.point_bal += order.point_cost
        db.session.commit()

    return redirect(url_for('driver.dashboard'))