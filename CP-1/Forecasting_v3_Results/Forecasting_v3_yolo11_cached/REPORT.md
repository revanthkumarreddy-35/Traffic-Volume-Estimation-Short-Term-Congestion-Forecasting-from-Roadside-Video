# Forecasting v3 experiment

Selected using training-date validation only: regularized_xgb_base

Evaluation type: reused_historical_holdout

                      method  n  correct  accuracy  macro_f1
              selected_model 32       16   0.50000  0.494118
original_settings_recomputed 32       13   0.40625  0.409821
                    majority 32        8   0.25000  0.100000
  persistence_label_baseline 32       11   0.34375  0.335415

These are congestion-classification metrics. Detection/counting accuracy remains unmeasured. The original-settings baseline is refitted under the current software, sorted row order and preprocessing; it is not a bit-for-bit replay of the archived 37.5% run. Historical test performance is exploratory after previous inspection. Do not claim independent confirmation without new dates/cameras. Context features contain no human congestion labels. Motion is an image-plane proxy.
