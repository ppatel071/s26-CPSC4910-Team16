import datetime as dt
from functools import wraps

from flask import abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

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
from app.sponsor.services import (
    adjust_driver_points_for_sponsor,
    add_catalog_item_for_organization,
    approve_driver_for_sponsor,
    browse_catalog_products,
    create_sponsor_user,
    get_catalog_products_for_organization,
    get_driver_point_transactions_for_sponsor,
    get_organization_driver_sponsorship,
    get_organization_catalog_items,
    get_catalog_categories,
    get_driver_applications,
    get_organization_drivers,
    remove_catalog_item_for_organization,
    set_driver_status_for_sponsor,
    CATALOG_PAGE_SIZE,
    update_driver_profile_for_sponsor,
    update_sponsor_organization,
    validate_and_apply_user_profile_updates,
)


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


def render_driver_management_page(
    org_id: int,
    *,
    error: str | None = None,
    point_form_state: dict | None = None,
):
    return render_template(
        "sponsor/driver_management.html",
        drivers=get_organization_drivers(org_id),
        error=error,
        point_form_state=point_form_state,
        breadcrumbs=sponsor_breadcrumbs(("Driver Management", None)),
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
    error: str | None = None,
):
    try:
        catalog_items = get_catalog_products_for_organization(org_id)
    except Exception:
        return render_template(
            "sponsor/catalog_management.html",
            catalog_items=[],
            error=error
            or "The product catalog service is unavailable right now. Please try again.",
            breadcrumbs=sponsor_breadcrumbs(("Catalog Management", None)),
        )

    return render_template(
        "sponsor/catalog_management.html",
        catalog_items=catalog_items,
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

    try:
        categories = get_catalog_categories()
        product_list = browse_catalog_products(
            query=query,
            category=category,
            page=page,
            page_size=page_size,
        )
        catalog_items = get_organization_catalog_items(org_id)
    except Exception:
        return render_template(
            "sponsor/catalog_browse.html",
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

    return render_template(
        "sponsor/catalog_browse.html",
        catalog_external_ids={item.external_id for item in catalog_items},
        catalog_ids_by_external_id={
            item.external_id: item.catalog_id for item in catalog_items
        },
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


@sponsor_bp.route("/dashboard")
@login_required
@sponsor_required
def dashboard():
    s_user: SponsorUser = current_user.sponsor_user
    sponsor_users = s_user.organization.sponsor_users
    users = [s.user for s in sponsor_users if s.sponsor_id != s_user.sponsor_id]
    pending_applications, _ = get_driver_applications(
        current_user.sponsor_user.organization_id
    )
    pending_applications = pending_applications or []

    return render_template(
        "sponsor/dashboard.html",
        users=users,
        num_applications=len(pending_applications),
        breadcrumbs=[("Sponsor Dashboard", None)],
    )


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


@sponsor_bp.route("/catalog", methods=["GET", "POST"])
@login_required
@sponsor_required
def catalog_management():
    org_id = current_user.sponsor_user.organization_id

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        catalog_id = request.form.get("catalog_id", type=int)

        try:
            if action == "remove":
                if not catalog_id:
                    raise ValueError("A catalog item must be selected before it can be removed.")
                remove_catalog_item_for_organization(org_id, catalog_id)
            else:
                abort(400)

            return redirect(url_for("sponsor.catalog_management"))
        except ValueError as e:
            return render_catalog_management_page(org_id, error=str(e))
        except Exception:
            return render_catalog_management_page(
                org_id,
                error="The product catalog service is unavailable right now. Please try again.",
            )

    return render_catalog_management_page(org_id)


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
        except Exception:
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
            application.driver, current_user.sponsor_user.organization_id
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
        return redirect(url_for("sponsor.driver_management"))
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
