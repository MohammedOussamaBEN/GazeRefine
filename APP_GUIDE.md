# GazeRefine Studio

Two interfaces share a real CPU-only inference engine: a native Tk desktop app
and a loopback browser app. They use the pretrained DINOv3 ViT-L/16 encoder,
not a simulated segmentation function. No target-task weights are trained.

## Install and launch

Python 3.10–3.12 is recommended (Python 3.11 for the Windows build).
Use a new environment. On Linux, install the distribution's `python3-tk` package
for the desktop interface. On macOS, use a Python distribution that includes Tk.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-app.txt
python -m desktop.app
```

On macOS/Linux activate with `source .venv/bin/activate`. Install PyTorch with
the appropriate platform command from https://pytorch.org/get-started/locally/.
After installation, Windows users can double-click **Start-GazeRefine.cmd**.

For the local browser UI:

```sh
python scripts/serve_app.py
```

It opens `http://127.0.0.1:8765`. A different port can be chosen with `--port`.
GitHub Pages hosts the project information; it cannot execute PyTorch. The
Hugging Face demo is a separate hosted service. Uploaded images in the local
apps remain local; browser webcam mode fetches its optional SDK and models from
third-party CDNs. The segmentation checkpoint downloads on first use (about
1.2 GB); availability and pretrained-weight terms are controlled by its provider.

### Local checkpoint / offline inference

To reuse a matching, already-downloaded `timm` DINOv3 ViT-L checkpoint:

```powershell
$env:GAZEREFINE_CHECKPOINT = 'C:\models\model.safetensors'
python -m desktop.app
```

This variable is optional. It avoids a checkpoint download. After weights are
available, manual/CSV segmentation does not require a network connection.
Optional webcam SDK model downloads may still require connectivity.

## CPU settings

| Setting | Colonoscopy | Prostate MRI |
|---|---:|---:|
| Heatmap sigma (patch units) | 2.0 | 0.5 |
| kNN k | 20 | 3 |
| Refinement iterations | 5 | 1 |
| Gaze anchor | 0.5 | 0.8 |
| Threshold | 0.5 | 0.5 |
| kNN temperature | 0.05 | 0.05 |

The app settings follow the coordinate-noise study, whose cached kNN evaluator
used temperature 0.05. The repository's original evaluation presets remain
separate (including their historical MRI sigma / kNN-temperature settings).
An app run is not evidence of exact reproduction of those historical runs.

384 px and 592 px are CPU previews. They change the patch grid and the effective
spatial scale of sigma, so published Dice scores do not apply. 1184 px uses the
full-resolution grid. All runs use one image at a time, CPU FP32, last-block
tokens, background contrast and kNN. Exact neighbor search is chunked and
neighbors are reused across refinement iterations to reduce memory and work.
The model is cached between runs; only one resolution's model remains loaded.
Runtime depends on CPU, image size, cache state and fixation count. The native
UI remains responsive while inference runs in a background thread.

## Gaze sources

### Existing expert fixation files

Select **normalized** or **pixels** before importing a simple CSV:

```csv
x,y,duration
0.45,0.52,180
0.48,0.49,240
0.50,0.54,150
```

Coordinates are relative to the displayed, EXIF-oriented image. Duration can
use any consistent positive unit. `IMAGE,CURRENT_FIX_INDEX,CURRENT_FIX_X,
CURRENT_FIX_Y,CURRENT_FIX_DURATION` exports are matched by image stem and use
normalized image coordinates. Missing durations in simple CSVs get equal unit
weights. Nonfinite, negative-duration and out-of-image rows are rejected, not
silently clamped. Multi-frame DICOM is rejected; select a single slice.

Duration weighting follows min-max normalization for varying durations.
Equal durations and single prompts receive unit weights to avoid a zero prior.
This degenerate-input behavior differs from the original research loader.
Manual clicks are explicitly simulated prompts, not expert gaze measurements.

### EyeTrax webcam (desktop)

EyeTrax is a separate Python webcam tracker, not the RealEye API.

```sh
python -m pip install -r requirements-eyetrax.txt
python -m desktop.app
```

Choose **EyeTrax webcam**, then **Start gaze capture**. The adapter creates
`GazeEstimator()`, runs the SDK's nine-point calibration, and predicts screen
coordinates from non-blink frames. Look at the intended structure and stop
capture to convert samples to dwell groups. Camera 0 is used. Calibration
requires your webcam, face and cooperation; it cannot be verified without them.

### Tobii Pro hardware (desktop)

Install a compatible `tobii_research` SDK and device drivers separately, then
calibrate with Tobii Pro Eye Tracker Manager. Select **Tobii Pro hardware**.
The adapter uses the first discovered tracker, averages valid left/right gaze
positions when both are available, and ignores invalid eyes. It unsubscribes
when capture stops. Test with the intended device before collecting study data.

Both desktop sources currently require the calibrated **primary monitor at
100% OS scaling**, with the application window kept stationary. Samples are
mapped from screen pixels to the displayed image rectangle, accounting for
letterboxing. Gaze outside the image breaks a dwell group and is not clamped to
the image boundary. Multi-monitor and high-DPI acquisition need additional
validation; do not assume the mapping is correct on those configurations.

### RealEye webcam (local browser)

Choose **Enable camera + calibrate**. This optionally loads
`@realeye-io/webcam-eyetracker-light-open@1.1.0` using ESM, requests a webcam,
and collects five frames at each recommended calibration target. It then fits
the SDK's gaze calibration and records viewport CSS-pixel coordinates. Samples
are mapped through the actual canvas bounding rectangle to image coordinates.
Resizing invalidates calibration. Stop recording before running segmentation.

RealEye's **commercial REST study/export API**, its **Attention Predictor**, and
the **browser webcam library** are different products. This integration uses
the browser library, not a fabricated REST live-gaze endpoint. No commercial
RealEye account/API token is needed for this optional library integration.
RealEye's SDK has its own dual-license terms; review them before enabling or
redistributing that integration. It is not included under this repo's MIT
license. See THIRD_PARTY.md.

Webcam and hardware streams contain samples rather than fixation events.
The app uses a simple dwell-grouping heuristic: normalized distance radius
0.035, minimum span 100 ms, maximum inter-sample gap 150 ms. A gap, out-of-image
sample or departure from the running center ends a group. This is not a
validated clinical fixation detector and differs from retrospective expert
fixation reports. Both raw samples and derived groups can be exported.

## Export

Native app: **Save outputs** saves a binary PNG mask, overlay, grayscale gaze
prior, original fixation rows, raw captured samples, and JSON settings.
Browser app: download the mask/overlay, gaze CSV and settings JSON. Mask output
has the original image dimensions. Pixel score maps are interpolated to that
size before thresholding; this differs from evaluating on resized benchmark masks.

## Project website

The static site is in `docs/`. Preview it with
`python -m http.server 8000 --directory docs`.
The intended public URL is:
https://MohammedOussamaBEN.github.io/GazeRefine/

To publish after reviewing/merging the branch: enable **Settings → Pages →
Source: GitHub Actions**. `.github/workflows/pages.yml` deploys `docs/` on main.
The native/browser apps are not executed by the static project website.

## Windows executable build

Run **Build Windows desktop app** in GitHub Actions (`workflow_dispatch`).
It produces a downloadable `GazeRefine-Windows-CPU` artifact; it does not
automatically publish a release or bundle pretrained weights. The core build
supports image/CSV/manual inference. Optional EyeTrax and Tobii SDKs are not
bundled: use the source installation for those adapters. For a local build:

```sh
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onedir --windowed --name GazeRefine --collect-all timm --collect-all matplotlib --collect-all pydicom desktop_launcher.py
```

The source app is tested independently of the executable build. A workflow
definition alone does not establish that a signed/distributed binary exists.

## Validation

```sh
python -m unittest discover -s tests -v
python scripts/benchmark_cpu.py --checkpoint /path/to/model.safetensors
```

The benchmark uses shipped image/fixation examples and real pretrained features,
exports masks and records elapsed time. No camera or physical eye tracker is
required for those checks. Research prototype; not a diagnostic device.
