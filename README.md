# EV Supply Chain Shortage Dashboard

An interactive Streamlit dashboard that models how a PCBA (printed circuit board assembly) shortage moves through an EV bill of materials and turns lost builds into P&L and working capital impact.

**Live app:** to be added soon

## The question it answers

When one supplier cuts supply on a single part, how many vehicles can we still build, what does it cost, and where should we act first?

## Headline finding

A 4-week, 50% supply cut to one $85 circuit board strands $45M of other inventory and costs $22M. A cheap part can hold an entire build plan hostage.

## What it models

- **Scope:** 14-part EV bill of materials, 10 suppliers, 13-week quarter
- **Clear-to-build (CTB):** a weekly engine that finds the binding constraint part and flags line-down risk
- **Disruption cost:** gross profit lost, under-absorbed overhead, purchase price variance (PPV) and premium freight, plus the break-even point for expedited spot buys
- **Supplier risk:** a weighted score across lead time variability, OTIF, sole sourcing, region and financial health. It surfaces a single tier 2 chip fab sitting behind 5 different circuit boards
- **Safety stock:** sized with the critical ratio, showing that lead time variability, not unit cost, drives how much cash each buffer ties up

## Built with

Python, Streamlit, pandas, Plotly

## Data note

All data is synthetic and built to mirror a real EV supply chain planning workflow. It does not represent any company's actual figures.

## In progress

Integrating public production and delivery data from company filings, and modeling multi-tier supplier capacity.
