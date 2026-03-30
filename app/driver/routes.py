from functools import wraps

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.impersonation import (
    clear_sponsor_driver_impersonation,
    get_impersonator_sponsor_user_id,
)
from app.catalog_api.utils import get_catalog_products_for_organization
from app.driver import driver_bp
from app.driver.services import (
    ACTIVE_SPONSORSHIP_SESSION_KEY,
    build_impersonation_banner_context,
    cancel_driver_order,
    filter_driver_orders,
    get_active_sponsorship,
    get_available_organizations,
    get_driver_dashboard_data,
    get_sponsor_user_for_impersonation_return,
    is_driver_impersonated,
    resolve_active_sponsorship,
    redeem_catalog_item_for_driver,
    submit_driver_application,
    toggle_driver_alert,
    update_driver_account,
)
from app.models import Driver, User
from app.models.enums import RoleType


def driver_required(f):
    '''This is a simple wrapper to ensure driver users have the driver role'''
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role_type != RoleType.DRIVER:
            abort(403)
        return f(*args, **kwargs)

    return wrapper


@driver_bp.context_processor
def inject_driver_context():
    '''This injects variables into templates needed for impersonation and RC#2'''
    driver = getattr(current_user, "driver", None) if current_user.is_authenticated else None
    if not driver:
        return {
            "driver_sponsorships": [],
            "active_sponsorship": None,
            "is_impersonating_driver": False,
            "impersonation_banner_message": None,
            "impersonation_exit_endpoint": None,
            "impersonation_exit_label": None,
        }

    sponsorships, active_sponsorship = resolve_active_sponsorship(driver.driver_id)
    return {
        "driver_sponsorships": sponsorships,
        "active_sponsorship": active_sponsorship,
        **build_impersonation_banner_context(),
    }


def _redirect_impersonated_driver_to_dashboard():
    flash(
        "Sponsor impersonation does not allow access to sponsor application tools.",
        "error",
    )
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/sponsorship/select", methods=["POST"])
@login_required
@driver_required
def set_active_sponsorship():
    driver = current_user.driver
    selected_id = request.form.get("driver_sponsorship_id", type=int)
    sponsorships, _ = resolve_active_sponsorship(driver.driver_id)

    if selected_id and any(s.driver_sponsorship_id == selected_id for s in sponsorships):
        session[ACTIVE_SPONSORSHIP_SESSION_KEY] = selected_id

    next_url = request.form.get("next") or url_for("driver.dashboard")
    return redirect(next_url)


@driver_bp.route("/dashboard")
@login_required
@driver_required
def dashboard():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    is_impersonating_driver = is_driver_impersonated()
    dashboard_data = get_driver_dashboard_data(
        driver,
        include_applications=not is_impersonating_driver,
    )
    dashboard_data["orders"] = filter_driver_orders(
        driver.driver_id,
        request.args.get("search", "").strip(),
        request.args.get("status", "").strip(),
    )

    return render_template(
        "driver/dashboard.html",
        is_impersonating_driver=is_impersonating_driver,
        **dashboard_data,
    )


@driver_bp.route("/catalog")
@login_required
@driver_required
def catalog():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    active_sponsorship = get_active_sponsorship(driver)
    if not active_sponsorship or not active_sponsorship.organization:
        flash("You must have an active sponsorship to view the reward catalog.", "error")
        return redirect(url_for("driver.dashboard"))

    organization = active_sponsorship.organization
    catalog_items = get_catalog_products_for_organization(organization.organization_id)

    return render_template(
        "driver/catalog.html",
        active_sponsorship=active_sponsorship,
        organization=organization,
        catalog_items=catalog_items,
    )


@driver_bp.route("/account", methods=["GET", "POST"])
@login_required
@driver_required
def account_settings():
    user = current_user
    assert isinstance(user, User)

    if request.method == "POST":
        update_driver_account(
            user,
            first_name=request.form.get("first_name", ""),
            last_name=request.form.get("last_name", ""),
            email=request.form.get("email", ""),
        )
        flash("Account updated successfully.", "success")
        return redirect(url_for("driver.account_settings"))

    return render_template("driver/account_settings.html", user=user)


@driver_bp.route("/application")
@login_required
@driver_required
def application_form():
    if is_driver_impersonated():
        return _redirect_impersonated_driver_to_dashboard()

    driver = current_user.driver
    assert isinstance(driver, Driver)

    return render_template(
        "driver/application_form.html",
        available_organizations=get_available_organizations(driver.driver_id),
    )


@driver_bp.route("/application/submit", methods=["POST"])
@login_required
@driver_required
def submit_application():
    if is_driver_impersonated():
        return _redirect_impersonated_driver_to_dashboard()

    driver = current_user.driver
    organization_id = request.form.get("organization_id", type=int)

    if not organization_id:
        flash("Please select a sponsor organization.", "error")
        return redirect(url_for("driver.application_form"))

    try:
        submit_driver_application(driver, organization_id, request.form)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("driver.application_form"))

    flash("Application submitted successfully.", "success")
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/redeem", methods=["POST"])
@login_required
@driver_required
def redeem_points():
    driver = current_user.driver
    catalog_id = request.form.get("catalog_id", type=int)
    acting_user_id = get_impersonator_sponsor_user_id() or current_user.user_id

    if not catalog_id:
        flash("Invalid product selection.", "error")
        return redirect(url_for("driver.dashboard"))

    try:
        message = redeem_catalog_item_for_driver(
            driver,
            acting_user_id=acting_user_id,
            catalog_id=catalog_id,
        )
    except (ValueError, LookupError, RuntimeError) as e:
        flash(str(e), "error")
        return redirect(url_for("driver.dashboard"))

    flash(message, "success")
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/toggle-alert", methods=["POST"])
@login_required
@driver_required
def toggle_point_alert():
    driver = current_user.driver
    message = toggle_driver_alert(driver, request.form.get("alert_type", "point"))
    flash(message, "success")
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
@driver_required
def cancel_order(order_id):
    driver = current_user.driver

    try:
        message = cancel_driver_order(driver, order_id)
    except (LookupError, ValueError) as e:
        flash(str(e), "error")
        return redirect(url_for("driver.dashboard"))

    flash(message, "success")
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/impersonation/stop", methods=["POST"])
@login_required
@driver_required
def stop_impersonation():
    sponsor_user_id = get_impersonator_sponsor_user_id()
    clear_sponsor_driver_impersonation()

    if sponsor_user_id is None:
        return redirect(url_for("driver.dashboard"))

    sponsor_user = get_sponsor_user_for_impersonation_return(sponsor_user_id)
    if sponsor_user is None:
        logout_user()
        flash(
            "The impersonation session ended, but the sponsor account could not be restored.",
            "error",
        )
        return redirect(url_for("auth.login"))

    login_user(sponsor_user)
    flash("Returned to the sponsor driver management page.", "success")
    return redirect(url_for("sponsor.driver_management"))
