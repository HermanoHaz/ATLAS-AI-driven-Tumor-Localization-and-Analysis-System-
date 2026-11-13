"""segment.py - NRRD loading + MedSAM tumor segmentation (GPU when available).

Model: MedSAM ("Segment Anything in Medical Images", Ma et al., Nature Communications 2024).
It is the SAM ViT-B architecture fine-tuned on a large medical image collection, so it
loads through the same `segment_anything` package but uses its own pre-processing.

WHAT GOES INTO THE MODEL (it is NOT a 3D cube):
  one 2D axial slice at a time  ->  window/level to 8 bit  ->  resize to 1024 x 1024
  ->  scale to 0..1  ->  3 channels  ->  image encoder  ->  embedding (1, 256, 64, 64)
  ->  + a box prompt  ->  mask decoder  ->  one 2D mask for that slice.
  The 3D result is built by repeating this slice by slice (see segment_volume).
  Run with SAM_DEBUG=1 to print the real shapes the first time a slice goes through.

Checkpoint: download `medsam_vit_b.pth` from https://github.com/bowang-lab/MedSAM
(Get Started section) and put it next to this file, or set MEDSAM_CHECKPOINT.
If `medsam_finetuned.pth` (made by finetune.py) is next to this file it is used instead;
delete or rename it to go back to the original MedSAM.

Environment switches: SAM_DEVICE=cpu forces the CPU. SAM_HALF=1 / 0 forces half precision
on / off (default: the warm-up measures both and keeps the faster one that is accurate).
SAM_DEBUG=1 prints the model input / output shapes.

RESEARCH USE ONLY. Output is not a medical diagnosis.
"""
import os
import re
import threading
import time
from collections import OrderedDict

import numpy as np
import nrrd
import torch
import torch.nn.functional as F
from segment_anything import sam_model_registry

try:                                    # optional: used for interpolation and to tidy the 3D result
    from scipy import ndimage as ndi
except ImportError:
    ndi = None

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_CHECKPOINT = os.path.join(HERE, "medsam_vit_b.pth")          # original MedSAM weights
FINETUNED = os.path.join(HERE, "medsam_finetuned.pth")             # written by finetune.py
CHECKPOINT = os.environ.get("MEDSAM_CHECKPOINT") or (FINETUNED if os.path.exists(FINETUNED) else BASE_CHECKPOINT)
MODEL_NAME = ("MedSAM (custom)" if os.environ.get("MEDSAM_CHECKPOINT")
              else "MedSAM (fine-tuned)" if CHECKPOINT == FINETUNED else "MedSAM")
DEVICE = os.environ.get("SAM_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
DEBUG = bool(os.environ.get("SAM_DEBUG"))

if DEVICE == "cuda" and torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True       # the input is always 1024 x 1024: let cuDNN pick the fastest kernels


def device_info():
    """Human readable device string, e.g. 'GPU: NVIDIA GeForce GTX 1650'."""
    if DEVICE == "cuda" and torch.cuda.is_available():
        return f"GPU: {torch.cuda.get_device_name(0)}"
    return "CPU"


def checkpoint_ready():
    return os.path.exists(CHECKPOINT)


def _half_mode():
    """True / False when forced by SAM_HALF, None = decide automatically during warm-up."""
    flag = os.environ.get("SAM_HALF", "").lower()
    if DEVICE != "cuda" or not torch.cuda.is_available() or flag in ("0", "false"):
        return False
    if flag in ("1", "true"):
        return True
    return None


# ------------------------------------------------------------ volume I/O
def _to_volume(data, header):
    if data.ndim == 4:                  # multi-channel: keep the first channel
        data = data[0]
    if data.ndim != 3:
        raise ValueError("Only 3D NRRD volumes are supported.")
    spacing = (1.0, 1.0, 1.0)
    dirs = header.get("space directions")
    if dirs is not None:
        try:
            rows = [d for d in dirs if d is not None and not np.any(np.isnan(d))]
            sp = tuple(float(np.linalg.norm(d)) for d in rows[:3])
            if len(sp) == 3 and all(s > 0 for s in sp):
                spacing = sp
        except Exception:
            pass
    return data.astype(np.float32), spacing


def _to_mask(data):
    if data.ndim == 4:
        data = data[0]
    if data.ndim != 3:
        raise ValueError("The actual-tumor file must be a 3D NRRD.")
    return data > 0


def load_nrrd(path):
    """Return (volume[x, y, z] float32, spacing (sx, sy, sz) in mm)."""
    data, header = nrrd.read(path)
    return _to_volume(data, header)


def load_mask(path):
    """Load an 'actual tumor' NRRD as a boolean volume (any non-zero voxel is tumor)."""
    data, _ = nrrd.read(path)
    return _to_mask(data)


MASK_WORDS = ("tumor", "tumour", "mask", "seg", "label", "gt", "actual", "roi", "lesion")


def _looks_like_mask(data):
    flat = data.ravel()
    return len(np.unique(flat[::max(flat.size // 200000, 1)])) <= 4      # a mask has only a few different values


def load_pair(path_a, path_b):
    """Open two NRRD files that belong together and work out which one is the scan and which is the
    actual tumor: by their contents first (a mask has only a few values), then by file name."""
    da, ha = nrrd.read(path_a)
    db, hb = nrrd.read(path_b)
    ma, mb = _looks_like_mask(da), _looks_like_mask(db)
    if ma != mb:
        a_is_mask = ma
    else:
        na, nb = os.path.basename(path_a).lower(), os.path.basename(path_b).lower()
        wa, wb = any(w in na for w in MASK_WORDS), any(w in nb for w in MASK_WORDS)
        a_is_mask = wa if wa != wb else np.count_nonzero(da) < np.count_nonzero(db)
    if a_is_mask:
        sd, sh, sp, md, mp = db, hb, path_b, da, path_a
    else:
        sd, sh, sp, md, mp = da, ha, path_a, db, path_b
    vol, spacing = _to_volume(sd, sh)
    return {"vol": vol, "spacing": spacing, "scan_path": sp, "mask": _to_mask(md), "mask_path": mp}


def case_number(path):
    """The case number in a file name: the last number that follows an underscore (DATA_130 -> 130)."""
    found = re.findall(r"_(\d+)", os.path.splitext(os.path.basename(path))[0])
    return int(found[-1]) if found else None


def find_matching_mask(scan_path):
    """Find the actual-tumor file that belongs to a scan by the number after the underscore,
    e.g. .../Test_Images/DATA_130.nrrd  ->  .../Test_Masks/MASK_130.nrrd.
    Looks in folders next to the scan's folder whose name says mask / label / seg / tumor, then in
    mask folders inside the scan's folder, then beside the scan itself. Returns a path or None."""
    num = case_number(scan_path)
    if num is None:
        return None
    scan_path = os.path.abspath(scan_path)
    scan_dir = os.path.dirname(scan_path)
    words = ("mask", "label", "seg", "tumor", "tumour", "gt", "annotation")

    def mask_folders(root):
        try:
            return [os.path.join(root, n) for n in sorted(os.listdir(root))
                    if os.path.isdir(os.path.join(root, n)) and any(w in n.lower() for w in words)]
        except OSError:
            return []

    candidates = [(f, False) for f in mask_folders(os.path.dirname(scan_dir)) if f != scan_dir]
    candidates += [(f, False) for f in mask_folders(scan_dir)]
    candidates.append((scan_dir, True))                  # same folder: only files whose name says mask
    for folder, need_word in candidates:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for n in names:
            p = os.path.join(folder, n)
            if (p != scan_path and n.lower().endswith((".nrrd", ".nhdr")) and case_number(p) == num
                    and (not need_word or any(w in n.lower() for w in words))):
                return p
    return None


def slice_to_uint8(slice2d, center=None, width=None):
    """Window/level a 2D slice into uint8. Defaults to 1st-99th percentile."""
    if center is None or width is None:
        lo, hi = np.percentile(slice2d, [1, 99])
    else:
        lo, hi = center - width / 2.0, center + width / 2.0
    if hi <= lo:
        hi = lo + 1.0
    out = np.clip((slice2d - lo) / (hi - lo), 0, 1)
    return (out * 255).astype(np.uint8)


def axial(vol, k):
    """Axial slice as a (rows=y, cols=x) array. THIS 2D array is what the model receives."""
    return vol[:, :, k].T


def _test_image():
    y, x = np.mgrid[0:256, 0:256]
    return np.clip(40 + 0.3 * x + 150 * (((x - 128) ** 2 + (y - 128) ** 2) < 50 ** 2), 0, 255).astype(np.uint8)


# ----------------------------------------------------------- MedSAM engine
class TumorSegmenter:
    def __init__(self, checkpoint=CHECKPOINT):
        if not os.path.exists(checkpoint):
            raise FileNotFoundError(
                f"MedSAM checkpoint not found:\n{checkpoint}\n\n"
                "Download medsam_vit_b.pth from https://github.com/bowang-lab/MedSAM "
                "(Get Started section) and put it in the project folder.")
        self.device = DEVICE
        mode = _half_mode()
        self.half, self.auto_half = bool(mode), mode is None
        self.precision_note = ""
        self.last_calls = self.last_reused = self.reused = 0
        self._shown = False
        self._cache = OrderedDict()               # (scan, slice, window, precision) -> embedding on the CPU
        self.model = sam_model_registry["vit_b"](checkpoint=checkpoint).to(self.device).eval()

    def _timed(self, img, box, half, repeats=2):
        self.half = half
        self.segment_slice(img, box)                       # settle (first call after a switch is slower)
        torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(repeats):
            self.segment_slice(img, box)
        torch.cuda.synchronize()
        return (time.perf_counter() - t) / repeats

    def warmup(self):
        """Start up the GPU, and (unless forced) measure full vs half precision and keep the faster
        one that gives the same features. Half precision can be about twice as fast on GPUs that
        have fast half-precision units, but it is only used if it is checked to be accurate."""
        img, box = _test_image(), [64, 64, 192, 192]
        if self.device != "cuda" or not self.auto_half:
            self.segment_slice(img, box)
        else:
            t32, t16, rel, use = self._timed(img, box, False), float("nan"), float("nan"), False
            try:
                self.half = False
                e32, _, _ = self.embed(img)
                self.half = True
                e16, _, _ = self.embed(img)
                rel = float((e16 - e32).norm() / e32.norm().clamp(min=1e-8))
                t16 = self._timed(img, box, True)
                use = bool(torch.isfinite(e16).all()) and rel < 0.08 and t16 < 0.9 * t32
            except Exception:
                use = False
            self.half = use
            if DEBUG:
                print(f"[MedSAM] precision test: full {t32 * 1000:.0f} ms, half {t16 * 1000:.0f} ms, "
                      f"feature difference {rel:.3f} -> using {'half' if use else 'full'} precision")
        self.precision_note = "half precision" if self.half else "full precision"

    @torch.inference_mode()
    def embed(self, img_u8):
        """STEP 1, image encoder (the slow part, runs on the GPU).
        Input: ONE 2D uint8 slice (H, W). Output: embedding (1, 256, 64, 64), plus H and W."""
        H, W = img_u8.shape
        t = torch.from_numpy(img_u8).to(self.device).float()[None, None]       # (1, 1, H, W) on the GPU
        t = F.interpolate(t, size=(1024, 1024), mode="bicubic", align_corners=False).clamp(0, 255)
        t = (t - t.min()) / (t.max() - t.min()).clamp(min=1e-8)                # MedSAM expects 0..1
        t = t.expand(1, 3, 1024, 1024).contiguous()                            # (1, 3, 1024, 1024)
        with torch.autocast("cuda" if self.device == "cuda" else "cpu", dtype=torch.float16, enabled=self.half):
            emb = self.model.image_encoder(t)
        if DEBUG and not self._shown:
            print(f"[MedSAM] slice {H}x{W} uint8 -> encoder input {tuple(t.shape)} {t.dtype}, "
                  f"values {float(t.min()):.2f}..{float(t.max()):.2f} -> embedding {tuple(emb.shape)}")
        return emb.float(), H, W

    @torch.inference_mode()
    def decode(self, emb, box, H, W):
        """STEP 2, prompt encoder + mask decoder (fast).
        Input: the embedding and a box [x0, y0, x1, y1] in slice pixels. Output: a 2D bool mask (H, W)."""
        box_1024 = np.array(box, dtype=np.float32) / np.array([W, H, W, H], dtype=np.float32) * 1024
        box_t = torch.as_tensor(box_1024, dtype=torch.float, device=self.device)[None, None, :]
        sparse, dense = self.model.prompt_encoder(points=None, boxes=box_t, masks=None)
        logits, _ = self.model.mask_decoder(
            image_embeddings=emb, image_pe=self.model.prompt_encoder.get_dense_pe(),
            sparse_prompt_embeddings=sparse, dense_prompt_embeddings=dense, multimask_output=False)
        prob = F.interpolate(torch.sigmoid(logits), size=(H, W), mode="bilinear", align_corners=False)
        mask = (prob[0, 0] > 0.5).cpu().numpy()          # threshold on the GPU, copy back 1 byte per pixel
        if DEBUG and not self._shown:
            print(f"[MedSAM] box {np.round(box_1024).astype(int).tolist()} (1024 scale) -> prompt "
                  f"{tuple(sparse.shape)} + {tuple(dense.shape)} -> logits {tuple(logits.shape)} "
                  f"-> mask {mask.shape} ({100 * mask.mean():.1f}% of the slice)")
            self._shown = True
        return mask

    def segment_slice(self, img_u8, box, key=None):
        """Segment one 2D uint8 slice from a box [x0, y0, x1, y1] (MedSAM pipeline).
        With a key, the slow image-encoder result is remembered, so running the same slice again
        (another box, another speed setting) only costs the fast decoder."""
        H, W = img_u8.shape
        emb = self._cache_get(key)
        if emb is None:
            emb, _, _ = self.embed(img_u8)
            self._cache_put(key, emb)
        else:
            self.reused += 1
        return self.decode(emb, box, H, W)

    def _cache_get(self, key):
        v = self._cache.get(key) if key is not None else None
        if v is None:
            return None
        self._cache.move_to_end(key)
        return v.to(self.device).float()

    def _cache_put(self, key, emb, limit=120):         # 120 slices = about 240 MB of RAM
        if key is None:
            return
        self._cache[key] = emb.half().cpu()
        while len(self._cache) > limit:
            self._cache.popitem(last=False)

    def segment_volume(self, vol, k0, box, center=None, width=None, follow=True, step=1, spacing=None,
                       max_slices=60, min_area=20, growth_limit=3.0, agree=0.92, coarse=4, cache_key=None, progress=None):
        """Segment slice k0 from a box, then (optionally) follow the tumor up and down the stack.

        The model only ever sees one 2D slice at a time; this loop repeats it slice by slice.
        step=1  every slice (Best).        step=2, 3  every 2nd / 3rd slice, the rest interpolated.
        step=0  Smart: a coarse pass over every 4th slice, then the model is run on a slice in
                between only where the shape is changing (so accuracy stays close to Best).
        Each new slice is prompted with the previous mask's bounding box; following stops when the
        mask vanishes or jumps in size. progress(done, expected) is called after every model run.
        Returns a boolean mask volume shaped like `vol`.
        """
        nz = vol.shape[2]
        smart = int(step) == 0 and ndi is not None
        s = coarse if smart else (2 if int(step) == 0 else max(int(step), 1))
        expected = [estimate_calls(box, spacing, s, smart, follow, max_slices)]
        calls = [0]
        self.reused = 0

        def run(k, bbox):
            key = None if cache_key is None else (cache_key, k, round(float(center), 3), round(float(width), 3), self.half)
            m = self.segment_slice(slice_to_uint8(axial(vol, k), center, width), bbox, key)
            calls[0] += 1
            if calls[0] >= 0.85 * expected[0]:               # the estimate was low: stretch it
                expected[0] = int(calls[0] * 1.3) + 2
            if progress:
                progress(calls[0], expected[0])
            return m

        def next_slice(prev, k, pad):
            bbox = mask_bbox(prev, pad=pad)
            if bbox is None:
                return None
            m = run(k, bbox)
            if m.sum() < min_area or m.sum() > growth_limit * max(prev.sum(), 1):
                return None
            return m

        first = run(k0, box)
        computed = {k0: first}
        if follow:
            for d in (1, -1):
                prev, last, k = first, k0, k0 + d * s
                while 0 <= k < nz and abs(k - k0) <= max_slices:
                    m = next_slice(prev, k, 4 + 2 * (s - 1))
                    if m is None:
                        break
                    computed[k] = m
                    prev, last, k = m, k, k + d * s
                for j in range(1, s):                    # the tumor may end between two sampled slices
                    kk = last + d * j
                    if not 0 <= kk < nz or kk in computed:
                        break
                    m = next_slice(prev, kk, 4)
                    if m is None:
                        break
                    computed[kk] = m
                    prev, last = m, kk

            if smart:                                    # look closer only where the shape is changing
                sdfs = {}

                def sdf_of(k):
                    if k not in sdfs:
                        sdfs[k] = _sdf(computed[k])
                    return sdfs[k]

                def refine(ka, kb):
                    if kb - ka <= 1:
                        return
                    km = (ka + kb) // 2
                    t = (km - ka) / (kb - ka)
                    guess = ((1 - t) * sdf_of(ka) + t * sdf_of(kb)) > 0
                    bbox = mask_bbox(guess, pad=4) or mask_bbox(computed[ka] | computed[kb], pad=4)
                    m = run(km, bbox)
                    computed[km] = m
                    if dice(guess, m) < agree:           # the guess was wrong here: check both halves
                        refine(ka, km)
                        refine(km, kb)

                ks = sorted(computed)
                for ka, kb in zip(ks[:-1], ks[1:]):
                    refine(ka, kb)

        mask3d = np.zeros(vol.shape, dtype=bool)
        for k, m in computed.items():
            mask3d[:, :, k] = m.T
        if s > 1:
            fill_between(mask3d, computed)
        self.last_calls, self.last_reused = calls[0], self.reused
        return clean_mask(mask3d, k0) if follow else mask3d


def estimate_calls(box, spacing, step, smart, follow, max_slices):
    """Rough number of model runs, used only for the percentage and the time left."""
    if not follow:
        return 1
    if spacing:                                          # a tumor is about as deep as it is wide
        diam = max((box[2] - box[0]) * spacing[0], (box[3] - box[1]) * spacing[1])
        span = max(diam / max(spacing[2], 1e-6), 3.0)
    else:
        span = 20.0
    span = min(span, 2 * max_slices + 1)
    est = span / 4 * 1.8 + 2 if smart else span / step + step
    return int(max(est, 3))


# One shared model: loaded (and warmed up) once, in the background if possible.
_SEG, _LOCK = None, threading.Lock()


def is_loaded():
    return _SEG is not None


def get_segmenter():
    global _SEG
    with _LOCK:
        if _SEG is None:
            seg = TumorSegmenter()
            seg.warmup()
            _SEG = seg
        return _SEG


def precision():
    return _SEG.precision_note if _SEG is not None else ""


def clear_cache():
    if _SEG is not None:
        _SEG._cache.clear()


# --------------------------------------------------------- mask utilities
def _sdf(m):
    """Signed distance map: positive inside the mask, negative outside."""
    if not m.any():
        return np.full(m.shape, -1e3)
    return ndi.distance_transform_edt(m) - ndi.distance_transform_edt(~m)


def fill_between(mask3d, computed):
    """Fill skipped slices between segmented ones by blending the two neighbouring shapes."""
    ks = sorted(computed)
    for ka, kb in zip(ks[:-1], ks[1:]):
        if kb - ka <= 1:
            continue
        if ndi is None:                                  # no scipy: copy the nearest segmented slice
            for k in range(ka + 1, kb):
                mask3d[:, :, k] = (computed[ka] if k - ka <= kb - k else computed[kb]).T
            continue
        sa, sb = _sdf(computed[ka]), _sdf(computed[kb])
        for k in range(ka + 1, kb):
            t = (k - ka) / (kb - ka)
            mask3d[:, :, k] = (((1 - t) * sa + t * sb) > 0).T


def clean_mask(mask, k0):
    """Tidy a 3D result: keep the piece connected to the start slice and fill holes in each slice."""
    if ndi is None or not mask.any():
        return mask
    lab, n = ndi.label(mask)
    if n > 1:
        ids = np.unique(lab[:, :, k0][lab[:, :, k0] > 0])
        if len(ids):
            mask = np.isin(lab, ids)
    for k in np.where(mask.any(axis=(0, 1)))[0]:
        mask[:, :, k] = ndi.binary_fill_holes(mask[:, :, k])
    return mask


def mask_bbox(mask, pad=0):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    h, w = mask.shape
    return [max(xs.min() - pad, 0), max(ys.min() - pad, 0),
            min(xs.max() + pad, w - 1), min(ys.max() + pad, h - 1)]


def box_from_mask(mask3d, pad=3):
    """Tight axial box around a mask on the slice where it is largest. Returns (slice, [x0, y0, x1, y1])."""
    k = int(np.argmax(mask3d.sum(axis=(0, 1))))
    return k, [float(v) for v in mask_bbox(mask3d[:, :, k].T, pad=pad)]


# ----------------------------------------------------------------- metrics
def volume_cc(mask3d, spacing):
    """Tumor volume in cubic centimetres (cc). 1 cc = 1 mL = 1000 mm^3."""
    return round(float(mask3d.sum()) * spacing[0] * spacing[1] * spacing[2] / 1000.0, 3)


def mask_stats(mask3d, spacing):
    zs = np.where(mask3d.any(axis=(0, 1)))[0]
    return {
        "voxels": int(mask3d.sum()),
        "volume_cc": volume_cc(mask3d, spacing),
        "slices": int(len(zs)),
        "slice_range": (int(zs.min()), int(zs.max())) if len(zs) else None,
    }


def dice(a, b):
    """Dice overlap between two boolean arrays (1.0 = identical)."""
    total = int(a.sum()) + int(b.sum())
    return 1.0 if total == 0 else 2.0 * int(np.logical_and(a, b).sum()) / total