from flask import session
import time


IMPERSONATOR_SPONSOR_USER_ID_SESSION_KEY = "impersonator_sponsor_user_id"
IMPERSONATOR_ADMIN_USER_ID_SESSION_KEY = "impersonator_admin_user_id"
IMPERSONATOR_ADMIN_SPONSOR_USER_ID_SESSION_KEY = "impersonator_admin_sponsor_user_id"
IMPERSONATED_DRIVER_SPONSORSHIP_ID_SESSION_KEY = "impersonated_driver_sponsorship_id"
SPONSOR_IMPERSONATION_LAST_ACTIVITY_SESSION_KEY = "sponsor_impersonation_last_activity"
SPONSOR_IMPERSONATION_IDLE_TIMEOUT_SECONDS = 10 * 60


def start_sponsor_driver_impersonation(
    sponsor_user_id: int,
    driver_sponsorship_id: int,
) -> None:
    clear_driver_impersonation()
    session[IMPERSONATOR_SPONSOR_USER_ID_SESSION_KEY] = sponsor_user_id
    session[IMPERSONATED_DRIVER_SPONSORSHIP_ID_SESSION_KEY] = driver_sponsorship_id
    touch_sponsor_driver_impersonation_activity()


def clear_sponsor_driver_impersonation() -> None:
    session.pop(IMPERSONATOR_SPONSOR_USER_ID_SESSION_KEY, None)
    session.pop(IMPERSONATED_DRIVER_SPONSORSHIP_ID_SESSION_KEY, None)
    session.pop(SPONSOR_IMPERSONATION_LAST_ACTIVITY_SESSION_KEY, None)


def start_admin_driver_impersonation(admin_user_id: int) -> None:
    clear_driver_impersonation()
    clear_admin_sponsor_impersonation()
    session[IMPERSONATOR_ADMIN_USER_ID_SESSION_KEY] = admin_user_id


def clear_admin_driver_impersonation() -> None:
    session.pop(IMPERSONATOR_ADMIN_USER_ID_SESSION_KEY, None)


def start_admin_sponsor_impersonation(admin_user_id: int) -> None:
    clear_driver_impersonation()
    clear_admin_sponsor_impersonation()
    session[IMPERSONATOR_ADMIN_SPONSOR_USER_ID_SESSION_KEY] = admin_user_id


def clear_admin_sponsor_impersonation() -> None:
    session.pop(IMPERSONATOR_ADMIN_SPONSOR_USER_ID_SESSION_KEY, None)


def clear_driver_impersonation() -> None:
    clear_sponsor_driver_impersonation()
    clear_admin_driver_impersonation()


def clear_impersonation() -> None:
    clear_driver_impersonation()
    clear_admin_sponsor_impersonation()


def get_impersonator_sponsor_user_id() -> int | None:
    return session.get(IMPERSONATOR_SPONSOR_USER_ID_SESSION_KEY)


def get_impersonator_admin_user_id() -> int | None:
    return session.get(IMPERSONATOR_ADMIN_USER_ID_SESSION_KEY)


def get_impersonator_admin_sponsor_user_id() -> int | None:
    return session.get(IMPERSONATOR_ADMIN_SPONSOR_USER_ID_SESSION_KEY)


def get_impersonated_driver_sponsorship_id() -> int | None:
    return session.get(IMPERSONATED_DRIVER_SPONSORSHIP_ID_SESSION_KEY)


def is_sponsor_driver_impersonation_active() -> bool:
    return (
        get_impersonator_sponsor_user_id() is not None
        and get_impersonated_driver_sponsorship_id() is not None
    )


def touch_sponsor_driver_impersonation_activity() -> None:
    session[SPONSOR_IMPERSONATION_LAST_ACTIVITY_SESSION_KEY] = int(time.time())


def is_sponsor_driver_impersonation_timed_out() -> bool:
    if not is_sponsor_driver_impersonation_active():
        return False

    last_activity = session.get(SPONSOR_IMPERSONATION_LAST_ACTIVITY_SESSION_KEY)
    if last_activity is None:
        return True

    return (int(time.time()) - int(last_activity)) >= SPONSOR_IMPERSONATION_IDLE_TIMEOUT_SECONDS


def is_admin_driver_impersonation_active() -> bool:
    return get_impersonator_admin_user_id() is not None


def is_admin_sponsor_impersonation_active() -> bool:
    return get_impersonator_admin_sponsor_user_id() is not None
