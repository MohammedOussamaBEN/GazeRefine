# Validation record

Validated locally on Windows, Python 3.10.11, PyTorch 2.7.0, timm 1.0.22.
All model calls explicitly use CPU FP32. A matching, locally cached DINOv3
ViT-L/16 pretrained checkpoint was used; weights are not distributed here.

* Seven automated checks pass: equal/single-duration prompts, invalid input,
  explicit CSV units and image selection, dwell grouping across gaps,
  chunked exact kNN agreement with a full matrix, local API session/origin
  protection, and static-route boundaries.
* Native Tk app initializes, displays an image, clears gaze, and shuts down.
* Real-weight CPU inference succeeds for shipped colonoscopy and DICOM
  examples at 384 and 1184 pixels, with original-size mask exports.
* Representative 384-pixel timings: 11.06 s colonoscopy including initial model
  load, then 1.36 s MRI using the cached model. Full-resolution timings:
  32.60 s colonoscopy including initial load, then 22.51 s MRI. These are smoke
  timings on one workstation, not controlled performance benchmarks.
* The default pretrained model also loads from the normal Hugging Face cache
  without a custom checkpoint path, with offline mode enabled.
* Chrome desktop (1440 px) and mobile (390 px) checks pass: no horizontal
  overflow; image comparison toggle works. All local images decode.
* Browser app uploads the supplied example, imports its 35 gaze rows, runs
  actual CPU inference, renders the overlay, and offers the binary mask
  download. No browser JavaScript errors were observed.
* The actual optional RealEye 1.1.0 browser package imports and initializes
  its CPU MediaPipe backend; its API returns 17 calibration targets. Camera
  access was not requested for this validation.

Not yet established by these checks: live calibration accuracy, webcam gaze
quality, physical Tobii acquisition, multi-monitor/high-DPI mapping, clinical
performance, or reproduction of retrospective paper Dice scores by app runs.
Those require the relevant observer, hardware and evaluation protocol.
