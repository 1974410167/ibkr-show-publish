from app.domains.performance.cashflow_classifier import AccountCashFlowClassifier


def test_deposit_and_withdrawal_are_external_cashflows() -> None:
    classifier = AccountCashFlowClassifier()

    result = classifier.classify_daily_external_cashflows(
        [
            {
                "flow_type": "Deposits/Withdrawals",
                "flow_direction": "deposit",
                "settle_date": "2026-01-02",
                "amount_in_base": 100.0,
            },
            {
                "flow_type": "Deposits/Withdrawals",
                "flow_direction": "withdrawal",
                "settle_date": "2026-01-02",
                "amount_in_base": 20.0,
            },
        ]
    )

    assert result.net_flows_by_date == {"2026-01-02": 80.0}


def test_buy_sell_stock_are_not_external_cashflows() -> None:
    classifier = AccountCashFlowClassifier()

    records = [
        {"flow_type": "Trade", "description": "BUY AAPL", "settle_date": "2026-01-02", "amount": -100.0},
        {"flow_type": "Trade", "description": "SELL MSFT", "settle_date": "2026-01-03", "amount": 120.0},
    ]
    result = classifier.classify_daily_external_cashflows(records)

    assert result.net_flows_by_date == {}


def test_dividend_and_interest_are_not_external_cashflows() -> None:
    classifier = AccountCashFlowClassifier()

    records = [
        {"flow_type": "Dividend", "description": "Dividend AAPL", "settle_date": "2026-01-02", "amount": 1.0},
        {"flow_type": "Interest", "description": "Broker interest", "settle_date": "2026-01-03", "amount": 2.0},
    ]
    result = classifier.classify_daily_external_cashflows(records)

    assert result.net_flows_by_date == {}


def test_transfer_description_can_be_external_cashflow() -> None:
    classifier = AccountCashFlowClassifier()

    result = classifier.classify_daily_external_cashflows(
        [{"description": "Transfer out", "date_time": "2026-01-02T12:00:00", "amount": -50.0}]
    )

    assert result.net_flows_by_date == {"2026-01-02": -50.0}
