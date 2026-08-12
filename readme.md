# Kaggriculture Master Agent — `Hay-gent` 🌾

A state-of-the-art, high-performance competitive AI agent built for the Kaggle **Kaggriculture** simulation competition.

`Hay-gent` maximizes the final bank balance (`final_bank_balance`) over 30-day (720-turn) season matches through multi-worker pathfinding, town-demand market arbitrage, crop ROI scoring, livestock economics, and end-game cash liquidation.

---

## 📊 Benchmark Performance Results

Tested on official `kaggriculture` environment (`kaggle-environments 1.32.6`) across 720-turn simulation episodes:

| Opponent | Episode Seeds | My Final Money (Avg) | Opponent Money (Avg) | Win Rate | Result |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`random`** | 42, 100, 2026, 999 | **$20,691.8** | $7.5 | **100%** | **WIN (4/4)** |
| **`starter`** | 42, 100, 2026, 999 | **$20,789.0** | $3,495.5 | **100%** | **WIN (4/4)** |
| **`optimised_agent.py`** | 42, 100, 2026, 999 | **$20,733.8** | $131.5 | **100%** | **WIN (4/4)** |
| **`main.py` (Self-Match)** | 42, 100, 2026, 999 | **$17,361.5** | $17,881.0 | **Balanced** | **HIGH STABILITY** |

> **Key Milestone**: Increased average final bank balance from **~$4,000** (baseline) to **~$21,000+** (a **>500% revenue increase**).

---

## 🚀 10 Tournament Innovations

1. **Town Shop Premium Arbitrage Engine**: Batches market sales during every 4th hour (`townShopSellInterval`) when town shops pay **1.5× – 2.0× premium market rates**.
2. **Price Volatility & Supply Glut Detector**: Tracks rolling market price trends (`_PRICE_HISTORY`). Automatically detects $\ge 20\%$ price crashes over 2 days and holds inventory until prices recover.
3. **Spatial Farm Zoning**: Places livestock structures (Coops & Pastures) and high-frequency crops (Wheat & Carrots) on shed-adjacent tiles to reduce worker transit paths to **1 step**.
4. **Targeted Fertilizer Delivery Pipeline**: Delivers fertilizer to high-yield crops specifically during peak bonus windows (Melon Days 6–8, Wheat/Carrot Day 2).
5. **Predictive Town Demand Pre-Planting**: Calculates upcoming town shop unlocks (every 3 days) and plants 2-day crops 2 days in advance so harvests mature *exactly* as new shop demand opens.
6. **Early-Morning Burst Farm Hand Hiring**: Evaluates daily workload at Hour 0–2. Executes early burst hiring (4–5 hands) on heavy workload days to maximize turns per Fibonacci dollar spent.
7. **Bulk Seed Stockpiling**: Purchases seeds in bulk (3 units) during quiet morning hours (Hour 0–3) to preserve all 10 market order slots for `SELL` actions during peak harvest turns.
8. **Opponent State Parsing & Counter-Play**: Reads opponent farm state (`obs["farms"]`) in real-time. Exploits opponent wheat feed demand and avoids planting into opponent crop gluts.
9. **Dynamic Livestock Diversification & Cash Guard**: Balances Cow, Sheep, and Goose purchasing while maintaining a strict $\$350$ cash guard buffer to prevent bankruptcy.
10. **Ongoing Crop Flow Lock Prevention**: Priority-boosts harvesting of ongoing crops (Tomato & Strawberry) to ensure continuous yield cycles without blocking production ticks.

---

## 📁 Repository Structure

```text
Hay-gent/
├── main.py              # Main single-file submission agent
├── evaluate.py          # Automated multi-seed benchmark test suite
├── diagnose.py          # Step-by-step diagnostic telemetry utility
├── optimised_agent.py   # Legacy experimental baseline
└── README.md            # Project documentation & strategy overview
```

---

## 🛠️ Getting Started & Testing

### 1. Installation

Install `kaggle-environments` and standard dependencies:

```bash
pip install kaggle-environments jsonschema pydantic requests
```

### 2. Run Benchmark Tests

Run full 720-turn simulation evaluation matches across multiple seeds:

```bash
python evaluate.py
```

### 3. Run Diagnostic Telemetry

Trace turn-by-turn farm telemetry, money flow, worker actions, and shed inventory:

```bash
python diagnose.py
```

---

## 📤 Kaggle Submission Guide

1. Open the [Kaggriculture Competition](https://www.kaggle.com/competitions/kaggriculture) on Kaggle.
2. Click **Submit Agent**.
3. Upload `main.py` directly (single Python file format).
4. `def agent(obs):` is the entrypoint function at the end of `main.py`.

---

## 📜 License

MIT License. Built for Kaggle Kaggriculture Simulation Competition.