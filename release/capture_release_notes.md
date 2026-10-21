GazeRefine Studio preview 3 fixes raw gaze capture returning zero usable fixations and refreshes the desktop interface.

- Raw gaze always transfers back to the desktop, including recordings with zero derived fixations.
- Separate sample and fixation counts, export before inference, and clearer zero-fixation diagnostics.
- Selectable webcam (8% radius / 400 ms gap) or strict (3.5% / 150 ms) dwell grouping. Both require ≥100 ms and two samples; missing-face or outside-image samples break the group.
- Rebuild fixations from the last recording without duplicating prompts. These experimental acquisition settings do not change benchmark presets.
- Desktop sidebar workflow and larger image workspace. Project website redesigned with a centered academic layout inspired by the supplied reference.

Open an image, choose Open gaze capture, calibrate, record on the image, and Stop & use fixations. Verify the returned fixation count before Run on CPU. If it is zero, inspect on-image / outside / missing-face counts and try the webcam dwell profile or recalibrate.

Validation: 11 Python tests, native gaze-transfer checks, simulated-camera browser workflow and real-weight portable CPU inference. Simulated gaze tests do not establish real-user tracking accuracy.

Close the older app and browser session. Extract the complete ZIP into a new folder; keep _internal beside GazeRefine.exe. No Python or GPU required. Weights download separately on first inference. No private manuscript, medical dataset or pretrained weights are bundled.
