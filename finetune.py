"""finetune.py - adapt MedSAM to YOUR tumor data.

What it does
  Trains only the small mask decoder of MedSAM (the big image encoder stays frozen), using your
  scans and their actual-tumor files. It reports the Dice score on held-out cases before and
  after training and writes medsam_finetuned.pth only if the new model is clearly better.
  The viewer uses that file automatically (delete or rename it to go back to plain MedSAM).

Folder layout (file names must match; the tumor file may add a suffix such as _tumor or _mask)
  scans/   DATA_001.nrrd   DATA_002.nrrd   ...
  tumors/  MASK_001.nrrd   MASK_002.nrrd   ...      same size as the scan, tumor voxels > 0
  (files are paired by the number after the underscore; matching names also work)

Run (one folder pair: 20% of the cases are held back for testing)
  python finetune.py --scans D:/data/scans --masks D:/data/tumors

Run (best: train on your train folders and test on your separate test folders, all on one line)
  python finetune.py --scans D:/dataset/train/Train_Images --masks D:/dataset/train/Train_Masks --test-scans D:/dataset/test/Test_Images --test-masks D:/dataset/test/Test_Masks

Needs several cases (ideally 20 or more). With only 1 to 3 cases it just memorises them and
will not help on new scans. Research use only.
"""
import argparse
import glob
import os
import random
import re
import time

import numpy as np
import torch
import torch.nn.functional as F

import segment

EXTS = (".nrrd", ".nhdr")


# ------------------------------------------------------------------ data
def list_files(folder):
    return sorted(p for p in glob.glob(os.path.join(folder, "*")) if p.lower().endswith(EXTS))


def find_pairs(scans_dir, masks_dir):
    """Match every scan with its tumor file: first by the number after the underscore
    (DATA_130 <-> MASK_130), otherwise by name (DATA_13 never matches DATA_130)."""
    masks = list_files(masks_dir)
    by_number = {}
    for m in masks:
        n = segment.case_number(m)
        if n is not None:
            by_number.setdefault(n, m)
    pairs = []
    for s in list_files(scans_dir):
        n = segment.case_number(s)
        if n is not None and n in by_number and os.path.abspath(by_number[n]) != os.path.abspath(s):
            pairs.append((s, by_number[n]))
            continue
        stem = os.path.splitext(os.path.basename(s))[0].lower()
        pat = re.compile(r"(?<![0-9a-z])" + re.escape(stem) + r"(?![0-9])")
        others = [m for m in masks if os.path.abspath(m) != os.path.abspath(s)]
        exact = [m for m in others if os.path.splitext(os.path.basename(m))[0].lower() == stem]
        loose = [m for m in others if pat.search(os.path.splitext(os.path.basename(m))[0].lower())]
        hit = (exact or loose or [None])[0]
        if hit:
            pairs.append((s, hit))
    return pairs


def default_window(vol):
    """Same default window the viewer uses (1st to 99th percentile)."""
    p1, p99 = np.percentile(vol, [1, 99])
    return (p1 + p99) / 2, max(p99 - p1, 1e-6)


def embed_case(seg, vol, mask, ks, cap):
    """Run the (frozen) image encoder once per tumor slice and keep the result."""
    if len(ks) > cap:
        ks = ks[np.linspace(0, len(ks) - 1, cap).round().astype(int)]
    center, width = default_window(vol)
    out = []
    for k in ks:
        img = segment.slice_to_uint8(segment.axial(vol, int(k)), center, width)
        gt = mask[:, :, k].T
        bbox = segment.mask_bbox(gt, pad=0)
        emb, H, W = seg.embed(img)
        gt256 = F.interpolate(torch.from_numpy(gt.astype(np.float32))[None, None], size=(256, 256),
                              mode="bilinear", align_corners=False)[0, 0] > 0.5
        out.append({
            "emb": emb[0].half().cpu().clone(),            # clone: a normal tensor, safe to train on
            "gt": gt256.float(),
            "box": np.array(bbox, dtype=np.float32) / np.array([W, H, W, H], dtype=np.float32) * 1024,
        })
    return out


def jitter_box(box, amount):
    """Random box noise so the model learns to cope with a hand-drawn, imperfect box."""
    b = np.clip(box + np.random.uniform(-amount, amount, 4).astype(np.float32), 0, 1024)
    return b if (b[2] - b[0] >= 4 and b[3] - b[1] >= 4) else box


# ----------------------------------------------------------------- model
def dice_t(p, g, eps=1.0):
    return (2 * (p * g).sum() + eps) / (p.sum() + g.sum() + eps)


def run_decoder(model, emb, box, device, dense_pe):
    e = emb[None].float().to(device)                                   # (1, 256, 64, 64)
    b = torch.as_tensor(box, dtype=torch.float, device=device)[None, None, :]
    with torch.no_grad():
        sparse, dense = model.prompt_encoder(points=None, boxes=b, masks=None)
    logits, _ = model.mask_decoder(image_embeddings=e, image_pe=dense_pe, sparse_prompt_embeddings=sparse,
                                   dense_prompt_embeddings=dense, multimask_output=False)
    return logits                                                      # (1, 1, 256, 256)


@torch.no_grad()
def evaluate(model, samples, device, dense_pe):
    """Mean Dice using exact tumor boxes (no noise)."""
    if not samples:
        return float("nan")
    model.mask_decoder.eval()
    scores = []
    for s in samples:
        pred = (torch.sigmoid(run_decoder(model, s["emb"], s["box"], device, dense_pe))[0, 0] > 0.5).float()
        scores.append(float(dice_t(pred, s["gt"].to(device))))
    return float(np.mean(scores))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Fine-tune the MedSAM mask decoder on your own tumors.")
    ap.add_argument("--scans", required=True, help="folder with the scan .nrrd files")
    ap.add_argument("--masks", required=True, help="folder with the actual-tumor .nrrd files")
    ap.add_argument("--out", default=segment.FINETUNED, help="where to write the new weights")
    ap.add_argument("--init", default=segment.BASE_CHECKPOINT, help="weights to start from")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--jitter", type=float, default=10.0, help="box noise in pixels (1024 scale)")
    ap.add_argument("--max-slices", type=int, default=1500, help="cap on stored slices (about 2 MB of RAM each)")
    ap.add_argument("--min-area", type=int, default=30, help="ignore slices with fewer tumor pixels")
    ap.add_argument("--val-frac", type=float, default=0.2, help="share of cases kept for testing")
    ap.add_argument("--test-scans", help="optional: separate folder of test scans (never used for training)")
    ap.add_argument("--test-masks", help="optional: separate folder of test tumors")
    args = ap.parse_args()

    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)
    device = segment.DEVICE
    print(f"Device: {segment.device_info()}")
    if device != "cuda":
        print("Warning: no GPU in use, this will be very slow.")

    pairs = find_pairs(args.scans, args.masks)
    print(f"Found {len(pairs)} scan/tumor pairs:")
    for s, m in pairs:
        print(f"  {os.path.basename(s)}  <->  {os.path.basename(m)}")
    if len(pairs) < 2:
        raise SystemExit("Need at least 2 cases. Check the folders and file names.")
    if len(pairs) < 10:
        print("Warning: fewer than 10 cases. The result may not carry over to new scans.")

    if args.test_scans and args.test_masks:                     # a separate test folder: the fairest check
        val_pairs = find_pairs(args.test_scans, args.test_masks)
        if not val_pairs:
            raise SystemExit("No scan/tumor pairs found in the test folders.")
        test_files = {os.path.abspath(s) for s, _ in val_pairs}
        train_pairs = [p for p in pairs if os.path.abspath(p[0]) not in test_files]
        print(f"Test folder: {len(val_pairs)} pairs, kept out of training. Training on {len(train_pairs)} pairs.")
    else:
        random.shuffle(pairs)
        n_val = max(1, round(len(pairs) * args.val_frac)) if len(pairs) >= 5 else 0
        val_pairs, train_pairs = pairs[:n_val], pairs[n_val:]
        if not n_val:
            print("Warning: too few cases to hold any back, so the score below is measured on the training data.")

    seg = segment.TumorSegmenter(checkpoint=args.init)
    model = seg.model
    cap = max(args.max_slices // max(len(train_pairs) + len(val_pairs), 1), 5)
    train, val = [], []
    t0 = time.perf_counter()
    for name, group, bucket in (("train", train_pairs, train), ("test", val_pairs, val)):
        for s, m in group:
            try:
                vol, _ = segment.load_nrrd(s)
                mask = segment.load_mask(m)
            except Exception as e:
                print(f"  skipped {os.path.basename(s)}: {e}")
                continue
            if vol.shape != mask.shape:
                print(f"  skipped {os.path.basename(s)}: scan {vol.shape} and tumor {mask.shape} differ in size")
                continue
            ks = np.where(mask.sum(axis=(0, 1)) >= args.min_area)[0]
            if not len(ks):
                print(f"  skipped {os.path.basename(s)}: no tumor large enough")
                continue
            bucket.extend(embed_case(seg, vol, mask, ks, cap))
            print(f"  [{name}] {os.path.basename(s)}: {len(ks)} tumor slices, "
                  f"{len(train) + len(val)} stored, {time.perf_counter() - t0:.0f} s")
    if not train:
        raise SystemExit("No usable training slices.")
    check = val or train
    print(f"Training slices: {len(train)} | test slices: {len(val)}")

    for p in model.parameters():
        p.requires_grad = False
    for p in model.mask_decoder.parameters():
        p.requires_grad = True
    with torch.no_grad():
        dense_pe = model.prompt_encoder.get_dense_pe()
    opt = torch.optim.AdamW(model.mask_decoder.parameters(), lr=args.lr, weight_decay=0.01)

    baseline = evaluate(model, check, device, dense_pe)
    print(f"Dice before training: {baseline:.3f}")
    best, best_state = baseline, None
    for epoch in range(1, args.epochs + 1):
        model.mask_decoder.train()
        order = np.random.permutation(len(train))
        total = 0.0
        for start in range(0, len(order), args.batch):
            idxs = order[start:start + args.batch]
            opt.zero_grad()
            for i in idxs:
                s = train[i]
                logits = run_decoder(model, s["emb"], jitter_box(s["box"], args.jitter), device, dense_pe)
                g = s["gt"].to(device)[None, None]
                loss = F.binary_cross_entropy_with_logits(logits, g) + (1 - dice_t(torch.sigmoid(logits), g))
                (loss / len(idxs)).backward()
                total += float(loss)
            opt.step()
        score = evaluate(model, check, device, dense_pe)
        flag = ""
        if score > best:
            best, flag = score, "  <- best so far"
            best_state = {k: v.detach().cpu().clone() for k, v in model.mask_decoder.state_dict().items()}
        print(f"Epoch {epoch:3d}/{args.epochs}  loss {total / len(train):.4f}  dice {score:.3f}{flag}")

    print("-" * 60)
    if best_state is not None and best > baseline + 0.005:
        model.mask_decoder.load_state_dict(best_state)
        torch.save(model.state_dict(), args.out)
        print(f"Dice {baseline:.3f} -> {best:.3f}. Saved {args.out}")
        print("The viewer will use it automatically. Delete that file to go back to plain MedSAM.")
    else:
        print(f"No clear improvement (before {baseline:.3f}, best {best:.3f}). Nothing was saved, "
              "so the viewer keeps using the original MedSAM.")
        print("More cases usually help more than more epochs.")


if __name__ == "__main__":
    main()