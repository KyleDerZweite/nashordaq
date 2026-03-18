import { useState } from "react";
import { useBankSummary, useBorrowFromBank, useRepayBankDebt } from "../api";
import { formatAmount, formatLocalDateTime } from "../utils/format";

interface Props {
  canManageBank: boolean;
  gambaEnabled?: boolean;
  onClose: () => void;
}

export default function BankModal({
  canManageBank,
  gambaEnabled = true,
  onClose,
}: Props) {
  const [repayAmount, setRepayAmount] = useState("");
  const { data, isLoading, isError, error } = useBankSummary(canManageBank);
  const borrowFromBank = useBorrowFromBank();
  const repayBankDebt = useRepayBankDebt();

  const parsedRepayAmount = Number(repayAmount);
  const canSubmitBorrow =
    canManageBank &&
    Boolean(data?.rescue_loan_available) &&
    !borrowFromBank.isPending;
  const canSubmitRepay =
    canManageBank &&
    Number.isFinite(parsedRepayAmount) &&
    parsedRepayAmount > 0 &&
    parsedRepayAmount <=
      Math.min(data?.cash_balance ?? 0, data?.debt_outstanding ?? 0) &&
    !repayBankDebt.isPending;

  function handleBorrowSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmitBorrow || !data) {
      return;
    }

    borrowFromBank.mutate({ amount: data.rescue_loan_amount });
  }

  function handleRepaySubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmitRepay) {
      return;
    }

    repayBankDebt.mutate(
      { amount: parsedRepayAmount },
      { onSuccess: () => setRepayAmount("") },
    );
  }

  const maxRepayAmount = Math.min(
    data?.cash_balance ?? 0,
    data?.debt_outstanding ?? 0,
  );
  const interestCadenceLabel = data
    ? `Failsafe debt opens with ${(data.rescue_loan_interest_rate * 100).toFixed(2)}% interest, then rolls every ${data.interest_interval_hours.toFixed(0)} hours`
    : "Failsafe debt opens with interest, then follows the regular rollover schedule";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/80"
      onClick={onClose}
    >
      <section
        className="w-full max-w-3xl border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b-4 border-hex-gold px-5 py-3">
          <div>
            <h2 className="font-serif text-xl font-bold text-hex-gold">
              Failsafe Bank
            </h2>
            <p className="mt-1 font-mono text-xs uppercase tracking-[0.18em] text-hex-bronze">
              {interestCadenceLabel}
            </p>
          </div>
          <button
            onClick={onClose}
            className="border-2 border-hex-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-bronze transition-colors hover:border-hex-white hover:text-hex-white"
          >
            Close
          </button>
        </div>

        <div className="px-5 py-4">
          {!canManageBank && (
            <p className="font-mono text-sm text-hex-bronze">
              Complete onboarding as a player to unlock rescue debt and
              repayment.
            </p>
          )}

          {canManageBank && isLoading && (
            <p className="font-mono text-sm text-hex-bronze">
              Loading bank account...
            </p>
          )}

          {canManageBank && isError && (
            <p className="font-mono text-sm text-hex-zaun">{error.message}</p>
          )}

          {canManageBank && data && (
            <div className="space-y-5">
              <div className="grid gap-3 md:grid-cols-4">
                {[
                  {
                    label: "Failsafe",
                    value: `${formatAmount(data.rescue_loan_amount)} P`,
                  },
                  {
                    label: "Net Worth Gate",
                    value: `${formatAmount(data.rescue_net_worth_threshold)} P`,
                  },
                  {
                    label: "Outstanding",
                    value: `${formatAmount(data.debt_outstanding)} P`,
                  },
                  {
                    label: "Next Charge",
                    value: `${formatAmount(data.next_interest_amount)} P`,
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="border border-hex-border bg-hex-bg-alt px-3 py-2"
                  >
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                      {item.label}
                    </div>
                    <div className="mt-1 font-mono text-sm font-bold text-hex-white">
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2 border border-hex-border px-4 py-3">
                  <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                    Rescue Rules
                  </h3>
                  <p className="font-mono text-xs text-hex-bronze">
                    Principal: {formatAmount(data.debt_principal)} P
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Accrued interest: {formatAmount(data.debt_accrued_interest)}{" "}
                    P
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Holdings mark: {formatAmount(data.holdings_value)} P
                  </p>
                  {gambaEnabled && (
                    <p className="font-mono text-xs text-hex-bronze">
                      Active Gamba mark: {formatAmount(data.active_gamba_value)}{" "}
                      P
                    </p>
                  )}
                  <p className="font-mono text-xs text-hex-bronze">
                    Cash available: {formatAmount(data.cash_balance)} P
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Unlocks once debt-adjusted net worth falls to{" "}
                    {formatAmount(data.rescue_net_worth_threshold)} P or below
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Uses remaining: {data.rescue_loan_uses_remaining}
                  </p>
                </div>

                <div className="space-y-2 border border-hex-border px-4 py-3">
                  <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                    Rescue Terms
                  </h3>
                  <p className="font-mono text-xs text-hex-bronze">
                    Rescue rate:{" "}
                    {(data.interest_rate_per_interval * 100).toFixed(2)}% /{" "}
                    {data.interest_interval_hours.toFixed(0)}h
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Opening charge:{" "}
                    {formatAmount(data.rescue_loan_upfront_interest_amount)} P
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Next accrual:{" "}
                    {data.next_interest_accrual_at
                      ? formatLocalDateTime(data.next_interest_accrual_at)
                      : "--"}
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Estimated next charge:{" "}
                    {formatAmount(data.next_interest_amount)} P
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Current net worth:{" "}
                    {formatAmount(data.debt_adjusted_net_worth)} P
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    {data.rescue_loan_available
                      ? "Failsafe is ready to claim."
                      : (data.rescue_loan_block_reason ??
                        "Failsafe is currently unavailable.")}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <form
                  onSubmit={handleBorrowSubmit}
                  className="space-y-3 border border-hex-border px-4 py-4"
                >
                  <div>
                    <h3 className="font-serif text-lg font-bold text-hex-gold">
                      Claim Failsafe
                    </h3>
                    <p className="mt-1 font-mono text-xs text-hex-bronze">
                      This is a one-time rescue. Cash lands instantly and the
                      opening interest is added right away. Once spent, an admin
                      has to restore it before it can be claimed again.
                    </p>
                  </div>
                  <div className="space-y-2 border border-hex-border bg-hex-bg-alt px-3 py-3">
                    <p className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
                      Rescue Package
                    </p>
                    <p className="font-mono text-sm font-bold text-hex-white">
                      {formatAmount(data.rescue_loan_amount)} P cash
                    </p>
                    <p className="font-mono text-xs text-hex-bronze">
                      Immediate charge:{" "}
                      {formatAmount(data.rescue_loan_upfront_interest_amount)} P
                    </p>
                    <p className="font-mono text-xs text-hex-bronze">
                      Availability:{" "}
                      {data.rescue_loan_available ? "Ready" : "Locked"}
                    </p>
                    <p className="font-mono text-xs text-hex-bronze">
                      Uses left: {data.rescue_loan_uses_remaining}
                    </p>
                  </div>
                  {borrowFromBank.isError && (
                    <p className="font-mono text-xs text-hex-zaun">
                      {borrowFromBank.error.message}
                    </p>
                  )}
                  <button
                    type="submit"
                    disabled={!canSubmitBorrow}
                    className={`w-full border-2 py-2 font-mono text-xs font-bold uppercase tracking-[0.18em] transition-colors ${
                      canSubmitBorrow
                        ? "border-hex-zaun text-hex-zaun hover:bg-hex-zaun hover:text-hex-bg"
                        : "cursor-not-allowed border-hex-border text-hex-border"
                    }`}
                  >
                    {borrowFromBank.isPending
                      ? "Claiming..."
                      : "Claim Failsafe"}
                  </button>
                </form>

                <form
                  onSubmit={handleRepaySubmit}
                  className="space-y-3 border border-hex-border px-4 py-4"
                >
                  <div>
                    <h3 className="font-serif text-lg font-bold text-hex-gold">
                      Repay
                    </h3>
                    <p className="mt-1 font-mono text-xs text-hex-bronze">
                      Payments clear accrued interest first, then principal.
                    </p>
                  </div>
                  <div>
                    <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
                      Amount
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={repayAmount}
                        onChange={(e) => setRepayAmount(e.target.value)}
                        className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setRepayAmount(
                            maxRepayAmount > 0 ? maxRepayAmount.toFixed(2) : "",
                          )
                        }
                        disabled={maxRepayAmount <= 0}
                        className={`shrink-0 border-2 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                          maxRepayAmount > 0
                            ? "border-hex-gold text-hex-gold hover:bg-hex-gold hover:text-hex-bg"
                            : "cursor-not-allowed border-hex-border text-hex-border"
                        }`}
                      >
                        Max
                      </button>
                    </div>
                    <p className="mt-2 font-mono text-xs text-hex-bronze">
                      Repayable now: {formatAmount(maxRepayAmount)} P
                    </p>
                  </div>
                  {repayBankDebt.isError && (
                    <p className="font-mono text-xs text-hex-zaun">
                      {repayBankDebt.error.message}
                    </p>
                  )}
                  <button
                    type="submit"
                    disabled={!canSubmitRepay}
                    className={`w-full border-2 py-2 font-mono text-xs font-bold uppercase tracking-[0.18em] transition-colors ${
                      canSubmitRepay
                        ? "border-hex-magic text-hex-magic hover:bg-hex-magic hover:text-hex-bg"
                        : "cursor-not-allowed border-hex-border text-hex-border"
                    }`}
                  >
                    {repayBankDebt.isPending ? "Repaying..." : "Repay Debt"}
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
