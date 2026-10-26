# Shortage to Cash Impact

**A PCBA supply risk dashboard built in Streamlit.**

When a single circuit board goes short, an EV line stops. Supply chain teams measure that in vehicles. Finance teams measure it in margin, variances and cash. This dashboard connects the two: pick a part, cut its supply, and watch the shortage move from the factory floor into the P&L and the balance sheet.

> All part, supplier and cost data in this project is **simulated**. Part names, suppliers, costs and quantities are illustrative assumptions designed to behave like a real automotive supply base. It is not Tesla data.

## Headline finding

A 4-week, 50% supply cut to one $85 circuit board strands $45M of other inventory and costs $22M. A cheap part can hold an entire build plan hostage.

## Why PCBAs

A printed circuit board assembly (PCBA) is a circuit board with its chips and components already mounted. A modern EV carries dozens of them, from the main compute board to the small modules that move the seats. During the 2021 and 2022 semiconductor shortage, many automakers could build nearly the whole car but not ship it, because one cheap board was missing. That gap between a part's cost and its impact is what this project measures.

## The five pages

| Page | Question it answers |
|---|---|
| **Executive Overview** | How many cars did we lose, and what did it cost? Plan vs actual build, total disruption cost, and a line-down watchlist. |
| **Clear to Build** | Given stock on hand plus this week's deliveries, how many cars can we actually build, and which part is the binding constraint? Includes a days-of-supply heatmap. |
| **Supplier Risk** | Which suppliers could stop the line? A composite risk score, a reliability map, and the hidden tier 2 chip fab that sits underneath five different boards. |
| **Shortage P&L Impact** | What does the shortage do to the income statement? A cost waterfall, stranded inventory, a spot buy decision curve, and a severity by duration sensitivity grid. |
| **Working Capital** | How much safety stock is worth holding? Carrying cost vs stockout cost, the critical ratio that sets the optimal service level, why supplier lead time variability (not part price) drives buffer size, and the cash conversion cycle. |

The sidebar scenario controls (which part, how severe, how long, and how much to spot buy) apply to every page at once.

## How it works

1. **Simulated supply base.** 14 tracked parts across 10 suppliers in 5 countries, over one 13-week quarter with a plan of 5,000 vehicles per week. Weekly deliveries vary with each supplier's on-time performance.
2. **Clear-to-build engine.** Each week: receive inbound parts, compute clear-to-build for every part, build the minimum (capped at plan), consume parts, and carry the rest forward.
3. **Shock and mitigation.** The chosen part loses a share of its inbound for the chosen weeks. Optionally, part of the gap is bought on the spot market at a premium and air-freighted in a week later.
4. **Financial translation.** The gap between the baseline and the shocked run is converted into gross profit lost, under-absorbed overhead, purchase price variance, premium freight and the carrying cost of stranded inventory.

All logic lives in `core/engine.py` with no Streamlit code, so every number can be tested on its own.

## Supply chain and finance terms used

**Supply chain**

| Term | Meaning | Where it appears |
|---|---|---|
| Bill of materials (BOM) | The list of parts and quantities that make one vehicle | Clear to Build |
| Clear to build (CTB) | Vehicles you can build with parts on hand plus confirmed inbound | Clear to Build |
| Binding constraint | The part with the lowest CTB. It alone sets output | Clear to Build, Overview |
| Days of supply | Inventory expressed as days of production it can support | Heatmap, watchlist |
| Line-down risk | A part close to running out, which would stop the line | Overview watchlist |
| Lead time and lead time variability | How long a supplier takes, and how unpredictable that is | Supplier Risk, Working Capital |
| On-time in-full (OTIF) | Share of deliveries that arrive on time and complete | Supplier Risk |
| Sole source | A part with only one qualified supplier | Supplier Risk, CTB table |
| Tier 1 / Tier 2 supplier | Tier 1 ships to the plant. Tier 2 supplies the tier 1 | Supplier Risk |
| Safety stock | Buffer inventory held against demand and lead time swings | Working Capital |
| Reorder point | Stock level that triggers a new order | Working Capital |
| Service level | Probability of not running out during a lead time | Working Capital |
| Critical ratio | The optimal service level, where the cost of holding one more unit equals the expected cost of running short | Working Capital |
| Spot buy / expedite | Buying from brokers and air freighting to cover a gap | Shortage P&L Impact |
| Bullwhip effect | Small demand changes growing into large order swings upstream. Panic ordering in 2021 made the chip shortage worse | Context for the shortage scenario |

**Finance**

| Term | Meaning | Where it appears |
|---|---|---|
| Gross profit lost | Permanently lost vehicles x selling price x gross margin | Shortage P&L Impact |
| Under-absorbed overhead | Fixed plant costs still incurred while fewer cars are built | Shortage P&L Impact |
| Purchase price variance (PPV) | (Actual price paid - standard cost) x quantity | Shortage P&L Impact |
| Stranded inventory | Parts that arrive but cannot be used because another part is missing | Overview, Shortage P&L Impact |
| Inventory carrying cost | Annual cost of holding inventory (capital, storage, obsolescence) as a % of its value | Working Capital |
| Days inventory outstanding (DIO) | Average inventory value / daily cost of goods sold | Overview, Working Capital |
| Cash conversion cycle (CCC) | DIO + days sales outstanding - days payables outstanding | Working Capital |

## Key formulas

- **CTB per part** = floor(units available / quantity per vehicle)
- **Weekly build** = min(build plan, lowest CTB across all parts)
- **Safety stock** = z x sqrt(lead time x demand variance + demand² x lead time variance)
- **Reorder point** = average daily demand x lead time + safety stock
- **Critical ratio** = 1 - (annual holding cost per unit / (order cycles per year x stockout cost per unit))
- **Expected units short per cycle** = σ over lead time x L(z), where L(z) is the standard normal loss function
- **Supplier risk score** = 30% lead time variability + 25% OTIF gap + 20% sole sourcing + 15% region risk + 10% financial health, scaled 0 to 100

## Default assumptions

All of these can be changed in the sidebar.

| Assumption | Default |
|---|---|
| Average selling price | $47,000 |
| Automotive gross margin | 18% |
| Fixed overhead per vehicle | $3,200 |
| Lost builds recovered next quarter | 60% |
| Inventory carrying rate | 25% per year |
| Spot price multiple | 3x standard cost |
| Premium freight | $12 per part |

## Run it locally

```bash
cd tesla-dashboard
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

## Deploy it (free)

ev-shortage-dashboard.streamlit.app


## Project structure

```
app.py                  Router and sidebar scenario controls
core/data.py            Simulated parts, suppliers and inbound schedule
core/engine.py          CTB simulation, financials, risk score, safety stock math
core/ui.py              Shared formatting, chart styling and caching
pages/                  One file per dashboard page
.streamlit/config.toml  Theme
```

**Live app:** [ev-shortage-dashboard.streamlit.app](https://ev-shortage-dashboard.streamlit.app)
Built by Aarna Pandey.
