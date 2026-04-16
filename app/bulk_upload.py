from __future__ import annotations

from dataclasses import dataclass, field
import io
import secrets
from typing import TextIO

from sqlalchemy import func

from app.auth.services import register_user
from app.extensions import db
from app.models import DriverSponsorship, SponsorOrganization, SponsorUser, User, Driver
from app.models.enums import DriverStatus, RoleType
from app.sponsor.services import approve_driver_for_sponsor, adjust_driver_points_for_sponsor


SPONSOR_SCOPE = "sponsor"
ADMIN_SCOPE = "admin"
VALID_RECORD_TYPES = {"O", "D", "S"}


class BulkUploadError(ValueError):
    pass


@dataclass
class BulkUploadIssue:
    line_number: int
    level: str
    message: str
    raw_line: str


@dataclass
class BulkUploadCredential:
    role: str
    organization_name: str | None
    email: str
    username: str
    temporary_password: str


@dataclass
class BulkUploadReport:
    scope: str
    input_lines: int = 0
    successful_lines: int = 0
    skipped_lines: int = 0
    created_organizations: int = 0
    created_sponsors: int = 0
    created_drivers: int = 0
    updated_drivers: int = 0
    warning_count: int = 0
    error_count: int = 0
    issues: list[BulkUploadIssue] = field(default_factory=list)
    created_credentials: list[BulkUploadCredential] = field(default_factory=list)

    def add_issue(
        self,
        *,
        line_number: int,
        level: str,
        message: str,
        raw_line: str,
    ) -> None:
        self.issues.append(
            BulkUploadIssue(
                line_number=line_number,
                level=level,
                message=message,
                raw_line=raw_line,
            )
        )
        if level == "warning":
            self.warning_count += 1
        else:
            self.error_count += 1


def build_text_stream(upload) -> TextIO:
    upload.stream.seek(0)
    return io.TextIOWrapper(upload.stream, encoding="utf-8-sig", newline=None)


def process_bulk_upload_stream(
    stream: TextIO,
    *,
    acting_user: User,
    scope: str,
) -> BulkUploadReport:
    if scope not in {SPONSOR_SCOPE, ADMIN_SCOPE}:
        raise ValueError("Invalid bulk upload scope.")

    report = BulkUploadReport(scope=scope)

    try:
        for line_number, raw_line in enumerate(stream, start=1):
            original_line = raw_line.rstrip("\r\n")
            if not original_line.strip():
                report.input_lines += 1
                report.skipped_lines += 1
                report.add_issue(
                    line_number=line_number,
                    level="warning",
                    message="Blank lines are ignored.",
                    raw_line="",
                )
                continue

            report.input_lines += 1
            savepoint = db.session.begin_nested()
            try:
                warnings, created_credential = _process_record(
                    line_number=line_number,
                    raw_line=original_line,
                    acting_user=acting_user,
                    scope=scope,
                    report=report,
                )
                savepoint.commit()
                report.successful_lines += 1
                if created_credential is not None:
                    report.created_credentials.append(created_credential)
                for warning in warnings:
                    report.add_issue(
                        line_number=line_number,
                        level="warning",
                        message=warning,
                        raw_line=original_line,
                    )
            except BulkUploadError as exc:
                savepoint.rollback()
                report.skipped_lines += 1
                report.add_issue(
                    line_number=line_number,
                    level="error",
                    message=str(exc),
                    raw_line=original_line,
                )

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return report


def _process_record(
    *,
    line_number: int,
    raw_line: str,
    acting_user: User,
    scope: str,
    report: BulkUploadReport,
) -> tuple[list[str], BulkUploadCredential | None]:
    fields = raw_line.split("|")
    if len(fields) > 7:
        raise BulkUploadError("Too many fields. Expected at most 7 pipe-delimited values.")

    record_type = (fields[0] if fields else "").strip().upper()
    if record_type not in VALID_RECORD_TYPES:
        raise BulkUploadError("Type must be one of O, D, or S.")

    if record_type == "O":
        return _process_organization_record(
            fields=fields,
            line_number=line_number,
            raw_line=raw_line,
            scope=scope,
            report=report,
        )

    if len(fields) < 5:
        raise BulkUploadError(
            "Driver and sponsor records require type, organization field, first name, last name, and email."
        )

    padded_fields = fields + [""] * (7 - len(fields))
    organization_name = padded_fields[1].strip()
    first_name = padded_fields[2].strip()
    last_name = padded_fields[3].strip()
    email = padded_fields[4].strip().lower()
    points_raw = padded_fields[5].strip()
    reason = padded_fields[6].strip()

    if not first_name:
        raise BulkUploadError("First name is required.")
    if not last_name:
        raise BulkUploadError("Last name is required.")
    if not email:
        raise BulkUploadError("Email address is required.")

    if record_type == "S":
        return _process_sponsor_record(
            organization_name=organization_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            points_raw=points_raw,
            reason=reason,
            acting_user=acting_user,
            scope=scope,
            report=report,
        )

    return _process_driver_record(
        organization_name=organization_name,
        first_name=first_name,
        last_name=last_name,
        email=email,
        points_raw=points_raw,
        reason=reason,
        acting_user=acting_user,
        scope=scope,
        report=report,
    )


def _process_organization_record(
    *,
    fields: list[str],
    line_number: int,
    raw_line: str,
    scope: str,
    report: BulkUploadReport,
) -> tuple[list[str], None]:
    if scope == SPONSOR_SCOPE:
        raise BulkUploadError("Sponsors cannot upload organization records.")

    if len(fields) < 2:
        raise BulkUploadError("Organization records require an organization name.")

    organization_name = fields[1].strip()
    if not organization_name:
        raise BulkUploadError("Organization name is required.")

    warnings: list[str] = []
    if any((value or "").strip() for value in fields[2:]):
        warnings.append("Only the organization name is used for O records. Extra fields were ignored.")

    organization = _find_single_organization_by_name(organization_name)
    if organization is None:
        db.session.add(SponsorOrganization(name=organization_name, point_value=0.01))
        db.session.flush()
        report.created_organizations += 1
    else:
        warnings.append(f'Organization "{organization.name}" already exists and was reused.')

    return warnings, None


def _process_sponsor_record(
    *,
    organization_name: str,
    first_name: str,
    last_name: str,
    email: str,
    points_raw: str,
    reason: str,
    acting_user: User,
    scope: str,
    report: BulkUploadReport,
) -> tuple[list[str], BulkUploadCredential | None]:
    warnings: list[str] = []
    organization = _resolve_target_organization(
        scope=scope,
        acting_user=acting_user,
        organization_name=organization_name,
        warnings=warnings,
    )

    if points_raw or reason:
        warnings.append("Points cannot be assigned to sponsor users. Points and reason were ignored.")

    existing_user = _find_user_by_email(email)
    if existing_user is None:
        temporary_password = _generate_temporary_password()
        created_user = register_user(
            username=email,
            password=temporary_password,
            role=RoleType.SPONSOR,
            email=email,
            first_name=first_name,
            last_name=last_name,
            commit=False,
        )
        db.session.add(
            SponsorUser(
                user_id=created_user.user_id,
                organization_id=organization.organization_id,
            )
        )
        db.session.flush()
        report.created_sponsors += 1
        return warnings, BulkUploadCredential(
            role="Sponsor",
            organization_name=organization.name,
            email=email,
            username=created_user.username,
            temporary_password=temporary_password,
        )

    if existing_user.role_type != RoleType.SPONSOR or existing_user.sponsor_user is None:
        raise BulkUploadError(
            f"Email {email} already belongs to a non-sponsor account and cannot be uploaded as a sponsor."
        )

    if existing_user.sponsor_user.organization_id != organization.organization_id:
        raise BulkUploadError(
            f"Email {email} already belongs to a sponsor user in a different organization."
        )

    return warnings, None


def _process_driver_record(
    *,
    organization_name: str,
    first_name: str,
    last_name: str,
    email: str,
    points_raw: str,
    reason: str,
    acting_user: User,
    scope: str,
    report: BulkUploadReport,
) -> tuple[list[str], BulkUploadCredential | None]:
    warnings: list[str] = []
    organization = _resolve_target_organization(
        scope=scope,
        acting_user=acting_user,
        organization_name=organization_name,
        warnings=warnings,
    )

    point_change = _parse_optional_point_change(points_raw=points_raw, reason=reason)
    existing_user = _find_user_by_email(email)
    created_credential: BulkUploadCredential | None = None

    if existing_user is None:
        temporary_password = _generate_temporary_password()
        created_user = register_user(
            username=email,
            password=temporary_password,
            role=RoleType.DRIVER,
            email=email,
            first_name=first_name,
            last_name=last_name,
            commit=False,
        )
        existing_user = created_user
        report.created_drivers += 1
        created_credential = BulkUploadCredential(
            role="Driver",
            organization_name=organization.name,
            email=email,
            username=created_user.username,
            temporary_password=temporary_password,
        )
    else:
        if existing_user.role_type != RoleType.DRIVER or existing_user.driver is None:
            raise BulkUploadError(
                f"Email {email} already belongs to a non-driver account and cannot be uploaded as a driver."
            )
        report.updated_drivers += 1
    assert isinstance(existing_user.driver, Driver)
    existing_sponsorship = DriverSponsorship.query.filter_by(
        driver_id=existing_user.driver.driver_id,
        organization_id=organization.organization_id,
    ).first()
    sponsorship = approve_driver_for_sponsor(
        existing_user.driver,
        organization.organization_id,
        acting_user=acting_user,
        commit=False,
    )
    if existing_sponsorship is not None and existing_sponsorship.status != DriverStatus.ACTIVE:
        warnings.append("Existing driver sponsorship was reactivated automatically.")

    if point_change is not None:
        adjust_driver_points_for_sponsor(
            organization.organization_id,
            sponsorship.driver_sponsorship_id,
            point_change,
            reason,
            acting_user,
            commit=False,
        )

    return warnings, created_credential


def _resolve_target_organization(
    *,
    scope: str,
    acting_user: User,
    organization_name: str,
    warnings: list[str],
) -> SponsorOrganization:
    if scope == SPONSOR_SCOPE:
        if organization_name:
            warnings.append(
                "Organization name is ignored for sponsor uploads. Records are always loaded into your organization."
            )
        sponsor_user = acting_user.sponsor_user
        if sponsor_user is None or sponsor_user.organization is None:
            raise BulkUploadError("Your sponsor account is not linked to an organization.")
        return sponsor_user.organization

    if not organization_name:
        raise BulkUploadError("Organization name is required for admin driver and sponsor records.")

    organization = _find_single_organization_by_name(organization_name)
    if organization is None:
        raise BulkUploadError(
            f'Organization "{organization_name}" does not exist. Add it with an O record before using it.'
        )
    return organization


def _find_single_organization_by_name(name: str) -> SponsorOrganization | None:
    matches = (
        SponsorOrganization.query.filter(
            func.lower(SponsorOrganization.name) == name.strip().lower()
        )
        .order_by(SponsorOrganization.organization_id.asc())
        .all()
    )
    if not matches:
        return None
    if len(matches) > 1:
        raise BulkUploadError(
            f'Multiple organizations named "{name}" already exist. Use a unique organization name before bulk uploading.'
        )
    return matches[0]


def _find_user_by_email(email: str) -> User | None:
    return User.query.filter(func.lower(User.email) == email.lower()).first()


def _parse_optional_point_change(*, points_raw: str, reason: str) -> int | None:
    if not points_raw and not reason:
        return None
    if not points_raw and reason:
        raise BulkUploadError("Reason for points cannot be provided without a points value.")
    if points_raw and not reason:
        raise BulkUploadError("Reason for points is required when a points value is provided.")

    try:
        return int(points_raw)
    except ValueError as exc:
        raise BulkUploadError("Points must be a whole number.") from exc


def _generate_temporary_password() -> str:
    return f"Temp{secrets.token_hex(4)}1a"
