"""Canonical domain enums for ResolveX AI.

PRD §7.1: Status dimensions are strictly separated to prevent collapsing
payment status, funds status, refund status, settlement status, and case status.
"""

from enum import StrEnum


class PaymentStatus(StrEnum):
    """Authoritative provider-confirmed payment status."""

    CREATED = "CREATED"
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    REVERSED = "REVERSED"
    UNKNOWN = "UNKNOWN"


class FundsStatus(StrEnum):
    """Independent debit/credit status indicating provider confirmation vs customer claim."""

    NOT_REPORTED = "NOT_REPORTED"
    CUSTOMER_REPORTED_DEBIT = "CUSTOMER_REPORTED_DEBIT"
    PROVIDER_CONFIRMED_DEBIT = "PROVIDER_CONFIRMED_DEBIT"
    PROVIDER_CONFIRMED_CREDIT = "PROVIDER_CONFIRMED_CREDIT"
    UNKNOWN = "UNKNOWN"


class RefundStatus(StrEnum):
    """Refund lifecycle state machine."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_INITIATED = "NOT_INITIATED"
    REQUESTED = "REQUESTED"
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class SettlementStatus(StrEnum):
    """Merchant settlement reconciliation status."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


class CaseStatus(StrEnum):
    """Case triage and resolution lifecycle."""

    NEW = "NEW"
    TRIAGING = "TRIAGING"
    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CaseType(StrEnum):
    """Categorization of financial operations cases."""

    PAYMENT_DISCREPANCY = "PAYMENT_DISCREPANCY"
    FRAUD_INVESTIGATION = "FRAUD_INVESTIGATION"
    REFUND_DELAY = "REFUND_DELAY"
    UNRECOGNIZED_TRANSACTION = "UNRECOGNIZED_TRANSACTION"


class FraudSeverity(StrEnum):
    """Deterministic and investigative fraud severity."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UserRole(StrEnum):
    """Role-based access control roles."""

    CUSTOMER = "CUSTOMER"
    SUPPORT_ANALYST = "SUPPORT_ANALYST"
    FRAUD_ANALYST = "FRAUD_ANALYST"
    SUPERVISOR = "SUPERVISOR"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"


class EvidenceSourceType(StrEnum):
    """Origin of evidence items."""

    RECEIPT_IMAGE = "RECEIPT_IMAGE"
    PDF_STATEMENT = "PDF_STATEMENT"
    VOICE_NOTE = "VOICE_NOTE"
    NOTIFICATION_SCREENSHOT = "NOTIFICATION_SCREENSHOT"
    WEBHOOK_PAYLOAD = "WEBHOOK_PAYLOAD"
    SYSTEM_LOG = "SYSTEM_LOG"


class VerificationState(StrEnum):
    """Candidate claim verification lifecycle."""

    UNVERIFIED = "UNVERIFIED"
    USER_CONFIRMED = "USER_CONFIRMED"
    REJECTED = "REJECTED"
    PROVIDER_MATCHED = "PROVIDER_MATCHED"


class ApprovalDecision(StrEnum):
    """Status of human-in-the-loop approval actions."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETURNED_FOR_EVIDENCE = "RETURNED_FOR_EVIDENCE"
