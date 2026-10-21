# Optional gaze integrations

GazeRefine's source is MIT licensed. External pretrained weights, SDKs and
browser libraries retain their own terms; none are relicensed by this project.

* **DINOv3 / timm**: https://huggingface.co/timm/vit_large_patch16_dinov3.lvd1689m
  and https://github.com/huggingface/pytorch-image-models. Weight downloads are
  separate from this repository and Windows artifact.
* **EyeTrax** (optional Python webcam capture, MIT):
  https://github.com/ck-zhang/EyeTrax. Calibration estimates gaze; it does not
  train the segmentation model.
* **Tobii Pro SDK** (optional hardware acquisition):
  https://developer.tobiipro.com/python/python-step-by-step-guide.html.
  Install the vendor SDK/drivers and accept vendor terms separately.
* **RealEye Webcam EyeTracker Light Open 1.1.0** (optional browser import):
  https://github.com/RealEye-io/webcam-eyetracker-light-open.
  Its dual license is AGPL-3.0-or-later or a separate RealEye commercial license:
  https://github.com/RealEye-io/webcam-eyetracker-light-open/blob/main/LICENSE.
  Check the actual applicable terms before enabling/redistributing. The
  browser module is fetched on explicit opt-in, not vendored into this repo.
  Its MediaPipe/WASM/model dependencies are loaded from their providers.
* **RealEye REST API** (not used for live capture here):
  https://www.realeye.io/docs/api/.

Camera frames in the local browser integration are used for local calibration
and gaze estimation. The local backend receives the medical image and derived
fixation coordinates for segmentation, not the webcam video. No analytics,
remote segmentation call, or automatic data upload is implemented in the
local apps. Initial checkpoint / optional SDK downloads still contact providers.
