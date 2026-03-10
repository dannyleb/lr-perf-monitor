# LR Perf Monitor

**Real-time performance monitoring for Adobe Lightroom Classic on macOS.**

Built for: MacBook Pro 2017 · Intel Core i7 · 16GB RAM · macOS Ventura 13.6

---

## What It Does

Lightroom Classic is resource-intensive and Adobe provides zero diagnostic tooling for end users. This app gives you full visibility into *why* LR is slow:

- **CPU tracking** — LR process CPU % vs. system total
- **RAM monitoring** — RSS memory usage, system RAM pressure, swap activity
- **Disk I/O** — read/write throughput in real time (critical for catalog + preview operations)
- **GPU monitoring** — active GPU detection (Radeon 555 discrete vs Intel HD 630 integrated)
- **Thermal tracking** — macOS thermal pressure state + CPU/GPU temps (with sudo)
- **Session logging** — every sample saved to SQLite
- **Charts** — scrolling real-time graphs for all metrics
- **Export** — PDF summary reports + full CSV data export

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/dannyleb/lr-perf-monitor.git
cd lr-perf-monitor
```

### 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run
```bash
python main.py
```

---

## Optional: Enable Thermal & Power Metrics

CPU/GPU temperatures and power draw require `powermetrics` with passwordless sudo.

**Add to `/etc/sudoers` (via `sudo visudo`):**
```
your_username ALL=(ALL) NOPASSWD: /usr/bin/powermetrics
```

Without this, the app still runs fully — thermal pressure state is still shown via `ioreg` (no sudo required).

---

## Project Structure

```
lr-perf-monitor/
├── main.py                      # Entry point
├── requirements.txt
├── src/
│   ├── monitor/
│   │   ├── process_monitor.py   # LR process CPU/RAM
│   │   ├── disk_monitor.py      # Disk I/O
│   │   ├── gpu_monitor.py       # Dual GPU detection
│   │   ├── thermal_monitor.py   # Temps + thermal pressure
│   │   └── session.py           # Sampling coordinator
│   ├── gui/
│   │   ├── main_window.py       # Main PyQt6 window
│   │   ├── dashboard.py         # Live metric cards
│   │   └── charts.py            # pyqtgraph scrolling charts
│   └── data/
│       ├── logger.py            # SQLite session logging
│       └── exporter.py          # PDF + CSV export
├── logs/                        # Session SQLite databases
└── reports/                     # Exported reports
```

---

## System Requirements

| Component | Requirement |
|---|---|
| macOS | 12 Ventura or later |
| Python | 3.10+ |
| PyQt6 | 6.4+ |
| Lightroom | Classic (any recent version) |

---

## Roadmap

- [ ] Phase 2: Catalog operation event tagging (correlate spikes with LR actions)
- [ ] Phase 3: Historical session comparison
- [ ] Phase 4: Automated diagnosis + recommendations engine
- [ ] Phase 5: macOS menu bar widget

---

## Hardware Context

This tool was specifically tuned for the 2017 MacBook Pro dual-GPU architecture. The Radeon Pro 555 / Intel HD 630 GPU switching that macOS performs can cause LR stalls — this app tracks which GPU is active during performance events.

---

*Built with Python 3, PyQt6, pyqtgraph, psutil*
