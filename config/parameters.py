"""Hardcoded business parameters.

These values drive business logic that is checked in code. Changes require a
release — unlike Settings tables, which are runtime-configurable via the UI.
"""
from typing import Final

# Physical panel areas for Job Auto (values stored on job_auto_film.area)
JOB_AUTO_AREAS: Final[list[str]] = [
    "windshield",
    "full_around",
    "front_side",
    "back_side",
    "rear",
    "sunroof",
    "three_front",
    "three_rear",
]

# Invoice type on a job — drives VAT handling
INVOICE_TYPES: Final[list[str]] = ["vat", "non_vat"]

# Purchase order state on a job
# - not_required: job doesn't need a PO
# - pending: needs one, waiting for dealer to send
# - available: PO received and linked via purchase_order_id
PO_STATUSES: Final[list[str]] = ["not_required", "pending", "available"]

# User employment type — drives compensation model selection
# - employee: internal DGC staff; gets commission via commission_rate_auto
# - contractor: external paid flat per price_type via installer_compensation_rate
EMPLOYMENT_TYPES: Final[list[str]] = ["employee", "contractor"]

# Leave types — only `holiday` deducts from balance
LEAVE_TYPES: Final[list[str]] = ["holiday", "sick", "wfh", "substitute"]
LEAVE_TYPE_DEDUCTS_BALANCE: Final[set[str]] = {"holiday"}

# Expense types
EXPENSE_TYPES: Final[list[str]] = ["reimbursement", "loan", "advance_payment", "petty_cash"]

# Leave policy
LEAVE_CARRYOVER_CAP_DAYS: Final[int] = 10
LEAVE_AUTO_APPROVE_HOURS: Final[int] = 24

# Job Auto statuses (Q39: simplified 4-state lifecycle)
# `awaiting_po` is a flag field on job_auto, not a status.
# `invoiced` is derived from internal_invoice_id IS NOT NULL.
JOB_AUTO_STATUSES: Final[list[str]] = [
    "scheduled",
    "completed",
    "cancelled",
    "paid",
]

BOOKING_BUILDING_STATUSES: Final[list[str]] = [
    "draft",
    "surveyed",
    "quoted",
    "approved",
    "scheduled",
    "in_progress",
    "completed",
    "invoiced",
    "paid",
    "cancelled",
]

# Order statuses
ORDER_STATUSES: Final[list[str]] = ["order", "dispatched", "paid", "cancelled"]

# Fiscal period statuses
FISCAL_PERIOD_STATUSES: Final[list[str]] = ["open", "closing", "closed"]
