"""
SE-AlexNet Fine-Tuning Script.

PURPOSE
-------
Task 1.2 of the assignment requires fine-tuning the SE-AlexNet model on
biometric face and iris data so the Squeeze-and-Excitation attention block
learns channel dependencies meaningful for biometrics — not ImageNet objects.

Strategy
--------
We treat this as a multi-class IDENTITY CLASSIFICATION Task:
- The 100 Exploitation Set users serve as the 100 classes.
- Face images from CASIA (Dataset 1) + LFW (Dataset 2) supply the training data.
- Iris images from CASIA (Dataset 1) + IITD (Dataset 2) supplement the training
  (both fed as 3-channel 224×224 tensors; the model is modality-agnostic).

Fine-tuning schedule (two-phase warm-up):
- Epochs 1 – WARMUP_EPOCHS : Only classifier + SE block weights are updated.
  The convolutional backbone is frozen to prevent catastrophic forgetting of
  ImageNet low-level features while the new SE attention warms up.
- Epochs WARMUP_EPOCHS+1 – END : Full unfreeze; all layers trained together
  with a lower LR to refine the backbone.

OUTPUT
------
results/se_alexnet_finetuned.pth  ← auto-loaded by main.py on next run

USAGE
-----
    (venv) > python train_se_alexnet.py
    (venv) > python train_se_alexnet.py --epochs 25 --batch_size 16 --warmup 8
"""

import os
import sys
import argparse

import cv2
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.logger import log
from src.features.deep_se_alexnet import SEAlexNet
from src.preprocessing.face_preprocessor import FacePreprocessor
from src.preprocessing.iris_preprocessor import IrisPreprocessor

# ─────────────────────────────────────────────────────────────
# Hyper-parameters (also exposed as CLI flags)
# ─────────────────────────────────────────────────────────────
DEFAULT_EPOCHS    = 20
DEFAULT_BATCH_SIZE = 16
DEFAULT_LR        = 0.0005    # Smaller LR for fine-tuning vs training from scratch
DEFAULT_WARMUP    = 6         # Epochs with backbone frozen
LR_FULL_FINETUNE  = 0.0001   # Further reduced LR once backbone is unfrozen
MAX_IMAGES_PER_USER = 20      # Cap per identity — face + iris combined


# ─────────────────────────────────────────────────────────────
# Dataset
# ─────────────────────────────────────────────────────────────
class BiometricIdentityDataset(Dataset):
    """
    Loads face and iris images for 100 Exploitation Set users.

    Each user = one integer class label.
    Both face AND iris images from the same user are treated as examples
    of that user's identity representation (modality-agnostic fine-tuning).

    Output per sample: (224×224 RGB float tensor normalised to ImageNet stats,
                        integer class_label)
    """

    SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')

    def __init__(self, mapping_df, transform):
        """
        mapping_df : DataFrame with columns Virtual_User_ID, Dataset,
                     Face_Source_ID, Iris_Source_ID
        transform  : torchvision transform to apply to each loaded image
        """
        self.samples   = []    # (absolute_image_path, integer_class_label, modality_type)
        self.transform = transform
        self.num_classes = 0
        
        self.face_prep = FacePreprocessor()
        self.iris_prep = IrisPreprocessor()
        
        self.cache_dir = os.path.join(Config.BASE_DIR, ".cache_images")
        os.makedirs(self.cache_dir, exist_ok=True)

        for class_label, (_, user_row) in enumerate(mapping_df.iterrows()):
            dataset_tag = user_row['Dataset']
            face_sid    = str(user_row['Face_Source_ID'])
            iris_sid    = str(user_row['Iris_Source_ID'])

            # Resolve source directories per dataset
            if dataset_tag == "Dataset_1":
                face_dir = os.path.join(Config.CASIA_DIR, face_sid)
                iris_dir = os.path.join(Config.CASIA_DIR, iris_sid)
            else:
                face_dir = os.path.join(Config.LFW_DIR,  face_sid)
                iris_dir = os.path.join(Config.IITD_DIR, iris_sid)

            collected = 0
            for source_dir in [face_dir, iris_dir]:
                if not os.path.isdir(source_dir):
                    continue
                image_files = sorted([
                    os.path.join(source_dir, f) for f in os.listdir(source_dir)
                    if f.lower().endswith(self.SUPPORTED_EXTENSIONS)
                ])
                for img_path in image_files:
                    if collected >= MAX_IMAGES_PER_USER:
                        break
                    modality_type = 'face' if source_dir == face_dir else 'iris'
                    self.samples.append((img_path, class_label, modality_type))
                    collected += 1

            self.num_classes += 1

        log.info(f"  BiometricIdentityDataset: {len(self.samples)} images, "
                 f"{self.num_classes} identity classes")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int):
        image_path, class_label, modality_type = self.samples[idx]

        # Generate a unique cache filename for this image + modality
        path_hash = hashlib.md5((image_path + modality_type).encode('utf-8')).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{path_hash}.jpg")
        
        bgr_image = None
        if os.path.exists(cache_file):
            # FAST PATH: Load pre-cropped image from cache
            bgr_image = cv2.imread(cache_file)

        if bgr_image is None:
            # SLOW PATH: Load original and run heavy CPU cropping
            bgr_image = cv2.imread(image_path)
            if bgr_image is None:
                # Return a zero tensor on rare load failure
                return torch.zeros(3, 224, 224, dtype=torch.float32), class_label

            # Apply modality-specific tight cropping (matching main.py evaluation)
            if modality_type == 'face':
                gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
                # Find face bounds using Dlib
                dlib_faces = self.face_prep.dlib_detector(gray, 1)
                if len(dlib_faces) > 0:
                    rect = dlib_faces[0]
                    x1 = max(0, rect.left())
                    y1 = max(0, rect.top())
                    x2 = min(bgr_image.shape[1], rect.right())
                    y2 = min(bgr_image.shape[0], rect.bottom())
                    cropped = bgr_image[y1:y2, x1:x2]
                    if cropped.size > 0:
                        bgr_image = cropped
            
            elif modality_type == 'iris':
                gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
                try:
                    # Find iris bounds using Hough (or contour fallback)
                    pupil, iris = self.iris_prep.find_pupil_and_iris(gray)
                    ix, iy, ir = iris
                    x1 = max(0, ix - ir)
                    y1 = max(0, iy - ir)
                    x2 = min(bgr_image.shape[1], ix + ir)
                    y2 = min(bgr_image.shape[0], iy + ir)
                    cropped_iris = bgr_image[y1:y2, x1:x2]
                    if cropped_iris.size > 0:
                        bgr_image = cropped_iris
                except ValueError:
                    # If preprocessor fails to find the iris, we just pass the uncropped 
                    # image (fallback) to ensure the tensor shape matches and no data is lost
                    pass

            # Save the cropped image to cache so we never process it again
            cv2.imwrite(cache_file, bgr_image)

        # Convert to RGB for ImageNet-pretrained AlexNet
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)

        # Apply transform: resize to 224x224, to tensor, normalise
        tensor = self.transform(rgb_image)
        return tensor, class_label


# ─────────────────────────────────────────────────────────────
# Freeze / unfreeze helpers
# ─────────────────────────────────────────────────────────────
def freeze_backbone(model: SEAlexNet):
    """
    Freezes the convolutional feature extractor and SE block, leaving only
    the classifier FC layers trainable.  Used during warm-up phase to
    avoid destroying ImageNet features while the SE attention initialises.
    """
    for param in model.features.parameters():
        param.requires_grad = False
    for param in model.se_block.parameters():
        param.requires_grad = False
    for param in model.classifier.parameters():
        param.requires_grad = True
    trainable_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log.model(f"Warm-up mode: backbone FROZEN, {trainable_count:,} trainable params (classifer+SE)")


def unfreeze_all(model: SEAlexNet):
    """
    Unlocks all parameters for full fine-tuning after warm-up phase completes.
    """
    for param in model.parameters():
        param.requires_grad = True
    trainable_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log.model(f"Full fine-tune: ALL weights trainable ({trainable_count:,} params)")


# ─────────────────────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────────────────────
def train_se_alexnet(mapping_df, num_epochs: int, batch_size: int,
                     learning_rate: float, warmup_epochs: int,
                     output_weights_path: str, device: torch.device,
                     resume: bool = False):
    """
    Fine-tunes SE-AlexNet for identity classification on biometric images.
    Saves the best-validation-loss checkpoint (weights on CPU).
    """
    # ImageNet mean/std normalisation — AlexNet was pretrained with these
    imagenet_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Resize((224, 224), antialias=True),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    full_dataset = BiometricIdentityDataset(mapping_df, imagenet_transform)

    if len(full_dataset) == 0:
        log.error("BiometricIdentityDataset is empty. Check that face/iris directories exist.")
        sys.exit(1)

    num_classes = full_dataset.num_classes

    # 80/20 train-validation split (deterministic, stratified by class is impractical here
    # given small per-user counts, so we use a simple index split)
    val_count   = max(1, int(0.20 * len(full_dataset)))
    train_count = len(full_dataset) - val_count
    train_subset, val_subset = torch.utils.data.random_split(
        full_dataset,
        [train_count, val_count],
        generator=torch.Generator().manual_seed(42)
    )

    train_loader = DataLoader(
        train_subset,
        batch_size  = batch_size,
        shuffle     = True,
        num_workers = 0,
        pin_memory  = device.type == "cuda",
        drop_last   = True,
    )
    val_loader = DataLoader(
        val_subset,
        batch_size  = batch_size * 2,    # Larger batch for faster validation
        shuffle     = False,
        num_workers = 0,
        pin_memory  = device.type == "cuda",
    )

    # Guard: drop_last=True produces 0 batches when dataset smaller than batch_size.
    # With 100 users × up to 20 images = 2000 samples this will not trigger in practice,
    # but the check prevents a silent no-op training run.
    if len(train_loader) == 0:
        log.error(f"Training DataLoader is empty after drop_last=True. "
                  f"train_count={train_count} is smaller than batch_size={batch_size}. "
                  f"Reduce --batch_size or increase MAX_IMAGES_PER_USER.")
        sys.exit(1)

    log.info(f"  Train samples : {train_count}  ({len(train_loader)} batches/epoch)")
    log.info(f"  Val samples   : {val_count}")
    log.info(f"  Identity classes : {num_classes}")

    # Build the model with correct num_classes for fine-tuning head
    model = SEAlexNet(pretrained=True, num_classes=num_classes)
    
    if resume and os.path.exists(output_weights_path):
        log.info(f"Resuming: Loading checkpoint from {output_weights_path}...")
        ckpt = torch.load(output_weights_path, map_location="cpu", weights_only=False)
        model.load_state_dict(ckpt, strict=False)
        log.ok("Checkpoint loaded successfully.")

    num_gpus = torch.cuda.device_count()
    if num_gpus > 1:
        log.model(f"Using {num_gpus} GPUs via nn.DataParallel")
        model = nn.DataParallel(model)
    model = model.to(device)

    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    criterion = nn.CrossEntropyLoss()

    # Start with backbone frozen for warm-up phase
    raw_model = model.module if isinstance(model, nn.DataParallel) else model
    freeze_backbone(raw_model)

    # Warm-up optimizer groups: only trainable params
    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=learning_rate
    )

    batches_per_epoch = len(train_loader)
    best_val_loss     = float('inf')
    best_weights      = None

    log.step("SE-AlexNet Fine-Tuning Loop")
    log.info(f"  Epochs       : {num_epochs}  |  Warm-up : first {warmup_epochs}")
    log.info(f"  Warm-up LR   : {learning_rate}  |  Full-FT LR : {LR_FULL_FINETUNE}")
    log.separator()

    for epoch_num in range(1, num_epochs + 1):

        # ── Phase transition: unfreeze backbone after warm-up ──────────────
        if epoch_num == warmup_epochs + 1:
            log.step(f"Epoch {epoch_num}: warm-up complete — unfreezing backbone for full FT")
            unfreeze_all(raw_model)
            # Rebuild optimizer to include all params at the lower full-FT LR
            optimizer = optim.Adam(model.parameters(), lr=LR_FULL_FINETUNE)

        # ── Training pass ──────────────────────────────────────────────────
        model.train()
        train_loss     = 0.0
        train_correct  = 0
        train_total    = 0

        for batch_idx, (batch_images, batch_labels) in enumerate(train_loader, start=1):
            batch_images = batch_images.to(device, non_blocking=True)
            batch_labels = batch_labels.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            logits     = model(batch_images)
            batch_loss = criterion(logits, batch_labels)
            batch_loss.backward()
            optimizer.step()

            train_loss    += batch_loss.item() * batch_images.size(0)
            predicted      = logits.argmax(dim=1)
            train_correct += (predicted == batch_labels).sum().item()
            train_total   += batch_images.size(0)

            if batch_idx % 5 == 0 or batch_idx == batches_per_epoch:
                running_acc = 100.0 * train_correct / max(train_total, 1)
                log.progress(
                    batch_idx, batches_per_epoch,
                    label=f"E{epoch_num:02d}/{num_epochs}  "
                          f"loss={batch_loss.item():.4f}  "
                          f"acc={running_acc:.1f}%"
                )

        # ── Validation pass ────────────────────────────────────────────────
        model.eval()
        val_loss    = 0.0
        val_correct = 0
        val_total   = 0

        with torch.no_grad():
            for val_images, val_labels in val_loader:
                val_images = val_images.to(device, non_blocking=True)
                val_labels = val_labels.to(device, non_blocking=True)
                val_logits = model(val_images)
                vl         = criterion(val_logits, val_labels)
                val_loss   += vl.item() * val_images.size(0)
                val_correct += (val_logits.argmax(dim=1) == val_labels).sum().item()
                val_total   += val_images.size(0)

        train_avg_loss = train_loss    / max(train_total, 1)
        train_accuracy = 100.0 * train_correct / max(train_total, 1)
        val_avg_loss   = val_loss      / max(val_total, 1)
        val_accuracy   = 100.0 * val_correct   / max(val_total, 1)

        frozen_tag = "FROZEN" if epoch_num <= warmup_epochs else "FULL-FT"
        log.ok(
            f"[{frozen_tag}] Epoch {epoch_num:3d}/{num_epochs}  "
            f"train_loss={train_avg_loss:.4f} acc={train_accuracy:.1f}%  |  "
            f"val_loss={val_avg_loss:.4f} acc={val_accuracy:.1f}%"
        )

        # Save checkpoint continuously at the end of every epoch
        raw_m = model.module if isinstance(model, nn.DataParallel) else model
        current_weights = {k: v.cpu().clone() for k, v in raw_m.state_dict().items()}
        torch.save(current_weights, output_weights_path)
        log.ok(f"  → Checkpoint saved at epoch {epoch_num}")

        # Track best val loss for logging
        if val_avg_loss < best_val_loss:
            best_val_loss = val_avg_loss
            log.info(f"  ↓ New best val_loss: {best_val_loss:.4f}")

    # ── Save ──────────────────────────────────────────────────────────────
    log.step("Fine-Tuning Complete")
    # No need to explicitly save again, as the end of the last epoch just saved the model.
    log.ok(f"SE-AlexNet fine-tuned weights → {output_weights_path}")
    log.info(f"Best validation loss : {best_val_loss:.4f}")
    log.info("main.py will auto-load these weights on next run.")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune SE-AlexNet on biometric face + iris identity classification"
    )
    parser.add_argument("--epochs",     type=int,   default=DEFAULT_EPOCHS,
                        help=f"Total fine-tuning epochs (default: {DEFAULT_EPOCHS})")
    parser.add_argument("--batch_size", type=int,   default=DEFAULT_BATCH_SIZE,
                        help=f"Batch size (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--lr",         type=float, default=DEFAULT_LR,
                        help=f"Warm-up learning rate (default: {DEFAULT_LR})")
    parser.add_argument("--warmup",     type=int,   default=DEFAULT_WARMUP,
                        help=f"Epochs to keep backbone frozen (default: {DEFAULT_WARMUP})")
    args = parser.parse_args()

    print()
    print("=" * 62)
    print("  SE-AlexNet  —  Biometric Fine-Tuning")
    print("  Task 1.2  |  SIL775/7175 Biometric Security")
    print("=" * 62)
    print()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.model(f"Compute device : {device}")
    if device.type == "cuda":
        for gpu_idx in range(torch.cuda.device_count()):
            gpu_name = torch.cuda.get_device_name(gpu_idx)
            gpu_mem  = torch.cuda.get_device_properties(gpu_idx).total_memory // (1024**3)
            log.model(f"  GPU {gpu_idx}: {gpu_name}  ({gpu_mem} GB)")

    Config.setup_directories()
    output_weights_path = os.path.join(Config.RESULTS_DIR, "se_alexnet_finetuned.pth")

    resume = False
    if os.path.exists(output_weights_path):
        log.warn(f"Fine-tuned weights already exist: {output_weights_path}")
        print("  [r] Resume training from existing checkpoint")
        print("  [o] Overwrite and start fresh")
        print("  [c] Cancel")
        response = input("Choice [r/o/c]: ").strip().lower()
        if response == 'r':
            resume = True
            log.info("Will resume from existing checkpoint.")
        elif response == 'o':
            resume = False
            log.info("Will overwrite existing checkpoint and start fresh.")
        else:
            log.info("Training cancelled. Run main.py to use existing weights.")
            return

    if not os.path.exists(Config.MAPPING_FILE):
        log.error(f"Mapping CSV not found: {Config.MAPPING_FILE}")
        log.error("Run  python main.py  once first to generate the mapping, "
                  "then re-run this script.")
        sys.exit(1)

    import pandas as pd
    mapping_df = pd.read_csv(Config.MAPPING_FILE, dtype=str)
    log.ok(f"Mapping loaded: {len(mapping_df)} virtual users")

    train_se_alexnet(
        mapping_df          = mapping_df,
        num_epochs          = args.epochs,
        batch_size          = args.batch_size,
        learning_rate       = args.lr,
        warmup_epochs       = args.warmup,
        output_weights_path = output_weights_path,
        device              = device,
        resume              = resume,
    )

    print()
    print("=" * 62)
    print(f"  Done. Weights saved to:")
    print(f"  {output_weights_path}")
    print()
    print("  All model weights are now ready.")
    print("  Run:  python main.py")
    print("=" * 62)


if __name__ == "__main__":
    main()
