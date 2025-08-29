"""Billing and invoice management."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class Invoice:
    """Invoice for tenant billing."""

    id: str
    tenant_id: str
    period_start: datetime
    period_end: datetime

    # Usage
    total_requests: int
    total_tokens: int
    cached_requests: int

    # Costs
    usage_cost: float
    overage_cost: float
    discount: float
    tax: float
    total_cost: float

    # Status
    status: str  # draft, pending, paid, overdue
    due_date: datetime
    paid_date: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "period": {"start": self.period_start.isoformat(), "end": self.period_end.isoformat()},
            "usage": {
                "requests": self.total_requests,
                "tokens": self.total_tokens,
                "cached_requests": self.cached_requests,
            },
            "costs": {
                "usage": round(self.usage_cost, 2),
                "overage": round(self.overage_cost, 2),
                "discount": round(self.discount, 2),
                "tax": round(self.tax, 2),
                "total": round(self.total_cost, 2),
            },
            "status": self.status,
            "due_date": self.due_date.isoformat(),
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
        }


class BillingManager:
    """Manages billing and invoicing."""

    # Pricing tiers
    PRICING_TIERS = {
        "free": {
            "monthly_cost": 0,
            "included_requests": 100,
            "included_tokens": 10000,
            "overage_per_1k_tokens": 0.005,
        },
        "starter": {
            "monthly_cost": 29,
            "included_requests": 1000,
            "included_tokens": 100000,
            "overage_per_1k_tokens": 0.003,
        },
        "professional": {
            "monthly_cost": 99,
            "included_requests": 10000,
            "included_tokens": 1000000,
            "overage_per_1k_tokens": 0.002,
        },
        "enterprise": {
            "monthly_cost": 499,
            "included_requests": 100000,
            "included_tokens": 10000000,
            "overage_per_1k_tokens": 0.001,
        },
    }

    def __init__(self):
        self.invoices: dict[str, Invoice] = {}
        self.tenant_tiers: dict[str, str] = {}  # tenant_id -> tier
        logger.info("Billing manager initialized")

    def set_tenant_tier(self, tenant_id: str, tier: str):
        """Set pricing tier for tenant."""
        if tier not in self.PRICING_TIERS:
            raise ValueError(f"Invalid tier: {tier}")

        self.tenant_tiers[tenant_id] = tier
        logger.info(f"Set tenant {tenant_id} to {tier} tier")

    def generate_invoice(
        self, tenant_id: str, period_start: datetime, period_end: datetime, usage_summary: dict
    ) -> Invoice:
        """Generate invoice for tenant."""

        # Get tenant tier
        tier = self.tenant_tiers.get(tenant_id, "free")
        tier_config = self.PRICING_TIERS[tier]

        # Extract usage
        total_requests = usage_summary.get("requests", 0)
        total_tokens = usage_summary.get("tokens", 0)
        cached_requests = usage_summary.get("cached_requests", 0)

        # Calculate base cost
        base_cost = tier_config["monthly_cost"]

        # Calculate overage
        overage_tokens = max(0, total_tokens - tier_config["included_tokens"])
        overage_cost = (overage_tokens / 1000) * tier_config["overage_per_1k_tokens"]

        # Apply discounts
        discount = 0

        # Volume discount
        if total_requests > 50000:
            discount = (base_cost + overage_cost) * 0.1
        elif total_requests > 10000:
            discount = (base_cost + overage_cost) * 0.05

        # Cache usage discount
        cache_rate = cached_requests / max(total_requests, 1)
        if cache_rate > 0.5:
            discount += (base_cost + overage_cost) * 0.05

        # Calculate tax (simplified)
        subtotal = base_cost + overage_cost - discount
        tax = subtotal * 0.1  # 10% tax rate

        # Total
        total_cost = subtotal + tax

        # Create invoice
        invoice = Invoice(
            id=str(uuid4()),
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            total_requests=total_requests,
            total_tokens=total_tokens,
            cached_requests=cached_requests,
            usage_cost=base_cost,
            overage_cost=overage_cost,
            discount=discount,
            tax=tax,
            total_cost=total_cost,
            status="draft",
            due_date=period_end + timedelta(days=30),
        )

        self.invoices[invoice.id] = invoice

        logger.info(f"Generated invoice {invoice.id} for tenant {tenant_id}: ${total_cost:.2f}")

        return invoice

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        """Get invoice by ID."""
        return self.invoices.get(invoice_id)

    def get_tenant_invoices(self, tenant_id: str) -> list[Invoice]:
        """Get all invoices for a tenant."""
        return [invoice for invoice in self.invoices.values() if invoice.tenant_id == tenant_id]

    def mark_invoice_paid(self, invoice_id: str):
        """Mark invoice as paid."""
        invoice = self.invoices.get(invoice_id)
        if invoice:
            invoice.status = "paid"
            invoice.paid_date = datetime.now()
            logger.info(f"Invoice {invoice_id} marked as paid")

    def get_billing_summary(self, tenant_id: str) -> dict:
        """Get billing summary for tenant."""

        tier = self.tenant_tiers.get(tenant_id, "free")
        tier_config = self.PRICING_TIERS[tier]

        # Get invoices
        invoices = self.get_tenant_invoices(tenant_id)

        # Calculate totals
        total_billed = sum(inv.total_cost for inv in invoices)
        total_paid = sum(inv.total_cost for inv in invoices if inv.status == "paid")
        outstanding = total_billed - total_paid

        # Get current month usage (mock)
        current_usage = {"requests": 5000, "tokens": 500000, "estimated_cost": 45.00}

        return {
            "tenant_id": tenant_id,
            "billing_tier": tier,
            "tier_details": tier_config,
            "current_month": current_usage,
            "billing_history": {
                "total_invoices": len(invoices),
                "total_billed": round(total_billed, 2),
                "total_paid": round(total_paid, 2),
                "outstanding": round(outstanding, 2),
            },
            "recent_invoices": [
                inv.to_dict()
                for inv in sorted(invoices, key=lambda x: x.period_end, reverse=True)[:5]
            ],
        }

    def estimate_monthly_cost(self, tenant_id: str, daily_requests: int, daily_tokens: int) -> dict:
        """Estimate monthly cost based on usage."""

        tier = self.tenant_tiers.get(tenant_id, "free")
        tier_config = self.PRICING_TIERS[tier]

        # Project to monthly
        monthly_requests = daily_requests * 30
        monthly_tokens = daily_tokens * 30

        # Calculate costs
        base_cost = tier_config["monthly_cost"]

        overage_tokens = max(0, monthly_tokens - tier_config["included_tokens"])
        overage_cost = (overage_tokens / 1000) * tier_config["overage_per_1k_tokens"]

        total_cost = base_cost + overage_cost

        # Recommend tier
        recommended_tier = self._recommend_tier(monthly_requests, monthly_tokens)

        return {
            "current_tier": tier,
            "estimated_monthly_cost": round(total_cost, 2),
            "breakdown": {
                "base_cost": base_cost,
                "overage_cost": round(overage_cost, 2),
                "included_requests": tier_config["included_requests"],
                "included_tokens": tier_config["included_tokens"],
                "projected_requests": monthly_requests,
                "projected_tokens": monthly_tokens,
            },
            "recommended_tier": recommended_tier,
            "potential_savings": self._calculate_savings(tier, recommended_tier, monthly_tokens),
        }

    def _recommend_tier(self, monthly_requests: int, monthly_tokens: int) -> str:
        """Recommend best tier based on usage."""

        best_tier = "free"
        best_cost = float("inf")

        for tier_name, tier_config in self.PRICING_TIERS.items():
            base_cost = tier_config["monthly_cost"]

            overage_tokens = max(0, monthly_tokens - tier_config["included_tokens"])
            overage_cost = (overage_tokens / 1000) * tier_config["overage_per_1k_tokens"]

            total_cost = base_cost + overage_cost

            if total_cost < best_cost:
                best_cost = total_cost
                best_tier = tier_name

        return best_tier

    def _calculate_savings(
        self, current_tier: str, recommended_tier: str, monthly_tokens: int
    ) -> float:
        """Calculate potential savings from tier change."""

        if current_tier == recommended_tier:
            return 0

        current_config = self.PRICING_TIERS[current_tier]
        recommended_config = self.PRICING_TIERS[recommended_tier]

        # Current cost
        current_overage = max(0, monthly_tokens - current_config["included_tokens"])
        current_cost = current_config["monthly_cost"] + (
            (current_overage / 1000) * current_config["overage_per_1k_tokens"]
        )

        # Recommended cost
        recommended_overage = max(0, monthly_tokens - recommended_config["included_tokens"])
        recommended_cost = recommended_config["monthly_cost"] + (
            (recommended_overage / 1000) * recommended_config["overage_per_1k_tokens"]
        )

        return round(max(0, current_cost - recommended_cost), 2)
