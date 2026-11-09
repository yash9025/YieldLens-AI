export const MOCK_DATES = [
  {
    date: "2022-03-16",
    label: "March 16, 2022 — Fed Liftoff (+25 bps)",
    event: "First Rate Hike of the 2022-2023 Cycle",
    brief: {
      date: "2022-03-16",
      mode: "HYBRID",
      summary: "Treasury yields rose following the FOMC announcement to raise the policy rate target by 25 bps to 0.25%-0.50%, with the 2-year yield surging 9.0 bps.",
      sentences: [
        {
          id: "s1",
          text: "The 2-year Treasury yield rose 9.0 bps to 1.94% on March 16.",
          section: "market_moves",
          fact_ids: ["DGS2_daily_2022-03-16", "DGS2_level_2022-03-16"],
          chunk_ids: [101],
          uncertainty: null,
          verdict: "SUPPORTED",
          issues: [],
          evidence: {
            facts: [
              {
                id: "DGS2_daily_2022-03-16",
                series: "2-Year Treasury",
                value: "+9.0 bps",
                formula: "DGS2[2022-03-16](1.94%) - DGS2[2022-03-15](1.85%) = +0.0900% = +9.0 bps",
                source: "FRED (DGS2)",
                url: "https://fred.stlouisfed.org/series/DGS2",
                validated: true
              },
              {
                id: "DGS2_level_2022-03-16",
                series: "2-Year Treasury Level",
                value: "1.94%",
                formula: "Closing yield: 1.9400%",
                source: "FRED (DGS2)",
                url: "https://fred.stlouisfed.org/series/DGS2",
                validated: true
              }
            ],
            chunks: [
              {
                id: 101,
                doc_type: "STATEMENT",
                meeting_date: "2022-03-16",
                pub_datetime: "2022-03-16T18:00:00Z",
                source_url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
                text: "The Committee decided to raise the target range for the federal funds rate to 1/4 to 1/2 percent and anticipates that ongoing increases in the target range will be appropriate. In addition, the Committee expects to begin reducing its holdings of Treasury securities and agency debt and agency mortgage-backed securities at a coming meeting."
              }
            ]
          }
        },
        {
          id: "s2",
          text: "The 10-year Treasury yield rose 4.0 bps to 2.19%, flattening the 10Y-2Y curve spread to 25.0 bps.",
          section: "market_moves",
          fact_ids: ["DGS10_daily_2022-03-16", "DGS10_DGS2_spread_2022-03-16"],
          chunk_ids: [101],
          uncertainty: null,
          verdict: "SUPPORTED",
          issues: [],
          evidence: {
            facts: [
              {
                id: "DGS10_daily_2022-03-16",
                series: "10-Year Treasury",
                value: "+4.0 bps",
                formula: "DGS10[2022-03-16](2.19%) - DGS10[2022-03-15](2.15%) = +0.0400% = +4.0 bps",
                source: "FRED (DGS10)",
                url: "https://fred.stlouisfed.org/series/DGS10",
                validated: true
              },
              {
                id: "DGS10_DGS2_spread_2022-03-16",
                series: "10Y-2Y Curve Spread",
                value: "+25.0 bps",
                formula: "DGS10(2.19%) - DGS2(1.94%) = +0.2500% = +25.0 bps",
                source: "FRED (T10Y2Y)",
                url: "https://fred.stlouisfed.org/series/T10Y2Y",
                validated: true
              }
            ],
            chunks: [
              {
                id: 101,
                doc_type: "STATEMENT",
                meeting_date: "2022-03-16",
                pub_datetime: "2022-03-16T18:00:00Z",
                source_url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
                text: "Inflation remains elevated, reflecting supply and demand imbalances related to the pandemic, higher energy prices, and broader price pressures."
              }
            ]
          }
        },
        {
          id: "s3",
          text: "In its official post-meeting statement, the FOMC announced an increase in the federal funds target range from 0%-0.25% to 0.25%-0.50%.",
          section: "fed_context",
          fact_ids: [],
          chunk_ids: [101],
          uncertainty: null,
          verdict: "SUPPORTED",
          issues: [],
          evidence: {
            facts: [],
            chunks: [
              {
                id: 101,
                doc_type: "STATEMENT",
                meeting_date: "2022-03-16",
                pub_datetime: "2022-03-16T18:00:00Z",
                source_url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
                text: "The Committee decided to raise the target range for the federal funds rate to 1/4 to 1/2 percent and anticipates that ongoing increases in the target range will be appropriate."
              }
            ]
          }
        },
        {
          id: "s4",
          text: "The Committee indicated that ongoing increases in the target range will be appropriate, signalling aggressive tightening ahead.",
          section: "fed_context",
          fact_ids: [],
          chunk_ids: [101],
          uncertainty: null,
          verdict: "PARTIAL",
          issues: ["'Aggressive tightening' is an analyst characterization not present in official statement text."],
          evidence: {
            facts: [],
            chunks: [
              {
                id: 101,
                doc_type: "STATEMENT",
                meeting_date: "2022-03-16",
                pub_datetime: "2022-03-16T18:00:00Z",
                source_url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
                text: "...anticipates that ongoing increases in the target range will be appropriate. In addition, the Committee expects to begin reducing its holdings..."
              }
            ]
          }
        },
        {
          id: "s5",
          text: "While short-dated yields rose after the statement release, the evidence establishes temporal sequence rather than isolated causal determination.",
          section: "uncertainty_flags",
          fact_ids: [],
          chunk_ids: [101],
          uncertainty: "Causality qualification: Oil price volatility from geopolitical tension coincided with the FOMC release.",
          verdict: "UNCERTAIN",
          issues: ["Explicit uncertainty acknowledgment: confounding geopolitical oil supply shock."],
          evidence: {
            facts: [],
            chunks: [
              {
                id: 101,
                doc_type: "STATEMENT",
                meeting_date: "2022-03-16",
                pub_datetime: "2022-03-16T18:00:00Z",
                source_url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
                text: "The invasion of Ukraine by Russia is causing tremendous human and economic hardship. The implications for the U.S. economy are highly uncertain..."
              }
            ]
          }
        }
      ]
    }
  },
  {
    date: "2023-10-19",
    label: "October 19, 2023 — 10Y Yield Peaks Above 5.0%",
    event: "Benchmark 10-Year Crosses Multi-Decade High",
    brief: {
      date: "2023-10-19",
      mode: "HYBRID",
      summary: "The 10-year Treasury yield crossed the 5.0% threshold for the first time in 16 years, rising 8.0 bps on October 19 amid heavy issuance and term premium expansion.",
      sentences: [
        {
          id: "s1",
          text: "The 10-year Treasury yield rose 8.0 bps to 4.99% (intraday high above 5.00%) on October 19.",
          section: "market_moves",
          fact_ids: ["DGS10_daily_2023-10-19", "DGS10_level_2023-10-19"],
          chunk_ids: [201],
          uncertainty: null,
          verdict: "SUPPORTED",
          issues: [],
          evidence: {
            facts: [
              {
                id: "DGS10_daily_2023-10-19",
                series: "10-Year Treasury",
                value: "+8.0 bps",
                formula: "DGS10[2023-10-19](4.99%) - DGS10[2023-10-18](4.91%) = +0.0800% = +8.0 bps",
                source: "FRED (DGS10)",
                url: "https://fred.stlouisfed.org/series/DGS10",
                validated: true
              }
            ],
            chunks: []
          }
        },
        {
          id: "s2",
          text: "Federal Reserve Chair Powell delivered remarks at the Economic Club of New York noting that higher bond yields were contributing to financial tightening.",
          section: "fed_context",
          fact_ids: [],
          chunk_ids: [201],
          uncertainty: null,
          verdict: "SUPPORTED",
          issues: [],
          evidence: {
            facts: [],
            chunks: [
              {
                id: 201,
                doc_type: "SPEECH",
                meeting_date: "2023-10-19",
                pub_datetime: "2023-10-19T16:00:00Z",
                source_url: "https://www.federalreserve.gov/newsevents/speech/powell20231019a.htm",
                text: "A range of factors may be driving this run-up, including term premiums. Financial conditions have tightened significantly in recent months, and longer-term bond yields have been an important driving engine."
              }
            ]
          }
        },
        {
          id: "s3",
          text: "The rise in yields was caused by market panic over the federal debt deficit.",
          section: "uncertainty_flags",
          fact_ids: [],
          chunk_ids: [],
          uncertainty: "Causal overreach detected.",
          verdict: "UNSUPPORTED",
          issues: [
            "Causal language 'caused by' is unsubstantiated by official documents.",
            "No fact_ids or chunk_ids provided supporting 'market panic'."
          ],
          evidence: {
            facts: [],
            chunks: []
          }
        }
      ]
    }
  }
];

export const MOCK_FACTS_SUMMARY = [
  { series: "Federal Funds Effective Rate (DFF)", level: "5.33%", daily_change: "0.0 bps", weekly_change: "0.0 bps", ytd_change: "+90.0 bps", source_url: "https://fred.stlouisfed.org/series/DFF" },
  { series: "2-Year Treasury Yield (DGS2)", level: "4.88%", daily_change: "+4.0 bps", weekly_change: "+12.0 bps", ytd_change: "+46.0 bps", source_url: "https://fred.stlouisfed.org/series/DGS2" },
  { series: "5-Year Treasury Yield (DGS5)", level: "4.52%", daily_change: "+6.0 bps", weekly_change: "+15.0 bps", ytd_change: "+52.0 bps", source_url: "https://fred.stlouisfed.org/series/DGS5" },
  { series: "10-Year Treasury Yield (DGS10)", level: "4.63%", daily_change: "+7.0 bps", weekly_change: "+18.0 bps", ytd_change: "+75.0 bps", source_url: "https://fred.stlouisfed.org/series/DGS10" },
  { series: "30-Year Treasury Yield (DGS30)", level: "4.78%", daily_change: "+8.0 bps", weekly_change: "+21.0 bps", ytd_change: "+81.0 bps", source_url: "https://fred.stlouisfed.org/series/DGS30" },
  { series: "10Y-2Y Spread (T10Y2Y)", level: "-25.0 bps", daily_change: "+3.0 bps", weekly_change: "+6.0 bps", ytd_change: "+29.0 bps", source_url: "https://fred.stlouisfed.org/series/T10Y2Y" },
];

