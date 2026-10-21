Fixes the image/gaze acquisition flow in the Windows CPU preview.

1. Open an image or DICOM slice in GazeRefine.exe.
2. Choose Browser / RealEye: the same image now loads automatically.
3. Complete the 17-target camera calibration (step 1, not image fixation recording).
4. Start recording on the image (step 2). Live cursor, sample trace, sample count and dwell-group count show incoming gaze.
5. Stop & use fixations plots the markers and sends new fixations back to the desktop app.

Raw gaze and fixation CSV export is available before segmentation. Missing-face/outside-image diagnostics explain zero-fixation runs. Cancel restores the image. Native SDK options unavailable in the portable build are hidden, avoiding the cv2 error.

Nine Python tests, a native image/gaze round-trip check, and a browser flow test using a fake camera/simulated tracker pass. These checks do not establish real-observer gaze accuracy. The rebuilt executable also passes a real-checkpoint CPU inference smoke test.

Extract the complete archive into a new folder and run GazeRefine.exe. Close the older app/browser session first. This unsigned research preview downloads pretrained weights separately if they are not cached. No medical dataset, journal PDF or pretrained weights are bundled.
