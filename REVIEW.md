# Project and publication review — 25 October 2026

## Paper instructions checked

- The current PDF has nine pages in the requested reference-inspired journal
  layout. The full-width abstract replaces the keywords sidebar.
- The outline paragraph and entire Declarations block are removed.
- All four requested student names and Dr. T. Praveen are present.
- Five figures, twelve research tables and 51 equations are preserved. Figure
  numbering is now sequential in reading order; the confidence-band chart is
  Figure 2 and the box-area/directional-flow plot is Figure 3.
- Confidence-band labels are readable. The caption explicitly distinguishes this
  descriptive plot from a ground-truth confusion matrix.
- All 26 bibliography source links and internal citation, figure and table
  destinations are present in the DOCX and PDF.
- Original, cached and expanded experiments are reported separately with their
  sample sizes, classifiers, class distributions and baseline comparisons.
  Unsupported detection/counting accuracy values are not invented.
- Appendix notation describes a source-clip feature vector, without implying that
  every clip lasts exactly 60 seconds.

The formatting follows the user's supplied example and requested edits; it is
not a claim that an unspecified journal's submission checklist has been met.
The related-work comparisons remain contextual because other papers use
different datasets and evaluation protocols.

## Results and code verification

Saved predictions independently reproduce Stage-A accuracy/macro-F1 for both
detectors, Stage-B selected-pipeline scores, and all four Stage-C methods.
The original expanded archive was checked against its extracted files; input and
checkpoint hashes, labels, chronological pairing, validation rankings, and
464 new clip manifests/crossing logs agree with the saved summaries.

The portable verifier checks the CSV evidence supplied in this repository.
Full tracking-log verification requires the original local/Drive artifacts.
The stored full audit is evidence of the completed local review, not a claim
that those omitted logs can be reconstructed from this repository.

Published review evidence:

- [Matched detector comparison](CP-1/Executed_Results_Analysis/YOLOV8_YOLO11_COMPARISON_REPORT.md)
- [Cached and expanded evaluation comparison](CP-1/Forecasting_v3_Results/COMPARISON.md)
- [Manual playback review](CP-1/Manual_Review/MANUAL_REVIEW_NOTES.md)

The forecasting suite covers nine cases, including label leakage, chronological
split boundaries, label-blind selection, motion features, checkpoint resume,
and contract mismatch handling. Counter checks cover finite-line geometry,
one count per track, tracker reset, and manually annotated count evaluation.
The comparison notebook checks enforce the exact 80 clips, labels, 48/32 split,
model-specific checkpoints and output directories. All notebook Python cells
were syntax-checked, accounting for Colab installation commands.

The review does not rerun GPU video inference, benchmark speed, or validate
vehicle boxes/counts against unavailable manual annotations. Test-set reuse
and limited minority-class support remain research limitations.

## Corrections and repository preparation

Fixed the renamed YOLO11 notebook path, stale paper links and outdated author
placeholder notes. The comparison-notebook test now accepts both saved execution
outputs and clean notebooks while still checking its logic. Paper figures were
renumbered and linked again; numerical results were not changed. The introduction
now correctly attributes road-surface installation to inductive loops without
making the same blanket claim about radar. The retained CSV, figure, audit, and review records were checked during repository preparation.

The current repository tree contains reusable notebooks/code, run instructions,
label inputs used by offline checks, measured evaluation CSVs/figures, audits,
and the current research-paper PDF. Output-free notebooks retain the
same code and configuration; executed originals are archived locally under
`Local_Only/Executed_Notebooks/`.

Administrative files, chat history, third-party reference PDFs, obsolete drafts,
raw tracking logs, downloaded model binaries, data-download manifests and one-time
maintenance files remain local. Removing previously tracked files from the
current tree does not erase them from earlier Git history. No history rewrite
or force push is part of this update.
