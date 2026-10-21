"""Shared CPU inference for local apps; preview resolutions are not benchmarks."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class AppConfig:
    modality: str = "colonoscopy"
    resolution: int = 384
    threshold: float = 0.5
    duration_weighted: bool = True
    checkpoint: str | None = None

    def validate(self):
        if self.modality not in ("colonoscopy", "mri"):
            raise ValueError("Choose colonoscopy or mri.")
        if self.resolution not in (384, 592, 1184):
            raise ValueError("Resolution must be 384, 592 or 1184.")
        if not 0 < self.threshold < 1:
            raise ValueError("Threshold must be between zero and one.")


def load_image(source) -> Image.Image:
    """Read images or a single-frame greyscale DICOM. No metadata is exported."""
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if isinstance(source, (str, Path)) and Path(source).suffix.lower() == ".dcm":
        import pydicom
        ds = pydicom.dcmread(source)
        if int(getattr(ds, "NumberOfFrames", 1)) != 1:
            raise ValueError("Select a single DICOM slice; multi-frame files are not supported.")
        a = ds.pixel_array.astype(np.float32)
        if a.ndim != 2:
            raise ValueError("DICOM input must be a single greyscale slice.")
        a = (a-a.min()) / max(float(a.max()-a.min()), 1e-8)
        return Image.fromarray((255*a).astype(np.uint8)).convert("RGB")
    with Image.open(source) as img:
        if img.width * img.height > 40_000_000:
            raise ValueError("Choose an image under 40 megapixels.")
        return ImageOps.exif_transpose(img).convert("RGB")


def normalize_fixations(points, duration_weighted=True):
    a = np.asarray(points, dtype=np.float32)
    if a.ndim != 2 or a.shape[1] != 3 or not 1 <= len(a) <= 5000:
        raise ValueError("Provide 1–5000 normalized x,y,duration rows.")
    if not np.isfinite(a).all() or (a[:, :2] < 0).any() or (a[:, :2] > 1).any():
        raise ValueError("Gaze coordinates must be finite and inside [0,1].")
    if (a[:, 2] <= 0).any():
        raise ValueError("Fixation durations must be positive.")
    a = a.copy()
    spread = float(np.ptp(a[:, 2]))
    # Preserve the research min-max transform for varying durations. Equal
    # durations/single clicks need unit weights, otherwise the prior is zero.
    a[:, 2] = (a[:, 2]-a[:, 2].min())/(spread+1e-8) if duration_weighted and spread > 1e-8 else 1.
    return a


def read_fixations(path, width, height, coordinates="normalized", image_name=None):
    import pandas as pd
    f = pd.read_csv(path, sep=None, engine="python")
    f.columns = f.columns.str.strip()
    if "IMAGE" in f:
        if not image_name:
            raise ValueError("An image filename is needed for multi-image exports.")
        ids = f.IMAGE.astype(str).map(lambda v: Path(v).stem)
        f = f[ids == Path(image_name).stem]
    if "CURRENT_FIX_X" in f:
        if "CURRENT_FIX_INDEX" in f:
            f = f.sort_values("CURRENT_FIX_INDEX")
        a = f[["CURRENT_FIX_X", "CURRENT_FIX_Y", "CURRENT_FIX_DURATION"]].to_numpy(float)
    else:
        if not {"x", "y"} <= set(f.columns):
            raise ValueError("CSV needs x,y,duration or EyeLink CURRENT_FIX_* columns.")
        a = np.column_stack([f.x, f.y, f.duration if "duration" in f else np.ones(len(f))]).astype(float)
        if coordinates == "pixels":
            a[:, 0] /= width; a[:, 1] /= height
        elif coordinates != "normalized":
            raise ValueError("Choose normalized or pixels explicitly.")
    normalize_fixations(a)
    return a.tolist()


def samples_to_fixations(samples, radius=.035, min_duration_ms=100, max_gap_ms=150):
    """Simple dwell grouping, not a validated clinical fixation filter.

    Input: normalized image x,y,timestamp_ms. Out-of-image samples end a
    group. Dwell is never accumulated across tracking gaps or blinks.
    """
    result, group = [], []
    def flush():
        if len(group) >= 2:
            duration = group[-1][2]-group[0][2]
            if duration >= min_duration_ms:
                mean = np.mean(np.asarray(group)[:, :2], axis=0)
                result.append([float(mean[0]), float(mean[1]), float(duration)])
    last_time = -float("inf")
    for x, y, timestamp in samples:
        if not np.isfinite([x,y,timestamp]).all() or timestamp < last_time:
            raise ValueError("Gaze samples must be finite and chronological.")
        last_time = timestamp
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            flush(); group = []; continue
        if group and (timestamp-group[-1][2] > max_gap_ms or
                      np.linalg.norm(np.array([x,y])-np.mean(np.asarray(group)[:, :2], axis=0)) > radius):
            flush(); group = []
        group.append([x,y,timestamp])
    flush()
    return result


class CPUInference:
    def __init__(self):
        self._model = None
        self._key = None
        self._lock = threading.Lock()

    def predict(self, image, points, config=AppConfig()):
        import torch
        from .model import GazeRefine
        config.validate()
        fix = normalize_fixations(points, config.duration_weighted)
        image = load_image(image)
        torch.set_num_threads(min(8, max(1, os.cpu_count() or 1)))
        checkpoint = config.checkpoint or os.environ.get("GAZEREFINE_CHECKPOINT")
        key = (config.resolution, checkpoint)
        with self._lock, torch.inference_mode():
            start = time.perf_counter()
            if key != self._key:
                self._model = None
                self._model = GazeRefine(img_size=config.resolution, extract_mode="last",
                                        checkpoint=checkpoint).to("cpu").eval()
                self._key = key
            m = self._model
            m.sigma = 2. if config.modality == "colonoscopy" else .5
            m.knn_k = 20 if config.modality == "colonoscopy" else 3
            m.max_iters = 5 if config.modality == "colonoscopy" else 1
            m.gaze_anchor_weight = .5 if config.modality == "colonoscopy" else .8
            m.knn_temp = .05  # cached-neighbor robustness evaluator setting
            m.knn_refine = True; m.contrast_method = "difference"
            resized = image.resize((config.resolution, config.resolution), Image.Resampling.BILINEAR)
            a = np.array(resized).astype(np.float32)/255
            a = (a-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
            tensor = torch.from_numpy(a).permute(2,0,1).unsqueeze(0)
            output = m(tensor, torch.from_numpy(fix).unsqueeze(0))
            scores = Image.fromarray(output["preds"][0,0].numpy()).resize(image.size, Image.Resampling.BILINEAR)
            mask_array = np.asarray(scores) > config.threshold
            mask = Image.fromarray(mask_array.astype(np.uint8)*255)
            overlay = np.asarray(image).copy()
            overlay[mask_array] = (overlay[mask_array]*.55+np.array([0,215,175])*.45).astype(np.uint8)
            prior = output["gaze_heatmap"][0].numpy()
            prior_img = Image.fromarray((prior*255).astype(np.uint8)).resize(image.size, Image.Resampling.BILINEAR)
            metadata = {**asdict(config), "device":"cpu", "backbone":"vit_large_patch16_dinov3.lvd1689m",
                        "sigma":m.sigma, "knn_k":m.knn_k, "max_iters":m.max_iters,
                        "anchor":m.gaze_anchor_weight, "knn_temp":m.knn_temp,
                        "preview":config.resolution != 1184, "n_fixations":len(fix),
                        "seconds_including_model_load":round(time.perf_counter()-start,3)}
            return {"mask":mask, "overlay":Image.fromarray(overlay), "prior":prior_img, "metadata":metadata}
