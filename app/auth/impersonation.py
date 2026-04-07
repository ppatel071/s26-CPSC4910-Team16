from flask import session


IMPERSONATOR_SPONSOR_USER_ID_SESSION_KEY = "impersonator_sponsor_user_id"
IMPERSONATOR_ADMIN_USER_ID_SESSION_KEY = "impersonator_admin_user_id"
IMPERSONATED_DRIVER_SPONSORSHIP_ID_SESSION_KEY = "impersonated_driver_sponsorship_id"


def start_sponsor_driver_impersonation(
    sponsor_user_id: int,
    driver_sponsorship_id: int,
) -> None:
    clear_driver_impersonation()
    session[IMPERSONATOR_SPONSOR_USER_ID_SESSION_KEY] = sponsor_user_id
    session[IMPERSONATED_DRIVER_SPONSORSHIP_ID_SESSION_KEY] = driver_sponsorship_id


def clear_sponsor_driver_impersonation() -> None:
    session.pop(IMPERSONATOR_SPONSOR_USER_ID_SESSION_KEY, None)
    session.pop(IMPERSONATED_DRIVER_SPONSORSHIP_ID_SESSION_KEY, None)


def start_admin_driver_impersonation(admin_user_id: int) -> None:
    clear_driver_impersonation()
    session[IMPERSONATOR_ADMIN_USER_ID_SESSION_KEY] = admin_user_id


def clear_admin_driver_impersonation() -> None:
    session.pop(IMPERSONATOR_ADMIN_USER_ID_SESSION_KEY, None)


def clear_driver_impersonation() -> None:
    clear_sponsor_driver_impersonation()
    clear_admin_driver_impersonation()


def get_impersonator_sponsor_user_id() -> int | None:
    return session.get(IMPERSONATOR_SPONSOR_USER_ID_SESSION_KEY)


def get_impersonator_admin_user_id() -> int | None:
    return session.get(IMPERSONATOR_ADMIN_USER_ID_SESSION_KEY)


def get_impersonated_driver_sponsorship_id() -> int | None:
    return session.get(IMPERSONATED_DRIVER_SPONSORSHIP_ID_SESSION_KEY)


def is_sponsor_driver_impersonation_active() -> bool:
    return (
        get_impersonator_sponsor_user_id() is not None
        and get_impersonated_driver_sponsorship_id() is not None
    )


def is_admin_driver_impersonation_active() -> bool:
    return get_impersonator_admin_user_id() is not None
