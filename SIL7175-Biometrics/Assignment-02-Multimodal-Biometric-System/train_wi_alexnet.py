"""
Writer-Independent (WI) AlexNet_N Training Script.

PURPOSE
-------
Task 2.2 of the assignment requires AlexNet_N to learn a Writer-Independent
feature space by training on a Development Set — BHSig subjects that are NOT
part of the 100-user Exploitation Set used in main.py.  After training, the
model weights are frozen and FC2 activations serve as WI feature vectors for
the per-user SVM classifiers.

RUN THIS BEFORE main.py.

OUTPUT
------
results/wi_alexnet_trained.pth  ← auto-loaded by main.py on next run

USAGE
-----
    (venv) > python train_wi_alexnet.py
    (venv) > python train_wi_alexnet.py --epochs 30 --batch_size 32 --lr 0.0005
"""

import os
import sys
import argparse

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

# Project root on sys.path so src.* imports resolve from any working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.logger import log
from src.features.deep_wi_alexnet import AlexNet_N
from src.preprocessing.signature_preprocessor import SignaturePreprocessor

# ─────────────────────────────────────────────────────────────
# Tuneable hyper-parameters (also exposed as CLI flags)
# ─────────────────────────────────────────────────────────────
DEFAULT_EPOCHS       = 20
DEFAULT_BATCH_SIZE   = 16
DEFAULT_LR           = 0.001
LR_STEP_SIZE         = 7     # Halve LR every 7 epochs (step-decay)
LR_GAMMA             = 0.5
# BHSig Bengali: 24 genuine + 30 forgeries per subject.
# We cap at 24 to cap per-subject contribution and save RAM.
MAX_GENUINE_PER_SUBJ = 24


# ─────────────────────────────────────────────────────────────
# Dataset
# ─────────────────────────────────────────────────────────────
class BHSigWIDataset(Dataset):
    """
    Maps each BHSig Development-Set subject directory → one integer class label.

    GENUINE-FILE DETECTION
    ----------------------
    BHSig filename conventions:
        Bengali: B-S-{subject}-G-{num}.tif  (genuine)
                 B-S-{subject}-F-{num}.tif  (forgery)
        Hindi  : H-S-{subject}-G-{num}.tif  (genuine)
                 H-S-{subject}-F-{num}.tif  (forgery)
    Genuines are identified by checking '-G-' in the uppercase filename.
    This is the only safe approach — the filenames do NOT start with 'G'.

    Only genuine signatures are used for WI training because the goal is
    to learn stroke-pattern representations, NOT to classify genuine vs. forgery.
    """

    SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')

    def __init__(self, subject_dirs: list, preprocessor: SignaturePreprocessor):
        self.samples      = []      # (absolute_image_path, integer_class_label)
        self.preprocessor = preprocessor
        self.num_classes  = 0

        empty_subject_count = 0

        for class_label, subject_dir in enumerate(subject_dirs):
            # Collect genuine image files.  '-G-' in upper-case name is the safe match.
            genuine_files = sorted([
                fname for fname in os.listdir(subject_dir)
                if fname.lower().endswith(self.SUPPORTED_EXTENSIONS)
                and '-G-' in fname.upper()
            ])

            if not genuine_files:
                # Some subject directories might only contain forgeries or be empty.
                # Log and skip rather than letting the class label go unrepresented.
                log.warn(f"    No genuine signatures in: {os.path.basename(subject_dir)} — skipping")
                empty_subject_count += 1
                continue

            # Use this subject as a valid class
            capped_files = genuine_files[:MAX_GENUINE_PER_SUBJ]
            for image_filename in capped_files:
                full_path = os.path.join(subject_dir, image_filename)
                self.samples.append((full_path, self.num_classes))

            self.num_classes += 1

        log.info(f"  WI Dataset constructed: {len(self.samples)} samples "
                 f"across {self.num_classes} valid subject classes "
                 f"({empty_subject_count} subjects skipped — no genuine files)")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int):
        image_path, class_label = self.samples[idx]

        # Returns a float32 ndarray of shape (170, 242) with ink=1, bg=0
        binary_array = self.preprocessor.process_signature(image_path)

        # Add channel dimension → (1, 170, 242) float32 tensor
        tensor = torch.tensor(binary_array, dtype=torch.float32).unsqueeze(0)
        return tensor, class_label


# ─────────────────────────────────────────────────────────────
# Subject-directory helpers
# ─────────────────────────────────────────────────────────────
def get_exploitation_subject_ids(mapping_csv_path: str,
                                  dataset_label: str,
                                  source_id_column: str) -> set:
    """
    Reads the chimeric mapping CSV and returns all Signature_Source_IDs
    committed to the Exploitation Set for the specified dataset label.
    These IDs are folder names (e.g. '001', '045') and must be excluded
    from the Development Set used for WI training.
    """
    import pandas as pd
    if not os.path.exists(mapping_csv_path):
        log.warn(f"Mapping CSV not found: {mapping_csv_path}  (no IDs will be excluded)")
        return set()
    df      = pd.read_csv(mapping_csv_path, dtype=str)
    subset  = df[df['Dataset'] == dataset_label]
    ids     = set(subset[source_id_column].dropna().unique())
    return ids


def collect_dev_set_dirs(bhsig_root: str, exploit_ids: set) -> list:
    """
    Walks the BHSig root directory and returns absolute paths of every
    subject subdirectory whose name is NOT in exploit_ids.
    """
    dev_dirs = []
    if not os.path.isdir(bhsig_root):
        log.warn(f"BHSig root directory not found: {bhsig_root}")
        return dev_dirs
    for folder_name in sorted(os.listdir(bhsig_root)):
        full_path = os.path.join(bhsig_root, folder_name)
        if not os.path.isdir(full_path):
            continue
        if folder_name in exploit_ids:
            continue     # Skip — used by Exploitation Set
        dev_dirs.append(full_path)
    return dev_dirs


# ─────────────────────────────────────────────────────────────
# Training function
# ─────────────────────────────────────────────────────────────
def train_wi_alexnet(subject_dirs: list, num_epochs: int, batch_size: int,
                     learning_rate: float, output_weights_path: str,
                     device: torch.device):
    """
    Trains AlexNet_N end-to-end on all development-set subjects.
    Saves the best-accuracy state_dict (weights on CPU) to output_weights_path.

    Multi-GPU note: wraps the model in nn.DataParallel when multiple CUDA
    devices are available so all GPUs are utilised.
    """
    if len(subject_dirs) == 0:
        log.error("No Development Set subject directories supplied. Training aborted.")
        log.error("Verify BHSig paths in config.py and that subjects beyond your 100 "
                  "Exploitation Set exist in the directory.")
        sys.exit(1)

    log.info(f"Development Set subject directories available: {len(subject_dirs)}")

    preprocessor  = SignaturePreprocessor()
    train_dataset = BHSigWIDataset(subject_dirs, preprocessor)

    if len(train_dataset) == 0:
        log.error("BHSigWIDataset is empty. "
                  "Ensure BHSig subject directories contain genuine files (filenames with '-G-').")
        sys.exit(1)

    num_wi_classes = train_dataset.num_classes
    log.info(f"Number of WI classes (subjects with ≥1 genuine image): {num_wi_classes}")

    # num_workers=0 on Windows is the only safe option when the Dataset uses cv2
    # inside __getitem__; cv2 captures are not picklable across process boundaries.
    train_loader = DataLoader(
        train_dataset,
        batch_size  = batch_size,
        shuffle     = True,
        num_workers = 0,
        pin_memory  = device.type == "cuda",
        drop_last   = True,    # Keep all batch sizes equal (BatchNorm1d requires >1 sample)
    )

    # Guard: drop_last=True produces 0 batches when total samples < batch_size.
    # Bengali Dev Set = ~3 subjects × 24 = 72 samples; batch=16 → 4 batches. Fine.
    # If somehow the dev set is very small, bail with a clear message.
    if len(train_loader) == 0:
        log.error(
            f"Training DataLoader is empty: {total_samples} samples with batch_size={batch_size} "
            f"and drop_last=True yields 0 complete batches. "
            f"Lower --batch_size or add more Development Set subjects."
        )
        sys.exit(1)

    # Initialise the model with the correct output dimension
    model = AlexNet_N(num_classes=num_wi_classes)

    # Use all available GPUs via DataParallel
    num_gpus = torch.cuda.device_count()
    if num_gpus > 1:
        log.model(f"Using {num_gpus} GPUs via nn.DataParallel")
        model = nn.DataParallel(model)
    model = model.to(device)

    # Enable cuDNN auto-tuner: benchmarks conv algorithms per input shape.
    # Gives 20–30% GPU throughput boost for fixed input size (170×242 → 6×6 after pooling).
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    log.model(f"AlexNet_N ready — {num_wi_classes} WI classes, training from random init")

    criterion    = nn.CrossEntropyLoss()
    optimizer    = optim.Adam(model.parameters(), lr=learning_rate)
    lr_scheduler = optim.lr_scheduler.StepLR(
        optimizer, step_size=LR_STEP_SIZE, gamma=LR_GAMMA
    )

    total_samples   = len(train_dataset)
    batches_per_ep  = len(train_loader)
    best_accuracy   = 0.0
    best_weights    = None    # Stored on CPU to avoid doubling VRAM usage

    log.step("WI Training Loop")
    log.info(f"  Total samples   : {total_samples}")
    log.info(f"  Batches / epoch : {batches_per_ep}")
    log.info(f"  Epochs          : {num_epochs}")
    log.info(f"  Initial LR      : {learning_rate}")
    log.info(f"  LR step / gamma : every {LR_STEP_SIZE} epochs × {LR_GAMMA}")
    log.separator()

    for epoch_num in range(1, num_epochs + 1):
        model.train()

        epoch_loss    = 0.0
        epoch_correct = 0
        epoch_total   = 0

        for batch_idx, (batch_images, batch_labels) in enumerate(train_loader, start=1):
            batch_images = batch_images.to(device, non_blocking=True)
            batch_labels = batch_labels.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)   # Slightly faster than assigning zero
            logits     = model(batch_images)
            batch_loss = criterion(logits, batch_labels)
            batch_loss.backward()
            optimizer.step()

            # Accumulate metrics
            epoch_loss    += batch_loss.item() * batch_images.size(0)
            predicted      = logits.argmax(dim=1)
            epoch_correct += (predicted == batch_labels).sum().item()
            epoch_total   += batch_images.size(0)

            # Live per-batch progress (every 5 batches or last batch)
            if batch_idx % 5 == 0 or batch_idx == batches_per_ep:
                running_acc = 100.0 * epoch_correct / max(epoch_total, 1)
                log.progress(
                    batch_idx, batches_per_ep,
                    label=f"E{epoch_num:02d}/{num_epochs}  "
                          f"loss={batch_loss.item():.4f}  "
                          f"acc={running_acc:.1f}%"
                )

        # Step the LR scheduler at END of each epoch (before printing the LR)
        lr_scheduler.step()
        current_lr = lr_scheduler.get_last_lr()[0]

        epoch_avg_loss = epoch_loss    / max(epoch_total, 1)
        epoch_accuracy = 100.0 * epoch_correct / max(epoch_total, 1)

        log.ok(
            f"Epoch {epoch_num:3d}/{num_epochs}  "
            f"loss={epoch_avg_loss:.4f}  "
            f"acc={epoch_accuracy:.2f}%  "
            f"lr={current_lr:.2e}"
        )

        # Keep the highest-accuracy checkpoint on CPU to avoid GPU VRAM doubling
        if epoch_accuracy > best_accuracy:
            best_accuracy = epoch_accuracy
            # Unwrap DataParallel before state_dict so the saved file is framework-agnostic
            raw_model     = model.module if isinstance(model, nn.DataParallel) else model
            best_weights  = {k: v.cpu().clone() for k, v in raw_model.state_dict().items()}
            log.ok(f"  New best @ epoch {epoch_num}: {best_accuracy:.2f}% — checkpoint saved")

    # ── Save ─────────────────────────────────────────────────────
    log.step("Saving Best Weights")
    os.makedirs(os.path.dirname(output_weights_path), exist_ok=True)

    # If training never improved (all epochs same acc), fall back to final state_dict
    if best_weights is None:
        raw_model    = model.module if isinstance(model, nn.DataParallel) else model
        best_weights = {k: v.cpu().clone() for k, v in raw_model.state_dict().items()}

    torch.save(best_weights, output_weights_path)
    log.ok(f"WI AlexNet_N trained weights → {output_weights_path}")
    log.info(f"Best training accuracy : {best_accuracy:.2f}%")
    log.info("main.py will auto-load these weights on next run.")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Train Writer-Independent AlexNet_N on BHSig Development Set"
    )
    parser.add_argument("--epochs",     type=int,   default=DEFAULT_EPOCHS,
                        help=f"Training epochs (default: {DEFAULT_EPOCHS})")
    parser.add_argument("--batch_size", type=int,   default=DEFAULT_BATCH_SIZE,
                        help=f"Batch size (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--lr",         type=float, default=DEFAULT_LR,
                        help=f"Initial learning rate (default: {DEFAULT_LR})")
    args = parser.parse_args()

    print()
    print("=" * 62)
    print("  AlexNet_N  —  Writer-Independent Pre-Training")
    print("  Task 2.2  |  SIL775/7175 Biometric Security")
    print("=" * 62)
    print()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.model(f"Compute device : {device}")
    if device.type == "cuda":
        for gpu_idx in range(torch.cuda.device_count()):
            gpu_name = torch.cuda.get_device_name(gpu_idx)
            gpu_mem  = torch.cuda.get_device_properties(gpu_idx).total_memory // (1024**3)
            log.model(f"  GPU {gpu_idx}: {gpu_name}  ({gpu_mem} GB)")

    # Output path (auto-loaded by main.py when present)
    Config.setup_directories()
    output_weights_path = os.path.join(Config.RESULTS_DIR, "wi_alexnet_trained.pth")

    if os.path.exists(output_weights_path):
        log.warn(f"Weights file already exists: {output_weights_path}")
        response = input("Overwrite and retrain? [y/N] : ").strip().lower()
        if response != 'y':
            log.info("Keeping existing weights. Run main.py to use them.")
            return

    # ── Discover Development Set subjects ─────────────────────
    log.phase("Development Set Subject Discovery")

    if not os.path.exists(Config.MAPPING_FILE):
        log.error(f"Mapping CSV not found: {Config.MAPPING_FILE}")
        log.error("Run  python main.py  once first to generate the mapping, "
                  "then re-run this script.")
        sys.exit(1)

    log.info("Reading exploitation set assignments to exclude them from Dev Set...")

    bengali_exploit_ids = get_exploitation_subject_ids(
        Config.MAPPING_FILE, "Dataset_1", "Signature_Source_ID"
    )
    hindi_exploit_ids = get_exploitation_subject_ids(
        Config.MAPPING_FILE, "Dataset_2", "Signature_Source_ID"
    )
    log.info(f"  Excluded (Bengali): {len(bengali_exploit_ids)} IDs")
    log.info(f"  Excluded (Hindi)  : {len(hindi_exploit_ids)} IDs")

    bengali_dev = collect_dev_set_dirs(Config.BHSIG_BENGALI_DIR, bengali_exploit_ids)
    hindi_dev   = collect_dev_set_dirs(Config.BHSIG_HINDI_DIR,   hindi_exploit_ids)

    all_dev_dirs = bengali_dev + hindi_dev
    log.ok(f"Dev Set: {len(bengali_dev)} Bengali + {len(hindi_dev)} Hindi = "
           f"{len(all_dev_dirs)} subject directories")
    log.phase_done("Development Set Subject Discovery")

    if not all_dev_dirs:
        log.error("No development-set subjects found.")
        log.error("Ensure BHSig directories contain more subjects than the 100 in the "
                  "Exploitation Set.")
        sys.exit(1)

    # ── Train ──────────────────────────────────────────────────
    train_wi_alexnet(
        subject_dirs        = all_dev_dirs,
        num_epochs          = args.epochs,
        batch_size          = args.batch_size,
        learning_rate       = args.lr,
        output_weights_path = output_weights_path,
        device              = device,
    )

    print()
    print("=" * 62)
    print(f"  Done. Weights saved to:")
    print(f"  {output_weights_path}")
    print()
    print("  Next step:  python train_se_alexnet.py")
    print("  Then run :  python main.py")
    print("=" * 62)


if __name__ == "__main__":
    main()
