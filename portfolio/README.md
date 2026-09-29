# Figures

| Figure | Source data | Script |
|---|---|---|
| [`final_benchmark_2025.png`](final_benchmark_2025.png): 2025 WAPE by series and model | `evidence/final_three_model_summary_20260929.json` | `build_final_chart.py` |
| [`development_two_model_2024.png`](development_two_model_2024.png): 2024 development, naïve vs Prophet only | `evidence/development_two_model_full_20260929.json` | `build_development_chart.py` |

Regenerate with `uv run --extra visualization python portfolio/build_final_chart.py --summary evidence/final_three_model_summary_20260929.json --output <png>`. Charts are drawn only from stored results.
