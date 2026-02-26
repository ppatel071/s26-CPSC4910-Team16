from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.organization import SponsorOrganization
from app.models.driver_workflow import DriverApplication
from app.models.enums import DriverApplicationStatus
from app.driver import driver_bp


@driver_bp.route('/dashboard')
@login_required
def dashboard():
    organizations = SponsorOrganization.query.all()
    transactions = current_user.driver.point_transactions
    return render_template(
        'driver/dashboard.html',
        organizations=organizations,
        transactions=transactions
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
        status=DriverApplicationStatus.PENDING
    )

    db.session.add(application)
    db.session.commit()

    return redirect(url_for('driver.dashboard'))