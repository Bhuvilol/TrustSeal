from enum import Enum

class UserRole(str, Enum):
    FACTORY = "factory"
    PORT = "port"
    WAREHOUSE = "warehouse"
    CUSTOMER = "customer"
    ADMIN = "admin"
    AUTHORITY = "authority"

class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"

class ShipmentStatus(str, Enum):
    CREATED = "created"
    IN_TRANSIT = "in_transit"
    DOCKING = "docking"
    COMPLETED = "completed"
    COMPROMISED = "compromised"

class LegStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SETTLED = "settled"
