# Data and labels

The project uses the Barbados Traffic Analysis Challenge congestion labels.
`Zindi_Labels/Train.csv` is the existing 16,076-row table used in the experiments,
with 4,019 rows for each of four Norman Niles camera views. It provides video
paths, camera IDs, timestamps, and entering/exiting congestion ratings.

For the Colab notebooks, place your dataset as follows:

```text
My Drive/CP-1 Dataset/
  CSV/Train.csv
  normanniles1/*.mp4
  normanniles2/*.mp4
  normanniles3/*.mp4
  normanniles4/*.mp4
```

Retain the original filenames: labels are joined by relative video path.
MP4 files do not need embedded attributes. The pipeline excludes 20 rows with
invalid segment timing and reports missing videos and unmatched labels.

Video downloads, torrent manifests and raw footage are not distributed here.
Obtain footage through its original provider and follow that provider's terms.
The label table and derived experimental exports are data artifacts, not
human-labelled vehicle boxes, identities, weather conditions or crossing counts.
Their availability does not permit measuring detection/counting accuracy.
