from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.driver import driver_bp
from app.models.users import User
from app.models.organization import SponsorOrganization
from app.models.enums import OrderStatus



@driver_bp.route('/dashboard')
@login_required
def dashboard():
    driver = current_user.driver

    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    orders = driver.orders if driver else []

    if search_query:
        orders = [o for o in orders if search_query.lower() in str(o.order_id).lower()]

    if status_filter:
        orders = [o for o in orders if o.order_status.value == status_filter]

    organizations = SponsorOrganization.query.all()
    transactions = driver.point_transactions if driver else []

    return render_template(
        'driver/dashboard.html',
        organizations=organizations,
        transactions=transactions,
        orders=orders
    )

@driver_bp.route('/application/submit', methods=['POST'])
@login_required
def submit_application():
    driver = current_user.driver

    return redirect(url_for('driver.dashboard'))

@driver_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account_settings():
    user: User = current_user

    if request.method == 'POST':
        user.first_name = request.form.get('first_name', '').strip()
        user.last_name = request.form.get('last_name', '').strip()
        user.email = request.form.get('email', '').strip()

        db.session.commit()
        return redirect(url_for('driver.account_settings'))

    return render_template('driver/account_settings.html', user=user)


@driver_bp.route('/application')
@login_required
def application_form():
    return render_template('driver/application_form.html')



@driver_bp.route('/redeem', methods=['POST'])
@login_required
def redeem_points():
    driver = current_user.driver
    points = int(request.form.get('points', 0))

    if driver and points > 0 and driver.point_bal >= points:
        driver.point_bal -= points
        db.session.commit()

    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/toggle-alert', methods=['POST'])
@login_required
def toggle_point_alert():
    driver = current_user.driver

    if driver:
        driver.point_change_alert = not driver.point_change_alert
        db.session.commit()

    return redirect(url_for('driver.dashboard'))



@driver_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    driver = current_user.driver

    if driver:
        order = next((o for o in driver.orders if o.order_id == order_id), None)

        if order and order.order_status != OrderStatus.CANCELLED:
            order.order_status = OrderStatus.CANCELLED
            db.session.commit()

    return redirect(url_for('driver.dashboard'))



@driver_bp.route('/apply/<int:organization_id>', methods=['POST'])
@login_required
def apply_to_organization(organization_id):
    driver = current_user.driver

    if driver:
        driver.organization_id = organization_id
        db.session.commit()

    return redirect(url_for('driver.dashboard'))


@driver_bp.route('/request-change/<int:organization_id>', methods=['POST'])
@login_required
def request_sponsor_change(organization_id):
    driver = current_user.driver

    if driver:
        driver.organization_id = organization_id
        db.session.commit()

    return redirect(url_for('driver.dashboard'))