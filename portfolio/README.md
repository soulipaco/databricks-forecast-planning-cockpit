# Figures

All figures are drawn from stored results only; none is edited by hand.

| Figure | Shows | Script |
|---|---|---|
| [`readme_banner.png`](readme_banner.png) | README banner and GitHub social preview (1280 × 640): headline, three score cards, fact chips | `build_readme_banner.py` (needs Chrome or Edge) |
| [`hero_forecasts.png`](hero_forecasts.png) | Actuals and all three 28-day forecasts, with the v2 80% interval, for the protocol-selected featured series at the final origin | `build_readme_figures.py` |
| [`scoreboard.png`](scoreboard.png) | Median series WAPE and signed bias, in two separate panels | `build_readme_figures.py` |
| [`bias_by_origin.png`](bias_by_origin.png) | Pooled signed bias at each of the 12 origins | `build_readme_figures.py` |
| [`final_benchmark_2025.png`](final_benchmark_2025.png) | 2025 WAPE for every series and model | `build_final_chart.py` |
| [`development_two_model_2024.png`](development_two_model_2024.png) | 2024 development, naïve vs Prophet only | `build_development_chart.py` |

```bash
uv run --extra visualization python portfolio/build_readme_figures.py
uv run --extra visualization python portfolio/build_final_chart.py --summary evidence/final_three_model_summary_20260929.json --output portfolio/final_benchmark_2025.png
```

Colours follow a fixed order (naïve orange, Prophet green, v2 blue), and each model also has its own marker shape, so identity never depends on colour alone.
