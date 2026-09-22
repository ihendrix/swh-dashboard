# Software Heritage Programming Language Explorer

Interactive exploration of programming-language evolution in the Software Heritage archive.

This project builds on the MSR 2025 paper **“50 Years of Programming Language Evolution through the Software Heritage looking glass”** by Adèle Desmazières, Roberto Di Cosmo, and Valentin Lorentz.

The paper analyzes the first appearance of unique file contents in Software Heritage to study how programming, markup, and data languages have changed over time. This project turns those static results into an interactive dashboard and applies the same general pipeline to the updated 2026 Software Heritage Aggregated Contents dataset.

## Dashboard

The dashboard allows users to:

- compare programming-language activity over time
- filter programming, markup, and data languages
- select individual languages for comparison
- switch between annual file counts and relative activity
- compare language activity for individual years
- inspect changes between 2018 and 2021
- explore extension-level and language-level data
- switch between the published MSR 2025 results and processed 2026 Software Heritage data

## Data pipeline

The analysis follows the structure used in the paper:

```text
Aggregated Contents
        ↓
most popular filename
        ↓
file extension
        ↓
first-occurrence year
        ↓
extension/year counts
        ↓
language mapping
        ↓
language/year counts
        ↓
interactive visualizations
