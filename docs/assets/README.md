# Research page assets

The local figures contain aggregate research results only. The method and qualitative
panels are linked to figures already published in this repository's `main/img` folder.

- `gaze-controls.svg`, `duration-effect.svg`, `scanpath-prefix.svg`: vector versions
  of journal study figures. The 117-slice collection is labelled NCI–ISBI; evaluation
  scope is described in the page rather than repeated in the plot title.
- `component-ablation.svg` and `ablation-results.csv`: the consistently recomputed
  factorial study (16 conditions for each dataset), matching the latest supplied
  journal table, including 80.52 for unweighted expert gaze without kNN and with
  background cleaning on NCI–ISBI.
- `coordinate-noise.svg`: unchanged gaze plus four independent Gaussian-noise
  levels; error bars summarize five perturbation seeds, not case-level uncertainty.
- `scanpath-first-last.svg` and `scanpath-results.csv`: additional prefix/suffix
  analysis from stored aggregate results, explicitly distinguished from the
  journal's prefix-only plot.

Controlled collections: 100 Kvasir-SEG images and 117 fixation-available NCI–ISBI
slices. The broader comparison uses 1,000 images and 789 slices and has its own
table. These scopes must not be pooled. Bootstrap intervals and comparator means
are reproduced from the supplied journal draft, not newly computed on the website.

No private manuscript PDF, raw gaze, patient IDs or newly supplied medical images
are included in this website asset package.
