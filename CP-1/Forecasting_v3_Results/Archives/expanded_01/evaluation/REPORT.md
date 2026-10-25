# Forecasting v3 experiment

Selected using training-date validation only: logistic_context

Evaluation type: new_clips_on_previously_examined_dates

                      method  n  correct  accuracy  balanced_accuracy  macro_f1
              selected_model 64       46  0.718750           0.467308  0.428289
original_settings_recomputed 64       48  0.750000           0.341346  0.368447
                    majority 64       52  0.812500           0.250000  0.224138
  persistence_label_baseline 64       51  0.796875           0.400962  0.417881

These are congestion-classification metrics. Detection/counting accuracy remains unmeasured. The original-settings baseline is refitted under the current software, sorted row order and preprocessing; it is not a bit-for-bit replay of the archived 37.5% run. Historical test performance is exploratory after previous inspection. Do not claim independent confirmation without new dates/cameras. Context features contain no human congestion labels. Motion is an image-plane proxy.
