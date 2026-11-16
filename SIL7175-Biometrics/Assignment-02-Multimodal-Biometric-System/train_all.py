"""
Master Training Launcher — runs both training steps in the correct order.

Run this ONCE before executing main.py:

    (venv) > python train_all.py

This script:
1. Trains AlexNet_N (Writer-Independent) on BHSig Development Set
2. Fine-tunes SE-AlexNet on biometric face + iris identity classification

Both steps use full GPU resources where available.
Trained weights are saved to the results/ directory and auto-loaded by main.py.

Individual scripts (train_wi_alexnet.py, train_se_alexnet.py) can also be called
directly with custom hyper-parameters.

Optional CLI flags:
  --wi_epochs  N      Epochs for WI AlexNet_N     (default: 20)
  --se_epochs  N      Epochs for SE-AlexNet FT     (default: 20)
  --batch_size N      Batch size for both scripts  (default: 16)
  --wi_lr      F      WI initial learning rate     (default: 0.001)
  --se_lr      F      SE warm-up learning rate     (default: 0.0005)
  --warmup     N      SE-AlexNet warm-up epochs    (default: 6)
  --skip_wi           Skip WI training (if already done)
  --skip_se           Skip SE-AlexNet training (if already done)
"""

import os
import sys
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.logger import log


def check_weights_exist():
    """Reports which model weights already exist in the results directory."""
    wi_path = os.path.join(Config.RESULTS_DIR, "wi_alexnet_trained.pth")
    se_path = os.path.join(Config.RESULTS_DIR, "se_alexnet_finetuned.pth")
    log.info(f"  WI AlexNet_N  : {'EXISTS ✓' if os.path.exists(wi_path) else 'MISSING'} → {wi_path}")
    log.info(f"  SE-AlexNet    : {'EXISTS ✓' if os.path.exists(se_path) else 'MISSING'} → {se_path}")
    return os.path.exists(wi_path), os.path.exists(se_path)


def run_wi_training(wi_epochs, batch_size, wi_lr):
    """
    Invokes the WI AlexNet_N training pipeline directly (not via subprocess)
    so we share the same Python process, GPU context, and logging output.
    """
    import torch
    from train_wi_alexnet import (
        get_exploitation_subject_ids,
        collect_dev_set_dirs,
        train_wi_alexnet,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    Config.setup_directories()
    output_path = os.path.join(Config.RESULTS_DIR, "wi_alexnet_trained.pth")

    log.phase("Step 1 — WI AlexNet_N Training")

    bengali_exploit_ids = get_exploitation_subject_ids(
        Config.MAPPING_FILE, "Dataset_1", "Signature_Source_ID"
    )
    hindi_exploit_ids = get_exploitation_subject_ids(
        Config.MAPPING_FILE, "Dataset_2", "Signature_Source_ID"
    )
    bengali_dev = collect_dev_set_dirs(Config.BHSIG_BENGALI_DIR, bengali_exploit_ids)
    hindi_dev   = collect_dev_set_dirs(Config.BHSIG_HINDI_DIR,   hindi_exploit_ids)
    all_dev_dirs = bengali_dev + hindi_dev

    log.info(f"Development Set: {len(bengali_dev)} Bengali + {len(hindi_dev)} Hindi subjects")

    if not all_dev_dirs:
        log.error("No Development Set subjects found — WI training aborted.")
        return False

    train_wi_alexnet(
        subject_dirs        = all_dev_dirs,
        num_epochs          = wi_epochs,
        batch_size          = batch_size,
        learning_rate       = wi_lr,
        output_weights_path = output_path,
        device              = device,
    )
    log.phase_done("Step 1 — WI AlexNet_N Training")
    return True


def run_se_training(se_epochs, batch_size, se_lr, warmup_epochs):
    """
    Invokes the SE-AlexNet fine-tuning pipeline directly.
    """
    import torch
    import pandas as pd
    from train_se_alexnet import train_se_alexnet

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    Config.setup_directories()
    output_path = os.path.join(Config.RESULTS_DIR, "se_alexnet_finetuned.pth")

    log.phase("Step 2 — SE-AlexNet Fine-Tuning")

    if not os.path.exists(Config.MAPPING_FILE):
        log.error(f"Mapping CSV not found: {Config.MAPPING_FILE}")
        log.error("Run  python main.py  once first to generate the mapping.")
        return False

    mapping_df = pd.read_csv(Config.MAPPING_FILE, dtype=str)
    log.info(f"Mapping loaded: {len(mapping_df)} virtual users")

    train_se_alexnet(
        mapping_df          = mapping_df,
        num_epochs          = se_epochs,
        batch_size          = batch_size,
        learning_rate       = se_lr,
        warmup_epochs       = warmup_epochs,
        output_weights_path = output_path,
        device              = device,
    )
    log.phase_done("Step 2 — SE-AlexNet Fine-Tuning")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Master launcher: train WI AlexNet_N then fine-tune SE-AlexNet"
    )
    parser.add_argument("--wi_epochs",  type=int,   default=20,     help="WI training epochs")
    parser.add_argument("--se_epochs",  type=int,   default=20,     help="SE FT epochs")
    parser.add_argument("--batch_size", type=int,   default=16,     help="Batch size (both models)")
    parser.add_argument("--wi_lr",      type=float, default=0.001,  help="WI learning rate")
    parser.add_argument("--se_lr",      type=float, default=0.0005, help="SE warm-up LR")
    parser.add_argument("--warmup",     type=int,   default=6,      help="SE warm-up epochs")
    parser.add_argument("--skip_wi",    action="store_true",        help="Skip WI training")
    parser.add_argument("--skip_se",    action="store_true",        help="Skip SE-AlexNet FT")
    args = parser.parse_args()

    import torch
    print()
    print("=" * 62)
    print("  Biometric Training Master Launcher")
    print("  SIL775/7175 Assignment 2")
    print("=" * 62)
    print()

    # Report GPU info once at the top
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.model(f"Compute device : {device}")
    if device.type == "cuda":
        for gpu_idx in range(torch.cuda.device_count()):
            gpu_name = torch.cuda.get_device_name(gpu_idx)
            gpu_mem  = torch.cuda.get_device_properties(gpu_idx).total_memory // (1024**3)
            log.model(f"  GPU {gpu_idx} : {gpu_name}  ({gpu_mem} GB VRAM)")
    else:
        log.warn("No CUDA GPU detected — training will run on CPU (very slow).")
        log.warn("Install CUDA-compatible PyTorch: https://pytorch.org/get-started/locally/")

    log.step("Current Weight Status")
    wi_exists, se_exists = check_weights_exist()

    # ---------------------------------------------------------------
    # Step 1: WI AlexNet_N
    # ---------------------------------------------------------------
    if args.skip_wi:
        log.info("--skip_wi flag set: skipping WI AlexNet_N training")
    elif wi_exists:
        log.warn("wi_alexnet_trained.pth already exists.")
        response = input("Re-train WI AlexNet_N? [y/N] : ").strip().lower()
        if response == 'y':
            t0 = time.time()
            success = run_wi_training(args.wi_epochs, args.batch_size, args.wi_lr)
            elapsed = time.time() - t0
            if success:
                log.ok(f"WI training complete in {elapsed:.0f}s")
        else:
            log.info("Keeping existing WI weights.")
    else:
        t0 = time.time()
        success = run_wi_training(args.wi_epochs, args.batch_size, args.wi_lr)
        elapsed = time.time() - t0
        if success:
            log.ok(f"WI training complete in {elapsed:.0f}s")

    # ---------------------------------------------------------------
    # Step 2: SE-AlexNet fine-tuning
    # ---------------------------------------------------------------
    if args.skip_se:
        log.info("--skip_se flag set: skipping SE-AlexNet fine-tuning")
    elif se_exists:
        log.warn("se_alexnet_finetuned.pth already exists.")
        response = input("Re-train SE-AlexNet? [y/N] : ").strip().lower()
        if response == 'y':
            t0 = time.time()
            success = run_se_training(args.se_epochs, args.batch_size, args.se_lr, args.warmup)
            elapsed = time.time() - t0
            if success:
                log.ok(f"SE-AlexNet fine-tuning complete in {elapsed:.0f}s")
        else:
            log.info("Keeping existing SE-AlexNet weights.")
    else:
        t0 = time.time()
        success = run_se_training(args.se_epochs, args.batch_size, args.se_lr, args.warmup)
        elapsed = time.time() - t0
        if success:
            log.ok(f"SE-AlexNet fine-tuning complete in {elapsed:.0f}s")

    # ---------------------------------------------------------------
    # Final status
    # ---------------------------------------------------------------
    print()
    print("=" * 62)
    log.step("Final Weight Status")
    wi_ready, se_ready = check_weights_exist()
    print()
    if wi_ready and se_ready:
        print("  ✓ All model weights trained and ready.")
        print("  Next:  python main.py")
    else:
        print("  ⚠  Some weights are still missing. Check logs above.")
    print("=" * 62)


if __name__ == "__main__":
    main()
