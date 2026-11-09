# YieldLens AI — Policy Language Annotation Guide & Taxonomy

**Document Version**: 1.0  
**Target Domain**: Federal Open Market Committee (FOMC) statements, minutes, and press conferences.

---

## 1. Overview & Business Problem

Automated market commentary engines must distinguish between shifts in policy stance (hawkish vs. dovish), explicit forward guidance, balance sheet operations, and interest rate decisions. Pre-trained general LLMs often conflate descriptive macroeconomic commentary with directional monetary policy stance.

This annotation guide establishes a rigorous multi-label annotation scheme for training and benchmarking:
1. A deterministic & TF-IDF baseline classifier.
2. A fine-tuned transformer (`distilbert-base-uncased`).

---

## 2. Label Taxonomy

Each FOMC sentence can carry **zero, one, or multiple** labels from the following mutually inclusive set:

| Label | Description | Diagnostic Criteria | Examples |
|---|---|---|---|
| `HAWKISH` | Signals tightening of monetary policy, upside inflation concerns, or above-target pressure. | Mentions inflation persistence, need for rate increases, restrictive stance, or labor market tightness risking wage-price spirals. | *"The Committee remains highly attentive to inflation risks."*<br>*"Additional policy firming may be appropriate."* |
| `DOVISH` | Signals accommodative monetary policy, downside growth/labor concerns, or readiness to ease. | Mentions labor market softening, downside risks to economic activity, downside inflation risks, or policy accommodation. | *"The Committee will act as appropriate to sustain the economic expansion."*<br>*"Job growth has slowed, and unemployment has edged up."* |
| `NEUTRAL` | Factual or descriptive reporting of economic indicators without directional policy bias. | Highlighting data releases without characterizing policy posture or future rate paths. | *"Economic activity expanded at a moderate pace in the third quarter."*<br>*"Consumer spending continued to advance."* |
| `FORWARD_GUIDANCE` | Explicit verbal commitments or conditionality regarding the future path of interest rates. | Uses conditional phrases ("until", "patient", "data-dependent", "expects to maintain", "anticipates"). | *"The Committee anticipates that ongoing increases in the target range will be appropriate."*<br>*"The stance remains data-dependent."* |
| `BALANCE_SHEET` | Quantitative easing (QE), quantitative tightening (QT), asset purchases, or reinvestment policy. | Explicit mention of Treasury purchases, MBS, reinvestment of principal payments, or balance sheet runoff. | *"The Committee will continue reducing its holdings of Treasury securities and agency debt."*<br>*"Monthly asset purchases will proceed at $120 billion."* |
| `RATES` | Federal funds target range decisions, rate levels, or voting outcomes. | Mentions target range numbers (e.g. 5-1/4 to 5-1/2 percent), basis points adjustment, or vote tallies. | *"The Committee decided to raise the target range for the federal funds rate by 25 basis points."* |

---

## 3. Decision Rules & Disambiguation

### Rule A: Multi-label Composition
A sentence that communicates an action and its policy objective receives multiple labels.
- *Sentence*: "To achieve 2 percent inflation, the Committee raised the target range by 50 basis points."
  - Annotations: `[HAWKISH, RATES]`

- *Sentence*: "The Committee anticipates holding the federal funds rate near zero until maximum employment is achieved."
  - Annotations: `[DOVISH, FORWARD_GUIDANCE, RATES]`

### Rule B: Temporal Distinction (Causation vs. Correlation)
Annotators must never infer causation unless the official text explicitly states causal link:
- *"Yields rose following the statement release"* → Temporal correlation (`[NEUTRAL]`)
- *"The Committee tightened rates because inflation remained elevated"* → Causal attribution (`[HAWKISH, RATES]`)

### Rule C: Forward Guidance Threshold
The word "expects" alone does not qualify as `FORWARD_GUIDANCE` unless it pertains to **future FOMC policy actions or rate conditions**. "Expects inflation to decline" is `NEUTRAL` or `DOVISH` (economic forecast), whereas "Expects to keep rates unchanged" is `FORWARD_GUIDANCE`.

---

## 4. Evaluation & Inter-Annotator Agreement

- **Gold Standard Metric**: Cohen's Kappa ($\kappa$) for binary presence per label; Fleiss' Kappa for multi-annotator rounds.
- **Minimum Agreement Threshold**: $\kappa \ge 0.82$ on held-out sample of 100 sentences before dataset freezing.
- **Splits**: Chronological split strictly applied. Statements before 2022 form training/validation; 2022+ reserved for held-out evaluation.

