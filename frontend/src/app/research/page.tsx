"use client";

import { useState, useEffect } from "react";
import { companiesApi, ingestionApi } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Search, Plus, Loader2, CheckCircle2, Building2 } from "lucide-react";
import Link from "next/link";

const SECTORS = [
  "All",
  "Technology",
  "Healthcare",
  "Financials",
  "Energy",
  "Consumer Discretionary",
  "Industrials",
  "Materials",
  "Communication Services",
  "Utilities",
  "Real Estate",
  "Consumer Staples",
];

export default function ResearchPage() {
  const [companies, setCompanies] = useState<Record<string, unknown>[]>([]);
  const [sector, setSector] = useState("All");
  const [searchTicker, setSearchTicker] = useState("");
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCompanies();
  }, [sector]);

  async function loadCompanies() {
    setLoading(true);
    try {
      const res = await companiesApi.list(sector === "All" ? undefined : sector);
      setCompanies(res.companies);
    } catch {
      setCompanies([]);
    }
    setLoading(false);
  }

  async function handleIngest() {
    if (!searchTicker.trim()) return;
    setIsIngesting(true);
    setIngestResult(null);
    try {
      const res = await ingestionApi.ingestTicker(searchTicker.trim().toUpperCase());
      setIngestResult(`${res.name || res.ticker} ingested successfully!`);
      // Reload after a short delay to show the new company
      setTimeout(() => {
        loadCompanies();
        setIngestResult(null);
      }, 2000);
    } catch (e) {
      setIngestResult("Ingestion failed. Check backend.");
      console.error(e);
    }
    setIsIngesting(false);
    setSearchTicker("");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Company Research</h1>
          <p className="text-sm text-muted-foreground">
            Browse researched companies or add new ones
          </p>
        </div>

        <div className="flex items-center gap-2">
          <input
            value={searchTicker}
            onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleIngest()}
            placeholder="AAPL"
            className="w-28 rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            onClick={handleIngest}
            disabled={isIngesting || !searchTicker.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2 text-sm font-medium text-white shadow-md transition-all hover:shadow-lg disabled:opacity-50"
          >
            {isIngesting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            Ingest
          </button>
        </div>
      </div>

      {/* Ingest Feedback */}
      {ingestResult && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-400">
          <CheckCircle2 className="h-4 w-4" />
          {ingestResult}
        </div>
      )}

      {/* Sector Filter */}
      <div className="flex flex-wrap gap-2">
        {SECTORS.map((s) => (
          <button
            key={s}
            onClick={() => setSector(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${sector === s
              ? "bg-gradient-to-r from-blue-600 to-violet-600 text-white"
              : "bg-muted text-muted-foreground hover:bg-accent"
              }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Companies Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : companies.length === 0 ? (
        <div className="py-12 text-center">
          <Search className="mx-auto h-12 w-12 text-muted-foreground/40" />
          <h3 className="mt-4 text-lg font-medium">No companies yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter a ticker above and click Ingest to start researching
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {companies.map((c) => (
            <Link
              key={c.ticker as string}
              href={`/research/${c.ticker}`}
              className="group rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/50 hover:shadow-lg hover:shadow-blue-500/5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-bold">{c.ticker as string}</h3>
                    {(c.has_research as boolean) && (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {(c.name as string) || (c.ticker as string)}
                  </p>
                </div>
                <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-medium">
                  {(c.sector as string) || "Unknown"}
                </span>
              </div>

              {c.market_cap ? (
                <div className="mt-3 flex items-center gap-4">
                  <div>
                    <p className="text-[10px] text-muted-foreground">
                      Market Cap
                    </p>
                    <p className="text-sm font-semibold">
                      {formatNumber(c.market_cap as number)}
                    </p>
                  </div>
                  {(c.fundamentals as Record<string, number>)?.pe_ratio && (
                    <div>
                      <p className="text-[10px] text-muted-foreground">P/E</p>
                      <p className="text-sm font-semibold">
                        {(
                          c.fundamentals as Record<string, number>
                        ).pe_ratio.toFixed(1)}
                      </p>
                    </div>
                  )}
                  {(c.fundamentals as Record<string, number>)
                    ?.profit_margin != null && (
                      <div>
                        <p className="text-[10px] text-muted-foreground">
                          Margin
                        </p>
                        <p className="text-sm font-semibold">
                          {(
                            ((c.fundamentals as Record<string, number>)
                              .profit_margin || 0) * 100
                          ).toFixed(1)}
                          %
                        </p>
                      </div>
                    )}
                </div>
              ) : (
                <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                  <Building2 className="h-3.5 w-3.5" />
                  Click to view details
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
