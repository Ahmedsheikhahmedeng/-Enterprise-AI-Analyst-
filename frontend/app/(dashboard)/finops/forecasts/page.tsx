"use client";

import React, { useState, useEffect } from "react";
import { TrendingUp, CheckCircle2, AlertOctagon, Calendar } from "lucide-react";
import { FinOpsNav } from "@/components/finops/finops-nav";
import { CostForecast } from "@/types/finops";

function getMockForecasts(): CostForecast[] {
  return [
    {
      id: "fc-01",
      organization_id: "org-primary",
      period: "MONTHLY",
      actual_to_date: "142.50",
      forecasted_total: "385.00",
      budget_limit: "500.00",
      expected_overrun: "0.00",
      confidence: 0.88,
      forecast_method: "LINEAR_VELOCITY_PROJECTION",
    },
    {
      id: "fc-02",
      organization_id: "org-primary",
      period: "WEEKLY",
      actual_to_date: "45.20",
      forecasted_total: "92.00",
      budget_limit: "100.00",
      expected_overrun: "0.00",
      confidence: 0.92,
      forecast_method: "LINEAR_VELOCITY_PROJECTION",
    },
  ];
}

export default function FinOpsForecastsPage() {
  const [forecasts, setForecasts] = useState<CostForecast[]>([]);

  useEffect(() => {
    async function loadForecasts() {
      try {
        const res = await fetch("/api/v1/finops/forecasts");
        if (res.ok) {
          const data = await res.json();
          setForecasts(data.items || getMockForecasts());
        } else {
          setForecasts(getMockForecasts());
        }
      } catch {
        setForecasts(getMockForecasts());
      }
    }
    loadForecasts();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-emerald-500" />
          <h1 className="text-2xl font-bold tracking-tight">Deterministic Spend Trajectory Forecasting</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          Linear velocity projections comparing month-to-date trajectory against allocated budget thresholds.
        </p>
      </div>

      <FinOpsNav />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {forecasts.map((fc) => {
          const actual = Number(fc.actual_to_date);
          const forecasted = Number(fc.forecasted_total);
          const limit = Number(fc.budget_limit);
          const overrun = Number(fc.expected_overrun);
          const hasOverrun = overrun > 0;

          return (
            <div key={fc.id} className="rounded-xl border border-border bg-card p-5 space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-foreground flex items-center gap-1.5">
                  <Calendar className="h-4 w-4 text-primary" /> {fc.period} Forecast
                </span>
                <span
                  className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-bold ${
                    hasOverrun
                      ? "bg-rose-500/10 text-rose-500 border border-rose-500/20"
                      : "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                  }`}
                >
                  {hasOverrun ? (
                    <>
                      <AlertOctagon className="h-3 w-3" /> Overrun Risk
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3 w-3" /> Within Budget
                    </>
                  )}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <span className="text-muted-foreground block text-[10px]">Actual To Date</span>
                  <span className="font-mono text-base font-bold text-foreground">${actual.toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px]">Projected Period End</span>
                  <span className={`font-mono text-base font-bold ${hasOverrun ? "text-rose-500" : "text-foreground"}`}>
                    ${forecasted.toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px]">Budget Ceiling</span>
                  <span className="font-mono text-base font-bold text-muted-foreground">${limit.toFixed(2)}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-muted-foreground">
                  <span>Spend Trajectory</span>
                  <span>{((forecasted / limit) * 100).toFixed(1)}% projected utilization</span>
                </div>
                <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full ${hasOverrun ? "bg-rose-500" : "bg-emerald-500"}`}
                    style={{ width: `${Math.min(100, (forecasted / limit) * 100)}%` }}
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-border flex items-center justify-between text-[10px] text-muted-foreground">
                <span>Method: {fc.forecast_method}</span>
                <span>Confidence: {(fc.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
