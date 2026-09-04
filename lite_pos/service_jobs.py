"""Shared presentation of the staff-work and customer-collection stages."""

READY_FOR_PICKUP_STATUSES = {"ready_for_pickup", "ready", "completed"}


def job_status_style(status: str) -> tuple[str, str, str]:
    if status in READY_FOR_PICKUP_STATUSES:
        return "Ready for Pickup", "#f3e8ff", "#6b21a8"
    return {
        "in_progress": ("In Progress", "#dbeafe", "#1e40af"),
        "delivered": ("Delivered", "#dcfce7", "#166534"),
        "cancelled": ("Cancelled", "#fee2e2", "#991b1b"),
    }.get(status, ("Pending", "#fef3c7", "#92400e"))
