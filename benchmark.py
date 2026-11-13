"""benchmark.py - measure on YOUR computer what makes MedSAM faster.

Run:  python benchmark.py
It needs medsam_vit_b.pth next to it (same as the viewer) and takes about a minute.

It answers three questions with real timings:
  1. How long does one slice take, and is half precision faster on this GPU?
  2. Do two threads (e.g. the up and the down direction at once) beat one thread?
  3. How much does the embedding cache save when a slice is run a second time?
"""
import threading
import time

import numpy as np
import torch

import segment

N = 6                                                   # slices per timing


def sync():
    if segment.DEVICE == "cuda" and torch.cuda.is_available():
        torch.cuda.synchronize()


def timed(fn):
    fn()                                                # settle
    sync()
    t = time.perf_counter()
    fn()
    sync()
    return time.perf_counter() - t


def main():
    print(f"Device: {segment.device_info()} | CPU threads used by PyTorch: {torch.get_num_threads()}")
    print("Loading the model and running its start-up check...")
    seg = segment.get_segmenter()
    print(f"Chosen precision: {seg.precision_note}")
    img = np.kron(segment._test_image(), np.ones((2, 2), np.uint8))        # a 512 x 512 slice
    box = [128, 128, 384, 384]

    def run(n=N):
        for _ in range(n):
            seg.segment_slice(img, box)

    print("\n1. One slice, one thread")
    base = timed(run) / N
    print(f"   {seg.precision_note}: {base:.2f} s per slice")
    if segment.DEVICE == "cuda" and torch.cuda.is_available():
        keep = seg.half
        for half in (False, True):
            seg.half = half
            try:
                print(f"   {'half' if half else 'full'} precision forced: {timed(run) / N:.2f} s per slice")
            except Exception as e:
                print(f"   {'half' if half else 'full'} precision failed: {e}")
        seg.half = keep
        print(f"   GPU memory used at most: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")

        print("\n2. Two threads at once (each on its own CUDA stream)")
        streams = [torch.cuda.Stream(), torch.cuda.Stream()]

        def work(st):
            with torch.cuda.stream(st):
                for _ in range(N // 2):
                    seg.segment_slice(img, box)
                st.synchronize()

        def two():
            ts = [threading.Thread(target=work, args=(st,)) for st in streams]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

        t2 = timed(two)
        speed = (base * N) / t2
        print(f"   {N} slices: one thread {base * N:.2f} s, two threads {t2:.2f} s -> {speed:.2f}x")
        print("   " + ("Two threads help a little on this GPU." if speed >= 1.15 else
                       "Two threads do not help: the GPU is already fully busy with one."))
    else:
        print("\n2. Skipped (no GPU in use).")

    print("\n3. Same slice a second time (embedding cache)")
    seg.segment_slice(img, box, key="bench")
    sync()
    t = time.perf_counter()
    seg.segment_slice(img, box, key="bench")
    sync()
    again = time.perf_counter() - t
    print(f"   first run {base:.2f} s, repeat {again * 1000:.0f} ms")


if __name__ == "__main__":
    main()