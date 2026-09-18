from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.collections import Investment


ACCRUAL_INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours
CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


@dataclass(frozen=True)
class AccrualState:
    base_profit: Decimal
    expected_profit: Decimal
    accrued_profit: Decimal
    completed_periods: int
    total_periods: int
    next_accrual_at: datetime | None
    withdrawable_profit: Decimal
    withdrawable_amount: Decimal


def calculate_base_profit(investment: Investment) -> Decimal:
    amount = money(investment.amount)
    rate = money(investment.rate)

    return (amount * rate / HUNDRED).quantize(CENT)


def calculate_expected_profit(investment: Investment) -> Decimal:
    return (
        calculate_base_profit(investment)
        + money(investment.additional_profit)
    ).quantize(CENT)


def calculate_total_active_seconds(
    investment: Investment,
) -> int:
    """
    Calculate the original active investment duration.

    Because resume_investment extends maturity_date by the
    paused duration, maturity_date - date includes the pauses.
    We remove total_paused_seconds to recover actual active time.
    """
    if investment.date is None or investment.maturity_date is None:
        return 0

    total_duration = int(
        (
            investment.maturity_date
            - investment.date
        ).total_seconds()
    )

    paused_seconds = max(
        0,
        int(investment.total_paused_seconds or 0),
    )

    return max(
        0,
        total_duration - paused_seconds,
    )


def calculate_active_elapsed_seconds(
    investment: Investment,
    now: datetime,
) -> int:
    """
    Calculate how much active time has elapsed.

    Current pause time is excluded as well as all previously
    completed pause durations.
    """
    if investment.date is None:
        return 0

    elapsed = int(
        (
            now - investment.date
        ).total_seconds()
    )

    elapsed -= max(
        0,
        int(investment.total_paused_seconds or 0),
    )

    # If currently paused, exclude the current pause interval.
    if investment.paused_at is not None:
        elapsed -= max(
            0,
            int(
                (
                    now - investment.paused_at
                ).total_seconds()
            ),
        )

    total_active_seconds = calculate_total_active_seconds(
        investment
    )

    return max(
        0,
        min(
            elapsed,
            total_active_seconds,
        ),
    )


def calculate_total_periods(
    investment: Investment,
) -> int:
    """
    Number of complete 6-hour accrual periods in the
    investment's active duration.

    A remainder shorter than 6 hours is handled at maturity,
    where accrued profit is forced to the full expected profit.
    """
    active_seconds = calculate_total_active_seconds(
        investment
    )

    if active_seconds <= 0:
        return 0

    return active_seconds // ACCRUAL_INTERVAL_SECONDS


def calculate_completed_periods(
    investment: Investment,
    now: datetime,
) -> int:
    total_periods = calculate_total_periods(
        investment
    )

    if total_periods <= 0:
        return 0

    status = (investment.status or "").lower()

    if (
        investment.withdrawaled
        or status == "completed"
    ):
        return total_periods

    # Once maturity is reached, all profit is considered accrued.
    if (
        investment.maturity_date is not None
        and now >= investment.maturity_date
        and investment.paused_at is None
    ):
        return total_periods

    elapsed_seconds = calculate_active_elapsed_seconds(
        investment,
        now,
    )

    return min(
        total_periods,
        elapsed_seconds // ACCRUAL_INTERVAL_SECONDS,
    )


def calculate_next_accrual_at(
    investment: Investment,
    completed_periods: int,
    now: datetime,
) -> datetime | None:
    if (
        investment.date is None
        or investment.paused_at is not None
    ):
        return None

    total_periods = calculate_total_periods(
        investment
    )

    if (
        total_periods <= 0
        or completed_periods >= total_periods
    ):
        return None

    historical_pause_seconds = max(
        0,
        int(investment.total_paused_seconds or 0),
    )

    target_seconds = (
        (completed_periods + 1)
        * ACCRUAL_INTERVAL_SECONDS
    )

    next_at = (
        investment.date
        + timedelta(
            seconds=(
                target_seconds
                + historical_pause_seconds
            )
        )
    )

    if next_at <= now:
        return now

    return next_at


def preview_accrual(
    investment: Investment,
    now: datetime | None = None,
) -> AccrualState:
    """
    Calculate the current accrual without modifying the database.

    This is safe to use from GET endpoints.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    base_profit = calculate_base_profit(
        investment
    )

    expected_profit = calculate_expected_profit(
        investment
    )

    total_periods = calculate_total_periods(
        investment
    )

    completed_periods = calculate_completed_periods(
        investment,
        now,
    )

    stored_periods = max(
        0,
        int(investment.accrued_periods or 0),
    )

    stored_accrued_profit = money(
        investment.accrued_profit
    )

    completed_periods = max(
        stored_periods,
        completed_periods,
    )

    # Already matured/fully accrued.
    if (
        total_periods > 0
        and completed_periods >= total_periods
    ):
        accrued_profit = expected_profit

    # No new completed periods since last checkpoint.
    elif completed_periods <= stored_periods:
        accrued_profit = stored_accrued_profit

    else:
        newly_completed_periods = (
            completed_periods - stored_periods
        )

        remaining_periods = (
            total_periods - stored_periods
        )

        remaining_profit = max(
            Decimal("0"),
            expected_profit - stored_accrued_profit,
        )

        if remaining_periods <= 0:
            increment = Decimal("0.00")
        else:
            increment = (
                remaining_profit
                * Decimal(newly_completed_periods)
                / Decimal(remaining_periods)
            ).quantize(CENT)

        accrued_profit = (
            stored_accrued_profit + increment
        ).quantize(CENT)

    accrued_profit = min(
        accrued_profit,
        expected_profit,
    )

    status = (investment.status or "").lower()

    is_matured = (
        investment.maturity_date is not None
        and now >= investment.maturity_date
        and investment.paused_at is None
    )

    is_claimable = (
        is_matured
        and not investment.withdrawaled
        and status != "completed"
        and status != "paused"
    )

    if is_claimable:
        withdrawable_profit = expected_profit
        withdrawable_amount = (
            money(investment.amount)
            + expected_profit
        ).quantize(CENT)
    else:
        withdrawable_profit = Decimal("0.00")
        withdrawable_amount = Decimal("0.00")

    next_accrual_at = calculate_next_accrual_at(
        investment,
        completed_periods,
        now,
    )

    return AccrualState(
        base_profit=base_profit,
        expected_profit=expected_profit,
        accrued_profit=accrued_profit,
        completed_periods=completed_periods,
        total_periods=total_periods,
        next_accrual_at=next_accrual_at,
        withdrawable_profit=withdrawable_profit,
        withdrawable_amount=withdrawable_amount,
    )


def settle_accrual(
    investment: Investment,
    now: datetime | None = None,
) -> AccrualState:
    """
    Calculate and persist the latest accrual checkpoint.

    Use this from state-changing operations such as:
    - ROI adjustment
    - pause
    - resume
    - claim
    """
    state = preview_accrual(
        investment,
        now,
    )

    investment.accrued_profit = (
        state.accrued_profit
    )

    investment.accrued_periods = (
        state.completed_periods
    )

    return state
