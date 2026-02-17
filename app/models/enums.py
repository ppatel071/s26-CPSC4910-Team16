import enum


class RoleType(enum.Enum):
    DRIVER = 'DRIVER'
    SPONSOR = 'SPONSOR'
    ADMIN = 'ADMIN'


class PasswordChangeType(enum.Enum):
    RESET = 'RESET'
    UPDATE = 'UPDATE'
    ADMIN_RESET = 'ADMIN_RESET'


class DriverStatus(enum.Enum):
    PENDING = 'PENDING'
    ACTIVE = 'ACTIVE'
    PAUSED = 'PAUSED'
    DROPPED = 'DROPPED'


class DriverApplicationStatus(enum.Enum):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'


class OrderStatus(enum.Enum):
    PENDING = 'PENDING'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


class NotificationCategory(enum.Enum):
    DRIVER_DROPPED = 'DRIVER_DROPPED'
    POINT_CHANGE = 'POINT_CHANGE'
    ORDER_PLACED = 'ORDER_PLACED'
