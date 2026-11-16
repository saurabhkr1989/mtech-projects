# Multimodal Biometric Verification System

## 1. Project Overview and Objectives

This repository contains the complete execution pipeline, source code, and evaluation methodology for an advanced **Multimodal Biometric Verification System** (Assignment 2). The core objective of this project is to construct a highly robust identity verification framework that significantly mitigates the vulnerabilities and Equal Error Rates (EER) inherent in single-modality systems. 

To achieve this, the system orthogonally fuses three distinct biometric modalities:
1.  **Face:** Capturing visual and spatial geometry features.
2.  **Iris:** Capturing textural and near-infrared (NIR) patterns.
3.  **Offline Signature:** Capturing behavioral and fine motor control characteristics.

The system strictly adheres to a **Verification (1:1)** methodology. It fundamentally validates whether a presented biometric sample matches the enrolled template for a claimed identity. To rigidly evaluate the system's performance and generalizability, we employ an exhaustive **5-Fold Cross-Validation** strategy across **100 Enrolled Virtual Users**. These users are synthetically generated via a **Chimeric Data Generation** process, mapping completely disparate physical identities across two highly distinct environmental datasets (Constrained vs. Unconstrained).

---

## 2. Exhaustive Directory Architecture & File Dictionary

The repository is modularized to separate configurations, core logic processing, data loading pipelines, machine learning models, and persistent state artifacts. 

```text
.
├── src/                                  # Core Python Packages and Modules
│   ├── config.py                         # **Global Configuration:** Acts as the brain for hyperparameters. It defines hardcoded constants such as ROI matrix sizes (e.g., Face regions are 30x30), sliding window strides (4px overlap for Iris strips), ULBP block divisions, absolute dataset paths, and cross-validation fold constants. Modifying this single file propagates changes throughout the entire pipeline.
│   ├── logger.py                         # **Console Output formatter:** A custom utility replacing standard `print()` statements. It injects ANSI escape codes to format terminal output with phase-oriented colors (e.g., Info=Blue, Warn=Yellow, Step=Green, Matrix=Magenta), improving logging readability during massive batch executions.
│   │
│   ├── data/                             
│   │   └── dataset_mapper.py             # **Phase 1 (Chimeric Linking):** This module scans the raw dataset directories (CASIA Face/Iris, LFW, IITD, BHSig Bengali/Hindi). It computes the `Min_Samples_N` cap per user to guarantee valid cross-validation partitions. Crucially, it filters out LFW subjects that do not possess at least 5 detectable face bounding boxes, preventing downstream starvation. It pairs subjects deterministically and writes the relationships to `dataset_mapping.csv`.
│   │
│   ├── preprocessing/                    
│   │   ├── face_preprocessor.py          # **Phase 2 (Face Formatting):** Implements the Active Appearance Model (AAM) equivalent pipeline. It uses a robust hybrid approach: deploying `cv2.HaarCascade` eye-detectors to locate faces in difficult Near-Infrared (CASIA) images where standard HOG algorithms fail, passing that bounding box to Dlib (`shape_predictor_68`) to isolate 68 landmark coordinates. It dynamically extracts exactly 15 centered 30x30 ROIs based on specific key points.
│   │   ├── iris_preprocessor.py          # **Phase 2 (Iris Formatting):** Executes classical Iris recognition geometry. Employs iterative Hough Circle transforms (and contour center-of-mass fallbacks for high glare) to segment the pupil and sclera boundaries. It translates this 2D circular plane into a linear 512x64 rectangular mesh utilizing John Daugman's Rubber-Sheet model. Finally, it slices this normalized image into 10 overlapping matrices (32x512) sliding by exactly 4 pixels.
│   │   └── signature_preprocessor.py     # **Phase 2 (Signature Formatting):** Cleans noisy offline ink traces. Utilizes adaptive Otsu Binarization to separate pure ink from paper texture. Computes physical spatial Cartesian moments to locate the signature's absolute Center of Mass. Applies an Affine Translation matrix to perfectly align that centroid within a strict 170x242 grid using Nearest Neighbor interpolation to avoid anti-aliasing artifacts.
│   │
│   ├── features/                         
│   │   ├── texture_extractor.py          # **Phase 3 (Hand-Crafted Textures):** Implements Uniform Local Binary Patterns (ULBP). Configured with P=8 neighbors and R=1 circle radius. It mathematically reduces 256 physical rotation patterns into exactly 59 uniform rotationally-invariant bins. Generates massive concatenated histograms across Face (10x10 blocks) and Iris (16x16 blocks).
│   │   ├── deep_se_alexnet.py            # **Phase 3 (Face/Iris Deep Architecture):** A structural modification of the `torchvision` AlexNet. It injects an adaptive Squeeze-and-Excitation (SE) channel-attention map immediately before the fully-connected classification planes. This module dynamically learns to suppress noisy or irrelevant convolutional activation channels while exciting prominent feature maps.
│   │   └── deep_wi_alexnet.py            # **Phase 4 (Signature Deep Architecture):** A custom, shallower 5-Convolutional, 2-Fully-Connected Neural Network topology designed specifically for the unique geometry of handwriting traces. Crucially, it injects `BatchNorm2d` and `BatchNorm1d` layers *before* activation functions to restrict exploding gradients and stabilize Writer-Independent learning over small batch sizes.
│   │
│   ├── classification/                   
│   │   └── svm_verification.py           # **Phase 5 (Identity Verification Engines):** Instantiates an independent Scikit-Learn `SVC` (Support Vector Classifier) with an RBF (Radial Basis Function) kernel for *every* user, across *every* modality. It implements a mathematically strict **1:3 Positive-to-Negative Target** imposter sampling mechanic to prevent the hyperplane from collapsing towards 99% negative predictions. Manages heavy system RAM via `joblib` disk caching.
│   │
│   ├── fusion/                           
│   │   └── fusion_strategies.py          # **Phase 5 (Multimodal Fusion):** 
│   │                                       *   **Feature Fusion:** Natively flattens and concatenates 1D arrays (Face Tex + Face Deep + Iris Tex + Iris Deep + Sig Deep) into a singular ultra-high dimensional space prior to training a final "Master SVM".
│   │                                       *   **Decision Fusion:** Receives 5 discrete binary {0, 1} states from uni-modal classifiers and implements a strict Majority Rules voter protocol (if sum of votes ≥ 3, Identity is Verified).
│   │
│   └── evaluation/                       
│       └── evaluator.py                  # **Phase 6 (Metrics & Visualization):** Orchestrates the K-Fold index distribution ensuring identical Chimeric Tuples are preserved across folds. It interpolates True Positive Rates (TPR) against False Positive Rates (FPR) utilizing continuous SVM `decision_function()` confidences. Calculates the precise Equal Error Rate (EER) intersection. Outputs analytical `.png` graph artifacts.
│
├── main.py                               # **The Core Execution Hub:** The root Python script that synchronously orchestrates the entire lifecycle. It invokes Phase 1 (Mapping), parallelizes Phase 2 (Preprocessing via Python `concurrent.futures`), executes Phase 3/4 (GPU Matrix Inferences), and drives Phase 5/6 (Multi-Threaded SVM batch scoring).
├── train_se_alexnet.py                   # **Trainer Script:** Exclusively fine-tunes the Face and Iris `deep_se_alexnet.py` models utilizing CrossEntropy backpropagation over the dynamically generated Chimeric Enrolled datasets.
├── train_wi_alexnet.py                   # **Trainer Script:** Exclusively trains the Signature `deep_wi_alexnet.py` model. It deliberately iterates *only* over the 'Development Set' (identity users deliberately stripped from the testing pool) to force the network to understand general curvature mathematics oblivious to specific identities.
├── download_dlib_model.py                # **Dependencies:** A critical script that automates the downloading and extraction of the essential Dlib `shape_predictor_68_face_landmarks.dat` model.
├── dataset_mapping.csv                   # **Persistence:** A generated reference index mapping string relationships ("User_D1_001 -> CASIA_Folder_002 + BHSig_Folder_102"). This ensures cross-validation topologies remain identical across different physical OS reboots.
├── requirements.txt                      # Detailed `pip` installation environment manifest.
│
├── Raw Dataset/                          # **Input Data:** The target root directory that must be provided by the user containing the unzipped CASIA, LFW, IITD, and BHSig datasets.
├── extracted_features/                   # **Artifacts:** Target location where massive numerical `.csv` arrays are dumped representing the final 1D feature tensors extracted from the pipelines.
├── results/                              # **Outputs:** Where cached SVM trees (`svm_cache/`), the fully saved deep learning weights (`.pth`), generated ROC `.png` graphs, and the master `summary_accuracy_eer.csv` metrics table are stored permanently.
└── visualizations/                       # **Diagnostics:** Stores debugging images visually validating bounding box rects and geometrically unrolled rubber sheet representations.
```

---

## 3. Holistic Algorithmic Workflow Processing

The system's execution mimics an hourglass—ingesting massive quantities of unstructured image data, structurally distilling it through rigid geometric formatting, and widening back out into broad mathematical tensor arrays for high-density classification scoring.

### Phase 1: Chimeric Cross-Modality Mapping Generation
Because physical databases naturally collect biometric traits from disparate human populations globally (e.g., CASIA Face vs. BHSig Bengali handwriting), valid Multi-modal testing requires generating composite synthetic identities. We construct **Virtual Users**.

*   **Logic Model:** The system iterates to generate exactly 100 Virtual Enrolled Users per Dataset block. It anchors on User A from the Face Database, dynamically linking them to User A from the Iris Database, and tying them sequentially to User A from the Signature dataset. 
*   **The Minimum Sample Validation (The Bounding Limit):** Real-world folders vary wildly in volume. A Face folder might hold 30 captures, while a Signature folder holds precisely 5. Since Cross-Validation validation requires uniform parallel testing matrices across all 3 modalities simultaneously, the mapper inherently calculates the `Min_Samples_N`. If the lowest contributing modality holds 5 files, the system culls the rest to generate exactly 5 identical Tuple indices ensuring test validation never mathematically starves.
*   **Dataset 2 Pre-Filtering (LFW Constraint):** LFW (Labeled Faces in the Wild) is highly volatile. Unlike CASIA, many subjects contain only 1 unusable image. Before mapping, Phase 1 invokes Dlib to deeply scan LFW directories, outright rejecting and bypassing any subject identity that fails to yield at minimum 5 physically detectable facial bounding margins. 

### Phase 2: Biological Structural Normalization (Preprocessing)
Unstructured raw images cannot be fed directly into feature mathematical arrays. Lighting variance, physical scale, and rotational translations completely destroy tensor mapping probabilities. 

**A) Facial Active Appearance Modeling (AAM)**
*   **The Near-Infrared Paradox:** The CASIA dataset (Dataset 1) captures subjects in the Near-Infrared physical spectrum. Traditional Dlib facial detection utilizes Histogram of Oriented Gradients (HOG) architecture trained entirely on RGB shadows. HOG fails silently when observing infrared planes.
*   **The Hybrid Solution:** We construct a cascading boundary logic. The system initializes a fast `cv2.HaarCascade` engine tuned specifically to locate relative eye-pupil geometry pairs. Using human facial proportion math, the system artificially extrapolates a precise facial bounding box.
*   **Extraction Formulation:** We inject that box directly into the Dlib `shape_predictor_68` predictor, successfully bypassing the HOG failure while retaining 68 perfect AAM geometric landmarks. We isolate 15 highly specific facial landmarks (Nose tip, left eye corner, mouth edges) and slice exactly 15 rigid `30x30` pixel localized sub-matrices, applying histogram equalization luminance correction universally.

**B) Iris Daugman Rubber-Sheet Flattening**
*   **The Spherical Problem:** Irises are heavily distorted 3D circular muscles that dilate dynamically based on lumen variance. Comparing 2 circles mathematically is statistically flawed due to pupil-area shifts.
*   **Segmentation Mechanics:** The script Gaussian-blurs the image heavily. It spins an iterative loop relaxing `HoughGradient` radial parameters mathematically defining the absolute inner pupil. (For extreme NIR glare where Hough fails, it clusters inverted binary contours locating the centroid moment). It then raycasts linearly tracing gradient shifts to locate the outer sclera limit.
*   **Mathematical Projection:** We implement John Daugman's Rubber Sheet protocol. Treating the iris boundaries as vectors, it projects 360-degrees of Cartesian `(x, y)` coordinate space dynamically into a flat 2D Polar `(r, θ)` rectangular grid (`512x64`).
*   **Matrix Slicing:** To isolate highly localized distinct texture deformations, the `512x64` matrix is physically sliced into exactly 10 horizontal strips tracking dimensions of `32x512`, sliding downward across a highly specific overlapping **4-Pixel Stride**. 

**C) Offline Signature Spatial Rectification**
*   **The Variance Problem:** Signatures are captured on inconsistent scanning beds dynamically shifted across completely different physical origin `(0,0)` points.
*   **Isolation:** The `PIL` library maps massive `.tif` files routing around LibTIFF backend crash sequences. Images run strictly through `Otsu Binarization` which determines the optimal mathematical variance point slicing background paper grey from pure ink. The mask is inverted forcing Ink integers to True `(1)`.
*   **Affine Centroids:** We calculate spatial array moments across the ink mapping axes locating the physical 2D Cartesian Center of Mass coordinate `(m10/m00, m01/m00)`. A rigid Affine geometric transformation maps this exact coordinate dynamically pinning it mathematically onto the absolute dead-center of a required `170x242` boundary box utilizing absolute Nearest Neighbor interpolations preventing structural pixel-stretching artifacts.

### Phase 3 & 4: Heavy GPU Deep and Global Textural Encoding

Once the biology is compressed into perfect geometrically normalized shapes, the system runs exhaustive vector encoding arrays extracting identifying invariants.

**A) Phase 3: Textural Hand-Crafted Histograms (ULBP)**
*   Uniform Local Binary Patterns (ULBP) excel at finding microscopic physical variances ignoring global illumination completely. 
*   We map exactly 8 geometric radius neighbors against circle radii `R=1`. An unmapped 8-bit space yields 256 structural rotation permutations severely diluting identifying uniqueness. ULBP logic isolates and compresses these down into precisely 59 rotationally-invariant "Uniform" geometrical definitions forming highly tight histogram vectors.
*   The system iteratively walks Face regions across grids measuring `10x10` and Iris rectangles spanning `16x16`, generating localized uniform counts flattening into single-dimensional identity strings.

**B) Phase 3: Face/Iris Custom Deep Channel Attentions (SE-AlexNet)**
*   Convolution arrays detect geometry, but propagate massive noise layers equally.
*   We aggressively structurally modify standard PyTorch `AlexNet`. Directly prior to the dense `FC1` layers, we construct an adaptive Squeeze-and-Excitation (SE) channel map. 
*   **Squeeze:** We globally pool the entire tensor matrix geometrically taking averages across its full depth mapping vectors `(b, c, 1, 1)`.
*   **Excitation:** Those weights funnel iteratively through two deeply compressive fully-connected arrays isolating explicit feature dependencies determining their relative validation "importance". The weights are physically multiplied directly back onto original tensors mathematically silencing noisy visual artifacts generated prematurely downstream in convolutional iterations perfectly preserving signal strength inside the final 4096-dimensional FC2 matrices.

**C) Phase 4: Signature Behavioral Deep Modeling (Writer Independent AlexNet_N)**
*   Target-learning behavior networks explicitly tracking identities completely fail against handwriting variance.
*   **The "Development Set":** We explicitly configure the script `train_wi_alexnet.py` mathematically excluding all 100 Enrolled User sets. It grabs directories housing unassigned public subjects. It trains a CNN dynamically mapping the architectural *physics* of handwriting curves, loops, and stops completely agnostic to verification identities.
*   **Layer Physics:** The architecture itself uses a shallow 5-Layer structure avoiding exploding physical gradients. Crucially, the system strictly injects spatial `BatchNorm2d` matrices dynamically balancing output variabilities *before* executing Rectified Linear Unit (`nn.ReLU`) nonlinearities perfectly combating internal covariate dimensional shifts protecting small matrix training batches from catastrophic over-adjustment.

### Phase 5 & 6: Mathematical Classifier Tuning and Metric Extractions

Raw Vectors from ML models output floating-point distances, they lack boolean verification boundary logic. We build a classification mechanism utilizing cross-validation tracking.

**1) SVM Instantiation and Impostor Tuning**
*   We deploy independent `sklearn.svm.SVC` instances built over an `rbf` spatial kernel mapped onto singular users physically separating matching identity spaces mathematically over thousands of hyperplanes.
*   **The Mathematical 1:99 Problem:** Running standard training arrays across 1 True tuple and 99 Impostor tuples forces the hyperplane to degrade logic; guessing `False` natively creates a 99% accuracy floor masking total failure. 
*   **The Ratio Fix:** The codebase dynamically selects precisely **3** random negative samples structurally balancing tests at a fixed `1:3` Positive-to-Negative margin scaling penalties heavily through `class_weight='balanced'` matrices effectively saving classification vectors from complete degradation. 

**2) K-Fold Multi-Tuple Testing Mechanisms (`evaluator.py`)** 
*   The script distributes mathematical index arrays strictly defining `5-Fold Cross Validation` arrays forcing all 100 virtual users securely into simultaneous identical testing loops parallelizing verifications cleanly across the epochs guaranteeing test arrays observe congruent metrics.
*   Boolean counting methodologies generating ROC curves generate flawed integer stair-steps geometrically masking metric crossovers. The system directly hooks into continuous SVM `.decision_function()` metrics plotting smooth true-value float arrays graphing accurate intersections deriving precisely where False Acceptances physically cross False Rejections producing Equal Error Rates (EER). 

---

## 4. Experimental System Setup & Hardware Specifications

Executing the entire pipeline from raw image arrays dynamically to `.pth` weights natively mathematically requires moderately heavy hardware architectures.

*   **Operating Systems:** Native Linux (Ubuntu 20+) or Windows 10/11 environments mapping continuous Python `concurrent.futures`. 
*   **Memory Thresholds:** Because pre-processing cascades spawn 4 detached background process loops simultaneously loading entire datasets dynamically inside Python lists, physical memory overhead easily spikes. A minimum requirement of **16GB System RAM** is strongly advised. 
*   **Hardware Acceleration:** Iterative Squeeze-and-Excitation tensors generated across AlexNet architectures executing backwards propagations demand `PyTorch CUDA` environments. Discrete NVIDIA GPUs carrying minimum bounds of **8GB VRAM** drastically prevent Out of Memory `(OOM)` pipeline halts natively pulling `cudnn.backends` optimizations. 
*   **Storage Toggles:** The system will mathematically evaluate 45,000+ verification scoring loops internally across all modality variations dynamically. Native caching logic routes heavy SVM state parameters continuously mapping directories out to `.joblib` disk states ensuring subsequent runs completely bypass retraining models caching them in `results/svm_cache/`. High I/O SSDs execute this instantly. 

---

## 5. Process Visualizations

> **Generation:** All figures below are produced by running `python generate_visualizations.py` from the project root.
> The script saves outputs to `visualizations/` and requires no SVM retraining or model inference beyond what is already cached in `results/`.

---

### Figure 1 — Face ROI Samples

**15 landmark-centered 30 × 30 pixel patches after Histogram Equalization**

The face preprocessor locates 68 landmarks via the Dlib shape predictor (with a Haar-eye cascade fallback for near-infrared CASIA images). From those 68 points, 15 anatomically significant indices are selected — covering the left/right eye corners, nose bridge and tip, nasal wings, mouth corners, lip edges, and jaw extremities (indices `[36, 39, 42, 45, 27, 30, 31, 35, 48, 51, 54, 57, 0, 8, 16]`). Each 30 × 30 crop is then histogram-equalised to normalise for illumination variance.

![Face ROI Samples — 15 landmark-centered 30×30 patches after Histogram Equalization](visualizations/fig1_face_roi_samples.png)

*Left*: original face image with ROI bounding boxes (red) and landmark dots (yellow) overlaid. *Right*: the 15 individual equalised patches arranged in a 3 × 5 grid.

---

### Figure 2 — Normalized Iris Strips

**Daugman Rubber-Sheet model → 10 overlapping 32 × 512 px horizontal strips**

The iris preprocessor first detects the pupil and sclera boundaries via adaptive Hough Circle Transforms (with contour center-of-mass fallbacks for high-glare NIR images). It then maps the annular iris region to a rectangular 512 × 64 px polar grid using John Daugman's Rubber-Sheet model. Finally, the rectangular band is sliced into 10 overlapping 32 × 512 strips with a 4-pixel vertical stride, and each strip is histogram-equalised independently.

![Iris Normalisation — Rubber-Sheet unrolling and 10-strip decomposition](visualizations/fig2_iris_normalized_strip.png)

*Top*: original iris image with pupil (cyan) and sclera (amber) boundaries. *Middle*: the full 512 × 64 unrolled band. *Bottom*: the 10 overlapping equalised strips (S01–S10) with row-range labels annotated.

---

### Figure 3 — Binarized and Centered Signature

**Otsu binarization → Center-of-Mass alignment → 170 × 242 px canvas**

The signature preprocessor: (A) reads the raw `.tif` grayscale scan via PIL to avoid LibTIFF warnings; (B) applies Otsu's optimal threshold to separate ink from paper, then inverts so ink = 255; (C) computes the spatial center of mass of the ink pixels, constructs an affine translation matrix to shift the CoM to the canvas center, and resizes the result to exactly 170 × 242 px with nearest-neighbour interpolation to preserve the sharp binary {0, 1} boundaries.

![Signature Pipeline — Otsu binarization, CoM alignment, 170×242 resize](visualizations/fig3_signature_pipeline.png)

*Left (A)*: raw grayscale scanner output. *Middle (B)*: after Otsu binarization & inversion — the red cross marks the detected center of mass with the required pixel shift annotated. *Right (C)*: final 170 × 242 px centered binary canvas.

---

### Figure 4 — Aggregated ROC Curves

**5-fold aggregated ROC for all modalities and fusion strategies**

These curves are the direct outputs of `evaluator.py` — no additional computation. The system uses continuous SVM `decision_function()` scores (not hard boolean votes) to produce smooth, accurate TPR-vs-FPR curves. The EER is the intersection of the ROC curve with the diagonal FAR = FRR line.

![Aggregated ROC Curves — Dataset 1 and Dataset 2 side-by-side](visualizations/fig4_roc_aggregated.png)

*Left*: Dataset 1 (CASIA-NIR face, IITD iris, BHSig Bengali signature). *Right*: Dataset 2 (LFW-RGB face, IITD iris, BHSig Hindi signature).

---

### Figure 5 — Per-Modality EER Comparison

**Bar chart comparing Equal Error Rate across all modalities for both datasets**

A lower EER indicates better verification performance. Signature Deep (Writer-Independent AlexNet) consistently achieves the lowest EER on both datasets (0.018 for D1; 0.048 for D2), validating the effectiveness of generalised behavioral training. The ULBP texture streams show the highest EER, dragging the fusion systems below the Signature-only baseline.

![EER Bar Chart — Per-modality comparison across Dataset 1 and Dataset 2](visualizations/fig5_modality_eer_bar.png)

---

### Figure 6 — End-to-End Pipeline Block Diagram

**6-phase architecture from raw images to EER / ROC outputs**

![Pipeline Block Diagram — 6-phase biometric architecture](visualizations/fig6_pipeline_diagram.png)

| Phase | Core Operation | Key Output |
|:---:|:---|:---|
| 1 | Chimeric cross-modality mapping | `dataset_mapping.csv` (100 virtual users) |
| 2 | Biological normalization (face / iris / signature) | Cropped, normalized image matrices |
| 3 | ULBP texture extraction | 59-bin histograms per block |
| 3/4 | SE-AlexNet & WI-AlexNet deep inference | 4096-dim feature vectors per sample |
| 5 | Per-user RBF SVM verification (1:3 class balance) | Binary genuine/impostor decisions + scores |
| 6 | Score fusion & 5-fold evaluation | EER, ROC curves, summary CSV |

---

## 6. In-Depth Metric Analysis & Result Tables

These values are aggregated dynamically iterating mean performance matrices natively over rigorous 5-Fold implementations mapping distinct datasets.

### Final Verification Results Averages 

| Dataset Constraints | Modality Subsystem Target | Mean Exact Accuracy | Mean Equal Error Rate (EER) | Mean False Positive | Mean False Negative |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Dataset_1** (CASIA-NIR / Bengali) | **Signature Deep CNN (AlexNet_N)** | **98.33%** | **0.018** | **0.013** | **0.025** |
| Dataset_1 | Face Regional Deep (SE-AlexNet) | 96.04% | 0.079 | 0.012 | 0.121 |
| Dataset_1 | Multisystem Decision Fusion | 91.01% | 0.159 | 0.0002 | 0.358 |
| Dataset_1 | Multisystem Feature Level Fusion | 86.81% | 0.114 | 0.0003 | 0.526 |
| Dataset_1 | Textural Face Mapping (ULBP) | 77.81% | 0.082 | 0.000 | 0.887 |
| | | | | | |
| **Dataset_2** (LFW-RGB / Hindi) | **Signature Deep CNN (AlexNet_N)** | **96.81%** | **0.048** | **0.009** | **0.098** |
| Dataset_2 | Iris Metric Block (SE-AlexNet) | 84.24% | 0.264 | 0.019 | 0.573 |
| Dataset_2 | Multisystem Decision Fusion | 79.48% | 0.273 | 0.000 | 0.820 |
| Dataset_2 | Face Regional Deep (SE-AlexNet) | 77.40% | 0.351 | 0.028 | 0.817 |
| Dataset_2 | Textural Handcrafted Mapping (ULBP)| 75.13% | 0.173 | 0.000 | 0.994 |

### Analyzing Modality Paradigms

1.  **The Degradation of Environmental Lighting Physics:**
    The matrix outputs display massive physical degradation evaluating `Dataset_1` (CASIA) directly against `Dataset_2` (LFW). `Dataset_1` captures faces continuously illuminated identically against flat backgrounds generating `Face Deep` accuracy profiles hitting a staggering **96.04%** (EER 0.079).
    Comparatively, `Dataset_2` LFW images are captured entirely identically in-the-wild. Tensors geometrically track sunglasses, deep varied shading gradients, and physical yaw translations. Localized 30x30 cropped matrices heavily mismatch geometrical regions inherently derailing the RBF boundary lines entirely destroying recognition probabilities plummeting arrays natively dropping down to **77.40%** (EER 0.351). Environments distinctly destroy geometric bounds.
2.  **The Effectiveness of Generalized Behavioral Training Protocols:**
    Looking across both physically disjointed datasets, offline behavioral Signature CNNs completely dominate results universally logging `98.33%` and `96.81%`. Deep generalized systems trained totally agnostic to physical user mappings strictly interpreting mathematical curve topology utilizing explicit generalized regularization (`Batch Normalization2D`) significantly over-achieves over static image capturing algorithms. 
3.  **The Paradox of Fusion Mechanism Starvation:**
    The theoretical claim that fusion immediately increases verification metrics breaks under this specific mathematical implementation resulting natively charting lower arrays (e.g., Fusion mapping drops natively around `80-91%` overall losing against `98%` Signature bounds natively). Let's review why:
    *   **Textural Starvation Limits:** The hand-crafted traditional ML `ULBP Textural` modules struggle heavily hitting constant extreme False Negative Rates natively averaging `0.88-0.99`. This means the Texture system fundamentally guesses Negative almost continually geometrically. 
    *   **Decision Fusion Fails:** When mathematically dictating Majority Rule topologies (Requiring exactly 3 out of 5 sub-systems to vote Positive to grant entry), if the Texture systems natively refuse logic continuously, it physically forces the Face and Signature arrays to carry maximum weight perfectly. If one deep system fails the entire verification matrix starves logically destroying final outputs effectively dragging general average fusion down overall drastically. 
    *   **Feature Saturation:** Concatenating raw vectors geometrically builds a single 1D matrix arrays mapping over 10,496 continuous floats. Creating singular linear boundaries inside huge dense environments naturally allows noisy dimensions to negatively impact positive verification coordinates. 

---

## 7. Step-by-Step Training & Execution Protocols

Executing the pipeline from un-configured state scripts directly generating deliverable artifacts. The workflow dictates rigid script sequences implicitly mapping arrays properly. 

### Step 0: Base Dependencies & Raw Extractions
Ensure Python virtual environments map dependencies universally. Execute structural data models externally.
```bash
# Provide all internal global module dependencies
pip install -r requirements.txt

# Manually extract the physical 68-Dlib .dat coordinate predictive topology locally 
python download_dlib_model.py
```
*(Ensure physical User generated raw domains unzipped sit locally directly adjacent `main.py` referencing folders naming `CASIA-Iris-Distance/`, `BHSig260/`, etc.)*

### Step 1: Writer-Independent Deep Identity Abstraction Pre-Training
Before running identity predictions natively, the system physically maps global curves structurally inside convolution arrays mathematically separated physically isolating all 100 User testing environments from memory gradients guaranteeing non-biased topologies.
```bash
python train_wi_alexnet.py --epochs 20 --batch_size 16
```
*(Physical Executions generates `results/wi_alexnet_trained.pth` arrays)*

### Step 2: Channel Attention Tensor Mapping Configuration
Prior to analyzing vectors specifically, we mathematically structurally enforce fine-tuning processes calibrating SE mechanisms explicitly bridging facial geometries.
```bash
python train_se_alexnet.py --epochs 15 --batch_size 16
```
*(Physical Executions generates `results/se_alexnet_finetuned.pth` arrays)*

### Step 3: Global Multi-System Evaluation Execution Run
Launches the continuous matrix iteration process triggering `dataset_mappers` threading pipelines scaling `Dlib` coordinate sweeps generating continuous SV Hyperplane mapping testing Folds predicting graphical AUC arrays structurally generating table results effectively.
```bash
python main.py
```
* **Phase Execution Timing:** The primary execution maps unoptimized geometries initially natively extracting 100 Models 5 Folds continuously generating high processing timing. Continuous dynamic saves natively utilize caching topologies storing parameters structurally. Subsequent physical re-executions entirely skip retraining executing tests pulling `.joblib` matrices practically instantaneously tracking execution natively optimally.

---

## 8. Derived Output Artifacts Directory 

Once execution finishes structurally completely, generated deliverables validate project constraints globally. 

1. **Analytical Numerical Float Spaces:** Mapped specifically inside `extracted_features/*.csv` (Generating raw float properties demanded analytically representing structural deep states matrices natively derived bridging testing algorithms globally).
2. **K-Fold Multi-Variant Historical Tables:** Recorded accurately inside `results/all_fold_metrics.csv` (Generating historical tables representing all verification testing sweeps over 50 unique geometric arrays globally tracking every sub-modality test logically).
3. **Execution Summarization Tables:** Available explicitly inside `results/summary_accuracy_eer.csv` (The root evaluation matrix defining exactly the average parameters evaluating overall effectiveness natively logging Mean EER structures structurally mathematically evaluating constraints locally). 
4. **Graphical Diagnostic Verification Overlays:** Plotted out smoothly mapping True intersections natively inside `results/*_roc.png` (Generating perfectly linear intersection geometry pinpointing EER coordinate graphs evaluating ROC curves graphically mapping boundaries globally derived locally).
5. **Physical Intermediary Projections:** Saved natively reviewing constraints inside `visualizations/` (Storing bounding boxes tracking iris topologies proving algorithmic generation geometrically mapping unrolled dimensions successfully locally generating physics parameters dynamically).

---

## 9. Submission & Google Drive Assets (20MB Limit Bypass)

Due to structural constraints limiting academic portal uploads to 20MB, the project is physically partitioned. The core logical pipeline, reporting artifacts, and `.py` structural execution files are submitted natively in the `.zip` archive. 

Heavy dimensional arrays and dataset images natively exceed 20MB. They are hosted remotely.

**[INSERT_GOOGLE_DRIVE_LINK_HERE]**

### A. Core Submission Archive (Max 20MB)
*   **Source Code:** `src/` modules, `main.py`, and training script logic (`train_*.py`).
*   **Documentation:** This `README.md`, `requirements.txt`, and the generated report.
*   **Metadata:** Global mappings (`dataset_mapping.csv`) and calculated results logging (`results/*.csv` and `results/*.png`).

### B. Remote Drive Assets (Download Required)
To execute the pipeline entirely and bypass pre-training, please download the remote assets from the Google Drive link above and extract them into the repository to mimic the original structural state:

1.  **Datasets (`Raw Dataset/`):** Contains original CASIA, LFW, IITD, and BHSig uncompressed directories. Unzip this folder physically into the repository root.
2.  **Facial Geometry Topology (`shape_predictor_68_face_landmarks.dat`):** Place natively adjacent to `main.py` (or execute `python download_dlib_model.py` to fetch it natively).
3.  **Trained Neural Weights (`results/*.pth`):** Pre-trained SE-AlexNet and Writer-Independent Signature deep configurations. Place them inside `results/`.
4.  **Extracted Metrics & SVM Caches (`extracted_features/` and `results/svm_cache/`):** Pre-calculated `.joblib` SVM matrices and massive float tensors. Prevents expensive feature extractions. Place inside their respective root folders.
