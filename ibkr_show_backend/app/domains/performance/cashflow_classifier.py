from collections import defaultdict
from dataclasses import dataclass


EXTERNAL_CASH_FLOW_TYPE = "Deposits/Withdrawals"
EXTERNAL_DESCRIPTION_KEYWORDS = (
    "deposit",
    "withdrawal",
    "withdraw",
    "transfer in",
    "transfer out",
    "cash transfer",
)
NON_EXTERNAL_FLOW_KEYWORDS = (
    "buy",
    "sell",
    "dividend",
    "interest",
    "commission",
    "fee",
    "realized pnl",
    "unrealized pnl",
    "fx translation",
)


@dataclass(frozen=True)
class CashFlowClassificationResult:
    net_flows_by_date: dict[str, float]
    data_limitations: list[str]


class AccountCashFlowClassifier:
    def classify_daily_external_cashflows(self, records: list[dict]) -> CashFlowClassificationResult:
        net_flows: dict[str, float] = defaultdict(float)
        limitations: list[str] = []
        skipped_uncertain = False

        for record in records:
            if not self.is_external_cashflow(record):
                if self._is_uncertain_cash_movement(record):
                    skipped_uncertain = True
                continue

            effective_date = self.effective_date(record)
            if not effective_date:
                limitations.append("cashflow_missing_effective_date")
                continue

            amount = self.normalized_amount(record)
            if amount is None:
                limitations.append("cashflow_missing_amount")
                continue
            net_flows[effective_date] += amount

        if skipped_uncertain:
            limitations.append("cashflow_classification_incomplete")

        return CashFlowClassificationResult(
            net_flows_by_date={key: round(value, 6) for key, value in sorted(net_flows.items())},
            data_limitations=_dedupe(limitations),
        )

    def is_external_cashflow(self, record: dict) -> bool:
        flow_type = str(record.get("flow_type") or "").strip().lower()
        description = str(record.get("description") or "").strip().lower()
        flow_direction = str(record.get("flow_direction") or "").strip().lower()

        if flow_type == EXTERNAL_CASH_FLOW_TYPE.lower():
            return True
        if any(keyword in description for keyword in NON_EXTERNAL_FLOW_KEYWORDS):
            return False
        if flow_direction in {"deposit", "withdrawal"}:
            return True
        return any(keyword in description for keyword in EXTERNAL_DESCRIPTION_KEYWORDS)

    def effective_date(self, record: dict) -> str | None:
        for field in ("settle_date", "report_date", "available_for_trading_date", "date_time"):
            value = record.get(field)
            if not value:
                continue
            return str(value).split("T", 1)[0]
        return None

    def normalized_amount(self, record: dict) -> float | None:
        raw = record.get("amount_in_base")
        if raw is None:
            raw = record.get("amount")
        if raw is None:
            return None
        amount = float(raw)
        direction = str(record.get("flow_direction") or "").strip().lower()
        if direction == "withdrawal" and amount > 0:
            return -amount
        if direction == "deposit" and amount < 0:
            return abs(amount)
        return amount

    def _is_uncertain_cash_movement(self, record: dict) -> bool:
        text = " ".join(
            str(record.get(field) or "").lower()
            for field in ("flow_type", "description", "transaction_type", "type")
        )
        if not text:
            return False
        if any(keyword in text for keyword in NON_EXTERNAL_FLOW_KEYWORDS):
            return False
        return "cash" in text and not self.is_external_cashflow(record)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
