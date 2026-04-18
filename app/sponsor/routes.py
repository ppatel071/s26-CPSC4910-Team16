import datetime as dt
from functools import wraps
from re import sub

import csv

from io import StringIO

from flask import abort, flash, redirect, render_template, request, url_for, Response
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.impersonation import (
    clear_admin_sponsor_impersonation,
    get_impersonator_admin_sponsor_user_id,
    start_sponsor_driver_impersonation,
)
from app.bulk_upload import build_text_stream, process_bulk_upload_stream
from app.catalog_api.utils import (
    CATALOG_PAGE_SIZE,
    browse_catalog_products,
    get_catalog_categories,
    get_catalog_item_lookup,
    get_catalog_products_for_organization,
    get_organization_catalog_items,
)
from app.extensions import db
from app.models import DriverApplication, SponsorOrganization, SponsorUser, User
from app.models.enums import (
    DriverApplicationStatus,
    DriverStatus,
    NotificationCategory,
    RoleType,
)
from app.models.system import Notification
from app.sponsor import sponsor_bp
from app.sponsor.services import *


def sponsor_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role_type != RoleType.SPONSOR:
            abort(403)
        return f(*args, **kwargs)

    return wrapper


def sponsor_breadcrumbs(*crumbs):
    base = [("Sponsor Dashboard", url_for("sponsor.dashboard"))]
    return base + list(crumbs)


def normalize_catalog_category(value: str | None) -> str:
    return sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")


def _parse_optional_date(date_str: str) -> dt.date | None:
    clean_date = (date_str or "").strip()
    if not clean_date:
        return None
    return dt.date.fromisoformat(clean_date)


@sponsor_bp.context_processor
def inject_sponsor_context():
    if not current_user.is_authenticated or current_user.role_type != RoleType.SPONSOR:
        return {
            "is_admin_impersonating_sponsor": False,
            "impersonation_banner_message": None,
            "impersonation_exit_endpoint": None,
            "impersonation_exit_label": None,
        }

    return build_admin_sponsor_impersonation_banner_context()


def render_driver_management_page(
    org_id: int,
    *,
    error: str | None = None,
    point_form_state: dict | None = None,
):
    drivers = get_organization_drivers(org_id)

    driverSponsors = {}

    for sponsorship in drivers:
        driver = sponsorship.driver
        user = driver.user

        all_sponsors = (
            db.session.query(SponsorOrganization)
            .join(
                DriverSponsorship,
                DriverSponsorship.organization_id == SponsorOrganization.organization_id,
            )
            .filter(
                DriverSponsorship.driver_id == driver.driver_id,
                DriverSponsorship.status == DriverStatus.ACTIVE,
            )
            .order_by(SponsorOrganization.name.asc())
            .all()
        )

        driverSponsors[user.user_id] = all_sponsors

    return render_template(
        "sponsor/driver_management.html",
        drivers=drivers,
        driverSponsors=driverSponsors,
        error=error,
        point_form_state=point_form_state,
        breadcrumbs=sponsor_breadcrumbs(("Driver Management", None)),
    )


def render_bulk_upload_page(*, report=None, error: str | None = None):
    return render_template(
        "sponsor/bulk_upload.html",
        report=report,
        error=error,
        breadcrumbs=sponsor_breadcrumbs(("Bulk Upload", None)),
    )


def render_driver_edit_page(
    org_id: int,
    driver_sponsorship_id: int,
    *,
    error: str | None = None,
    form_values: dict | None = None,
):
    sponsorship = get_organization_driver_sponsorship(org_id, driver_sponsorship_id)
    driver_user = sponsorship.driver.user
    display_name = f"{driver_user.first_name or ''} {driver_user.last_name or ''}".strip()
    if not display_name:
        display_name = driver_user.username

    return render_template(
        "sponsor/driver_edit.html",
        sponsorship=sponsorship,
        point_transactions=get_driver_point_transactions_for_sponsor(
            org_id, driver_sponsorship_id
        ),
        form_values=form_values,
        driver_display_name=display_name,
        error=error,
        breadcrumbs=sponsor_breadcrumbs(
            ("Driver Management", url_for("sponsor.driver_management")),
            (f"Edit {display_name}", None),
        ),
    )


def render_catalog_management_page(
    org_id: int,
    *,
    query: str = "",
    category: str = "",
    error: str | None = None,
):
    clean_query = (query or "").strip().lower()
    clean_category = (category or "").strip()

    try:
        categories = get_catalog_categories()
        catalog_items = get_catalog_products_for_organization(org_id)
        if clean_query:
            catalog_items = [
                (item, product)
                for item, product in catalog_items
                if clean_query
                in (product.title if product else item.product_name).strip().lower()
            ]
        if clean_category:
            catalog_items = [
                (item, product)
                for item, product in catalog_items
                if product and normalize_catalog_category(product.category) == clean_category
            ]
    except Exception as e:
        print(e)
        return render_template(
            "sponsor/catalog_management.html",
            categories=[],
            catalog_items=[],
            current_query=query,
            current_category=category,
            error=error
            or "The product catalog service is unavailable right now. Please try again.",
            breadcrumbs=sponsor_breadcrumbs(("Catalog Management", None)),
        )

    return render_template(
        "sponsor/catalog_management.html",
        categories=categories,
        catalog_items=catalog_items,
        current_query=query,
        current_category=category,
        error=error,
        breadcrumbs=sponsor_breadcrumbs(("Catalog Management", None)),
    )


def render_catalog_browser_page(
    org_id: int,
    *,
    query: str = "",
    category: str = "",
    page: int = 1,
    error: str | None = None,
):
    page_size = CATALOG_PAGE_SIZE
    organization = db.session.get(SponsorOrganization, org_id)

    try:
        categories = get_catalog_categories()
        product_list = browse_catalog_products(
            query=query,
            category=category,
            page=page,
            page_size=page_size,
        )
        catalog_items = get_organization_catalog_items(org_id)
    except Exception as e:
        print(e)
        return render_template(
            "sponsor/catalog_browse.html",
            organization=organization,
            catalog_external_ids=set(),
            catalog_ids_by_external_id={},
            categories=[],
            products=[],
            current_query=query,
            current_category=category,
            current_page=max(page, 1),
            total_pages=1,
            error=error
            or "The product catalog service is unavailable right now. Please try again.",
            breadcrumbs=sponsor_breadcrumbs(
                ("Catalog Management", url_for("sponsor.catalog_management")),
                ("Browse Products", None),
            ),
        )

    total_pages = max(1, (product_list.total + page_size - 1) // page_size)
    safe_page = min(max(page, 1), total_pages)
    if safe_page != page:
        product_list = browse_catalog_products(
            query=query,
            category=category,
            page=safe_page,
            page_size=page_size,
        )
    catalog_external_ids, catalog_ids_by_external_id = get_catalog_item_lookup(catalog_items)

    return render_template(
        "sponsor/catalog_browse.html",
        organization=organization,
        catalog_external_ids=catalog_external_ids,
        catalog_ids_by_external_id=catalog_ids_by_external_id,
        categories=categories,
        products=product_list.products,
        current_query=query,
        current_category=category,
        current_page=safe_page,
        total_pages=total_pages,
        error=error,
        breadcrumbs=sponsor_breadcrumbs(
            ("Catalog Management", url_for("sponsor.catalog_management")),
            ("Browse Products", None),
        ),
    )


def render_point_transactions_report_page(
    org_id: int,
    *,
    selected_driver_id: int | None = None,
    start_date_str: str = "",
    end_date_str: str = "",
):
    sponsorships = get_organization_drivers(org_id)
    driver_options = [
        {
            "driver_id": sponsorship.driver_id,
            "driver_name": build_user_display_name(sponsorship.driver.user),
        }
        for sponsorship in sponsorships
    ]
    valid_driver_ids = {option["driver_id"] for option in driver_options}
    error = None

    try:
        start_date = _parse_optional_date(start_date_str)
        end_date = _parse_optional_date(end_date_str)
    except ValueError:
        error = "Invalid date format. Use YYYY-MM-DD."
        start_date = None
        end_date = None

    if error is None and start_date and end_date and end_date < start_date:
        error = "End date must be on or after start date."

    if (
        error is None
        and selected_driver_id is not None
        and selected_driver_id not in valid_driver_ids
    ):
        error = "Selected driver was not found for your organization."

    redemption_summary = []
    point_transactions = []
    summary_totals = {
        "pending_orders": 0,
        "pending_points": 0,
        "completed_orders": 0,
        "completed_points": 0,
    }

    if error is None:
        redemption_summary = get_redemption_summary_for_sponsor(
            org_id,
            driver_id=selected_driver_id,
            start_date=start_date,
            end_date=end_date,
        )
        point_transactions = get_point_transaction_report_for_sponsor(
            org_id,
            driver_id=selected_driver_id,
            start_date=start_date,
            end_date=end_date,
        )
        summary_totals = {
            "pending_orders": sum(row["pending_orders"] for row in redemption_summary),
            "pending_points": sum(row["pending_points"] for row in redemption_summary),
            "completed_orders": sum(row["completed_orders"] for row in redemption_summary),
            "completed_points": sum(row["completed_points"] for row in redemption_summary),
        }

    return render_template(
        "sponsor/point_transactions_report.html",
        driver_options=driver_options,
        selected_driver_id=selected_driver_id,
        start_date=start_date_str,
        end_date=end_date_str,
        redemption_summary=redemption_summary,
        summary_totals=summary_totals,
        point_transactions=point_transactions,
        error=error,
        breadcrumbs=sponsor_breadcrumbs(("Point Transactions Report", None)),
    )


@sponsor_bp.route("/dashboard")
@login_required
@sponsor_required
def dashboard():
    s_user: SponsorUser = current_user.sponsor_user
    org = s_user.organization
    org_id = org.organization_id

    sponsor_users = org.sponsor_users
    users = [s.user for s in sponsor_users if s.sponsor_id != s_user.sponsor_id]

    pending_applications, _ = get_driver_applications(org_id)
    pending_applications = pending_applications or []

    return render_template(
        "sponsor/dashboard.html",
        users=users,
        num_applications=len(pending_applications),
        breadcrumbs=[("Sponsor Dashboard", None)],
    )


@sponsor_bp.route("/reports/point-transactions")
@login_required
@sponsor_required
def point_transactions_report():
    org_id = current_user.sponsor_user.organization_id
    return render_point_transactions_report_page(
        org_id,
        selected_driver_id=request.args.get("driver_id", type=int),
        start_date_str=request.args.get("start_date", "").strip(),
        end_date_str=request.args.get("end_date", "").strip(),
    )


@sponsor_bp.route("/reports/point-transactions/csv")
@login_required
@sponsor_required
def download_point_transactions_csv():
    org_id = current_user.sponsor_user.organization_id

    driver_id = request.args.get("driver_id", type=int)
    start_date_str = request.args.get("start_date", "").strip()
    end_date_str = request.args.get("end_date", "").strip()

    start_date = _parse_optional_date(start_date_str) if start_date_str else None
    end_date = _parse_optional_date(end_date_str) if end_date_str else None

    redemption_summary = get_redemption_summary_for_sponsor(
        org_id,
        driver_id=driver_id,
        start_date=start_date,
        end_date=end_date,
    )

    point_transactions = get_point_transaction_report_for_sponsor(
        org_id,
        driver_id=driver_id,
        start_date=start_date,
        end_date=end_date,
    )

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow(["Redemption Summary"])
    writer.writerow(["Driver", "Pending Orders", "Pending Points", "Completed Orders", "Completed Points"])

    for row in redemption_summary:
        writer.writerow([
            row["driver_name"],
            row["pending_orders"],
            row["pending_points"],
            row["completed_orders"],
            row["completed_points"],
        ])

    writer.writerow([])

    writer.writerow(["Point Transaction Details"])
    writer.writerow([
        "Driver Name",
        "Total Points",
        "Point Change",
        "Date",
        "Sponsor",
        "Reason"
    ])

    for row in point_transactions:
        writer.writerow([
            row["driver_name"],
            row["total_points"],
            row["point_change"],
            row["create_time"].strftime("%Y-%m-%d %H:%M"),
            row["sponsor_name"],
            row["reason"],
        ])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=point_transactions_report.csv"
        }
    )


@sponsor_bp.route("/impersonation/stop", methods=["POST"])
@login_required
@sponsor_required
def stop_impersonation():
    admin_user_id = get_impersonator_admin_sponsor_user_id()
    clear_admin_sponsor_impersonation()

    if admin_user_id is None:
        return redirect(url_for("sponsor.dashboard"))

    admin_user = get_admin_user_for_impersonation_return(admin_user_id)
    if admin_user is None:
        logout_user()
        flash(
            "The impersonation session ended, but the admin account could not be restored.",
            "error",
        )
        return redirect(url_for("auth.login"))

    login_user(admin_user)
    flash("Returned to the admin impersonation page.", "success")
    return redirect(url_for("admin.impersonate_sponsor_page"))


@sponsor_bp.route("/organization", methods=["GET", "POST"])
@login_required
@sponsor_required
def organization():
    org: SponsorOrganization = current_user.sponsor_user.organization
    breadcrumbs = sponsor_breadcrumbs(("Organization", None))

    if request.method == "POST":
        name = request.form.get("name", "")
        point_value = request.form.get("point_value", "")
        try:
            org = update_sponsor_organization(org, name, point_value)
            return render_template(
                "sponsor/organization.html", organization=org, breadcrumbs=breadcrumbs
            )
        except ValueError as e:
            return render_template(
                "sponsor/organization.html",
                organization=org,
                error=str(e),
                breadcrumbs=breadcrumbs,
            )

    return render_template(
        "sponsor/organization.html", organization=org, breadcrumbs=breadcrumbs
    )


@sponsor_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
@sponsor_required
def profile_edit():
    user = current_user
    assert isinstance(user, User)
    breadcrumbs = sponsor_breadcrumbs(("Edit Profile", None))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip() or None
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()

        try:
            validate_and_apply_user_profile_updates(
                user, username, email, first_name, last_name
            )
            db.session.commit()
            return redirect(url_for("sponsor.profile_edit"))
        except ValueError as e:
            return render_template(
                "sponsor/profile_edit.html",
                user=user,
                error=str(e),
                breadcrumbs=breadcrumbs,
            )

    return render_template(
        "sponsor/profile_edit.html", user=user, breadcrumbs=breadcrumbs
    )


@sponsor_bp.route("/create", methods=["GET", "POST"])
@login_required
@sponsor_required
def create_user():
    fields = {"username": "", "email": "", "first_name": "", "last_name": ""}
    breadcrumbs = sponsor_breadcrumbs(("Create Sponsor User", None))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()

        fields = {
            "username": username,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }

        organization = current_user.sponsor_user.organization

        try:
            create_sponsor_user(
                username, password, email, first_name, last_name, organization
            )
        except ValueError as e:
            return render_template(
                "sponsor/create_user.html",
                fields=fields,
                error=str(e),
                breadcrumbs=breadcrumbs,
            )

        return redirect(url_for("auth.home"))

    return render_template(
        "sponsor/create_user.html", fields=fields, breadcrumbs=breadcrumbs
    )


@sponsor_bp.route("/bulk-upload", methods=["GET", "POST"])
@login_required
@sponsor_required
def bulk_upload():
    if request.method == "POST":
        assert isinstance(current_user, User)
        upload = request.files.get("bulk_upload_file")
        if upload is None or not upload.filename:
            return render_bulk_upload_page(error="Choose a pipe-delimited text file to upload.")

        try:
            stream = build_text_stream(upload)
            report = process_bulk_upload_stream(
                stream,
                acting_user=current_user,
                scope="sponsor",
            )
        except UnicodeDecodeError:
            return render_bulk_upload_page(
                error="The uploaded file must be UTF-8 text."
            )
        finally:
            if "stream" in locals():
                stream.detach()

        return render_bulk_upload_page(report=report)

    return render_bulk_upload_page()


@sponsor_bp.route("/applications")
@login_required
@sponsor_required
def get_applications():
    pending_applications, historic_applications = get_driver_applications(
        current_user.sponsor_user.organization_id
    )
    breadcrumbs = sponsor_breadcrumbs(("Applications", None))

    return render_template(
        "sponsor/driver_applications.html",
        pending_applications=pending_applications,
        historic_applications=historic_applications,
        breadcrumbs=breadcrumbs,
    )

@sponsor_bp.route("/audit_log")
@login_required
@sponsor_required
def audit_log():
    org_id = current_user.sponsor_user.organization_id

    event_type = request.args.get("event_type", "").strip()
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")


    audits = get_organization_audit_logs(
        org_id,
        event_type=event_type,
        start_date=start_date,
        end_date=end_date
    )

    return render_template(
        "sponsor/audit_log.html", 
        audits=audits,
        selected_event_type=event_type,
        start_date=start_date,
        end_date=end_date
    )


@sponsor_bp.route("/audit_log/csv")
@login_required
@sponsor_required
def download_sponsor_audit_log_csv():
    org_id = current_user.sponsor_user.organization_id

    event_type = request.args.get("event_type", "").strip()
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")


    audits = get_organization_audit_logs(
        org_id,
        event_type=event_type,
        start_date=start_date,
        end_date=end_date
    )

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow(["Username", "Event", "Description", "Time"])

    for audit in audits:
        writer.writerow([
            audit['username'],
            audit['event_type'],
            audit['detail'],
            audit['event_time'].strftime('%Y-%m-%d %H:%M')
        ])

    output = si.getvalue()
    si.close

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sponsor_audit_log.csv"
        }
    )


@sponsor_bp.route("/catalog", methods=["GET", "POST"])
@login_required
@sponsor_required
def catalog_management():
    org_id = current_user.sponsor_user.organization_id

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        catalog_id = request.form.get("catalog_id", type=int)
        query = (request.form.get("query") or "").strip()
        category = (request.form.get("category") or "").strip()

        try:
            if action == "remove":
                if not catalog_id:
                    raise ValueError("A catalog item must be selected before it can be removed.")
                remove_catalog_item_for_organization(org_id, catalog_id)
            else:
                abort(400)

            return redirect(
                url_for(
                    "sponsor.catalog_management",
                    query=query,
                    category=category,
                )
            )
        except ValueError as e:
            return render_catalog_management_page(
                org_id,
                query=query,
                category=category,
                error=str(e),
            )
        except Exception as e:
            print(e)
            return render_catalog_management_page(
                org_id,
                query=query,
                category=category,
                error="The product catalog service is unavailable right now. Please try again.",
            )

    return render_catalog_management_page(
        org_id,
        query=(request.args.get("query") or "").strip(),
        category=(request.args.get("category") or "").strip(),
    )


@sponsor_bp.route("/catalog/browse", methods=["GET", "POST"])
@login_required
@sponsor_required
def catalog_browse():
    org_id = current_user.sponsor_user.organization_id

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        external_id = request.form.get("external_id", type=int)
        catalog_id = request.form.get("catalog_id", type=int)
        query = (request.form.get("query") or "").strip()
        category = (request.form.get("category") or "").strip()
        page = request.form.get("page", type=int) or 1

        try:
            if action == "add":
                if not external_id:
                    raise ValueError("A product must be selected before it can be added.")
                add_catalog_item_for_organization(org_id, external_id)
            elif action == "remove":
                if not catalog_id:
                    raise ValueError("A catalog item must be selected before it can be removed.")
                remove_catalog_item_for_organization(org_id, catalog_id)
            else:
                abort(400)
            return redirect(
                url_for(
                    "sponsor.catalog_browse",
                    query=query,
                    category=category,
                    page=page,
                )
            )
        except ValueError as e:
            return render_catalog_browser_page(
                org_id,
                query=query,
                category=category,
                page=page,
                error=str(e),
            )
        except Exception as e:
            print(e)
            return render_catalog_browser_page(
                org_id,
                query=query,
                category=category,
                page=page,
                error="The product catalog service is unavailable right now. Please try again.",
            )

    return render_catalog_browser_page(
        org_id,
        query=(request.args.get("query") or "").strip(),
        category=(request.args.get("category") or "").strip(),
        page=request.args.get("page", type=int) or 1,
    )


@sponsor_bp.route("/applications/<int:application_id>/decide", methods=["POST"])
@login_required
@sponsor_required
def decide_application(application_id: int):
    assert isinstance(current_user, User)
    assert isinstance(current_user.sponsor_user, SponsorUser)
    decision = (request.form.get("decision", "") or "").upper()
    reason = (request.form.get("reason", "") or "").strip()

    if decision not in ("APPROVED", "REJECTED"):
        abort(400)

    application: DriverApplication | None = DriverApplication.query.get(application_id)
    if not application:
        abort(404)
    if application.organization_id != current_user.sponsor_user.organization_id:
        abort(403)

    if application.status != DriverApplicationStatus.PENDING:
        return redirect(url_for("sponsor.get_applications"))

    decision_enum = DriverApplicationStatus[decision]
    if decision_enum == DriverApplicationStatus.APPROVED:
        approve_driver_for_sponsor(
            application.driver,
            current_user.sponsor_user.organization_id,
            acting_user=current_user,
        )
        message = "Your sponsor application has been approved."
    else:
        message = "Your sponsor application has been rejected."

    application.status = decision_enum
    application.reason = reason
    application.decision_date = dt.datetime.now(tz=dt.timezone.utc)
    application.decided_by_user_id = current_user.user_id

    db.session.add(
        Notification(
            driver_id=application.driver.driver_id,
            issued_by_user_id=current_user.user_id,
            category=NotificationCategory.APPLICATION,
            message=message,
            is_read=False,
        )
    )
    db.session.commit()

    return redirect(url_for("sponsor.get_applications"))


@sponsor_bp.route("/drivers", methods=["GET", "POST"])
@login_required
@sponsor_required
def driver_management():
    org_id = current_user.sponsor_user.organization_id

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        sponsorship_id = request.form.get("driver_sponsorship_id", type=int)

        if not sponsorship_id:
            return redirect(url_for("sponsor.driver_management"))

        if action == "drop":
            try:
                set_driver_status_for_sponsor(
                    org_id, sponsorship_id, DriverStatus.DROPPED, current_user
                )
                return redirect(url_for("sponsor.driver_management"))
            except ValueError as e:
                return render_driver_management_page(org_id, error=str(e))

        if action == "restore":
            try:
                set_driver_status_for_sponsor(
                    org_id, sponsorship_id, DriverStatus.ACTIVE, current_user
                )
                return redirect(url_for("sponsor.driver_management"))
            except ValueError as e:
                return render_driver_management_page(org_id, error=str(e))

        abort(400)

    return render_driver_management_page(org_id)


@sponsor_bp.route("/drivers/<int:driver_sponsorship_id>/edit", methods=["GET", "POST"])
@login_required
@sponsor_required
def edit_driver(driver_sponsorship_id: int):
    org_id = current_user.sponsor_user.organization_id

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip() or None
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()

        try:
            update_driver_profile_for_sponsor(
                org_id,
                driver_sponsorship_id,
                username,
                email,
                first_name,
                last_name,
            )
            return redirect(url_for("sponsor.driver_management"))
        except ValueError as e:
            return render_driver_edit_page(
                org_id,
                driver_sponsorship_id,
                error=str(e),
                form_values={
                    "username": username,
                    "email": email or "",
                    "first_name": first_name,
                    "last_name": last_name,
                },
            )

    return render_driver_edit_page(org_id, driver_sponsorship_id, form_values={})


@sponsor_bp.route("/drivers/<int:driver_sponsorship_id>/points", methods=["POST"])
@login_required
@sponsor_required
def update_driver_points(driver_sponsorship_id: int):
    assert isinstance(current_user, User)
    assert isinstance(current_user.sponsor_user, SponsorUser)
    org_id = current_user.sponsor_user.organization_id
    reason = (request.form.get("reason") or "").strip()
    raw_point_change = (request.form.get("point_change") or "").strip()

    try:
        point_change = int(raw_point_change)
    except ValueError:
        return render_driver_management_page(
            org_id,
            error="Point change must be a whole number.",
            point_form_state={
                "driver_sponsorship_id": driver_sponsorship_id,
                "point_change": raw_point_change,
                "reason": reason,
            },
        )

    try:
        adjust_driver_points_for_sponsor(
            org_id,
            driver_sponsorship_id,
            point_change,
            reason,
            current_user,
        )
    except ValueError as e:
        return render_driver_management_page(
            org_id,
            error=str(e),
            point_form_state={
                "driver_sponsorship_id": driver_sponsorship_id,
                "point_change": raw_point_change,
                "reason": reason,
            },
        )

    return redirect(url_for("sponsor.driver_management"))


@sponsor_bp.route(
    "/drivers/<int:driver_sponsorship_id>/impersonate",
    methods=["POST"],
)
@login_required
@sponsor_required
def impersonate_driver(driver_sponsorship_id: int):
    org_id = current_user.sponsor_user.organization_id
    sponsorship = get_organization_driver_sponsorship(org_id, driver_sponsorship_id)

    if sponsorship.status != DriverStatus.ACTIVE:
        flash("Only active drivers can be impersonated.", "error")
        return redirect(url_for("sponsor.driver_management"))

    driver_user = sponsorship.driver.user
    if not driver_user or driver_user.role_type != RoleType.DRIVER:
        abort(404)
    if not driver_user.is_user_active or driver_user.is_login_locked:
        flash("Only active, unlocked drivers can be impersonated.", "error")
        return redirect(url_for("sponsor.driver_management"))

    sponsor_user_id = current_user.user_id
    start_sponsor_driver_impersonation(
        sponsor_user_id=sponsor_user_id,
        driver_sponsorship_id=sponsorship.driver_sponsorship_id,
    )
    login_user(driver_user)

    display_name = f"{driver_user.first_name or ''} {driver_user.last_name or ''}".strip()
    if not display_name:
        display_name = driver_user.username

    flash(
        f"You are now impersonating {display_name} for {sponsorship.organization.name}.",
        "success",
    )
    return redirect(url_for("driver.dashboard"))
