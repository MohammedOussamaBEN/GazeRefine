GazeRefine - Windows CPU preview
===============================

1. Extract the entire archive to a folder on your computer.
2. Keep GazeRefine.exe and the _internal folder together.
3. Open GazeRefine.exe. No Python installation or GPU is required.
4. Open an image / single DICOM slice, then import a fixation CSV or add points.
5. Run on CPU and save the mask, overlay, gaze and settings.

The first inference downloads DINOv3 weights (about 1.2 GB) unless they are
already cached. An optional GAZEREFINE_CHECKPOINT environment variable can
point to a matching local model.safetensors file. Weights are not included.

384 and 592 pixels are preview modes, not published benchmark settings.
1184 pixels is the full-resolution option and takes longer.

For browser webcam capture, choose Open gaze capture in the desktop sidebar.
The local browser app loads its optional RealEye SDK/models on opt-in and
requests camera permission. Calibrate before recording. Webcam tracking
accuracy still requires validation with the intended user and setup.

The native EyeTrax / Tobii adapters require the source installation with the
optional SDKs; those SDKs are not bundled in this portable build.

This is an unsigned research preview, not a clinically validated device.
See APP_GUIDE.md, THIRD_PARTY.md and THIRD_PARTY_LICENSES for details.

Project: https://mohammedoussamaben.github.io/GazeRefine/
Source: https://github.com/MohammedOussamaBEN/GazeRefine/tree/codex/project-site-cpu-desktop

Capture workflow: open the image in the desktop app, choose Browser / RealEye,
complete the 17-target calibration, then click Start recording on the image.
Stop & use fixations plots the fixations and sends them back to the desktop.
Calibration targets alone are not image fixation recording.

Preview 3 shows raw sample and fixation counts separately. In browser capture,
choose a dwell profile and use Rebuild fixations from last recording if needed.
Raw-only recordings also sync to desktop and can be exported before inference.
