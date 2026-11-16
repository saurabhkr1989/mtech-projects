import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc
import pandas as pd
from sys import path

path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config

# Path for the running CSV file that accumulates all fold metrics across the experiment
ALL_METRICS_CSV = os.path.join(Config.RESULTS_DIR, "all_fold_metrics.csv")

class Evaluator:
    """
    Evaluates the biometric system performance using Cross-Validation.
    Calculates Accuracy, FPR, FNR, ROC Curves, and Equal Error Rate (EER).
    """
    def __init__(self, output_dir=Config.RESULTS_DIR):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        # Dictionary to accumulate all test labels and probabilities across folds
        # Format: { "Dataset_Name": { "ModalityName": {"y_true": [], "y_prob": []} } }
        self.aggregated_predictions = {}

    def compute_eer(self, fpr, tpr):
        """
        Computes the Equal Error Rate via linear intersection.
        EER occurs where FPR = FNR (= 1 - TPR).
        Returns None if the arrays are empty or all-NaN.
        """
        fnr = 1.0 - np.asarray(tpr, dtype=float)
        fpr = np.asarray(fpr, dtype=float)
        
        diff = fnr - fpr
        
        # The ROC curve is formed by connecting the (FPR, TPR) points.
        # The EER is exactly where the FNR - FPR line segment crosses zero.
        for i in range(len(diff) - 1):
            if diff[i] * diff[i+1] <= 0:
                # exact hit or segment crosses zero
                if diff[i+1] == diff[i]:
                    return float(fpr[i])
                
                # linear interpolation
                t = -diff[i] / (diff[i+1] - diff[i])
                eer = fpr[i] + t * (fpr[i+1] - fpr[i])
                return float(eer)

        # fallback if no sign-change is perfectly found
        abs_diff = np.absolute(diff)
        finite_mask = np.isfinite(abs_diff)
        if not np.any(finite_mask):
            return float("nan")
        idx = np.argmin(abs_diff[finite_mask])
        orig_idx = np.where(finite_mask)[0][idx]
        return float(fpr[orig_idx])

    def calculate_metrics(self, y_true, y_pred_prob=None, y_pred=None, threshold=0.5):
        """
        Calculates Accuracy, FNR, and FPR.
        If y_pred is provided, uses it directly. Otherwise, falls back to thresholding y_pred_prob.
        Returns a dictionary of metrics.
        """
        y_true = np.array(y_true)
        
        if y_pred is not None:
            y_pred = np.array(y_pred)
        else:
            y_prob = np.array(y_pred_prob)
            y_pred = (y_prob >= threshold).astype(int)
        
        # True Positives, etc.
        TP = np.sum((y_pred == 1) & (y_true == 1))
        TN = np.sum((y_pred == 0) & (y_true == 0))
        FP = np.sum((y_pred == 1) & (y_true == 0))
        FN = np.sum((y_pred == 0) & (y_true == 1))
        
        total = max(len(y_true), 1)
        accuracy = (TP + TN) / total
        
        fpr = FP / max((FP + TN), 1)
        fnr = FN / max((FN + TP), 1)
        
        return {
            "Accuracy": accuracy,
            "FPR": fpr,
            "FNR": fnr
        }

    def plot_and_save_roc(self, title, filename_prefix, results_dict):
        """
        Plots ROC curves mapping TPR against FPR for each modality.
        
        results_dict: Format { "ModalityName": (y_true_list, y_prob_list) }
        """
        plt.figure(figsize=(10, 8))
        
        for modality_name, (y_true, y_prob) in results_dict.items():
            if len(y_true) == 0:
                continue
            # Guard against degenerate folds where all labels are the same class
            y_t = np.array(y_true)
            if np.sum(y_t) == 0 or np.sum(y_t) == len(y_t):
                continue
            fpr, tpr, _ = roc_curve(y_true, y_prob, drop_intermediate=False)
            roc_auc = auc(fpr, tpr)
            eer = self.compute_eer(fpr, tpr)
            if not np.isfinite(eer):
                eer = 0.5
            plt.plot(fpr, tpr, lw=2, label=f'{modality_name} (AUC = {roc_auc:.3f}, EER = {eer:.3f})')
        
        # Plot diagonal random guess line
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate (FPR)')
        plt.ylabel('True Positive Rate (TPR)')
        plt.title(f'ROC Curve - {title}')
        plt.legend(loc="lower right")
        plt.grid(True, alpha=0.3)
        
        filepath = os.path.join(self.output_dir, f"{filename_prefix}_roc.png")
        plt.savefig(filepath, dpi=300)
        plt.close()
        
        print(f"[{title}] ROC Curve saved to: {filepath}")

    def evaluate_cross_val_fold(self, fold_idx, dataset_name, test_results):
        """
        Calculates and logs metrics for a specific CV fold.

        test_results format:
            { "ModalityName": [ {"y_true": int, "y_prob": float}, ... ] }
        """
        print(f"\n{'='*40}")
        print(f"Evaluating {dataset_name} - Fold {fold_idx}")
        print(f"{'='*40}")
        
        metrics_log = []
        plot_dict   = {}
        
        for modality, results in test_results.items():
            y_true = np.array([r["y_true"] for r in results])
            y_prob = np.array([r["y_prob"] for r in results])
            
            y_pred_list = [r.get("y_pred") for r in results]
            if None not in y_pred_list and len(y_pred_list) > 0:
                y_pred = np.array(y_pred_list)
            else:
                y_pred = None

            # Skip silently if no positive samples exist — roc_curve produces NaN in that case
            if len(y_true) == 0 or np.sum(y_true) == 0 or np.sum(y_true) == len(y_true):
                print(f"[{modality}] SKIP — no genuine/impostor variation in fold {fold_idx}")
                continue

            plot_dict[modality] = (y_true.tolist(), y_prob.tolist())

            # EER is the primary performance measure here
            metrics = self.calculate_metrics(y_true, y_pred_prob=y_prob, y_pred=y_pred)

            # Accumulate predictions for aggregated ROC Curve over all folds
            if dataset_name not in self.aggregated_predictions:
                self.aggregated_predictions[dataset_name] = {}
            if modality not in self.aggregated_predictions[dataset_name]:
                self.aggregated_predictions[dataset_name][modality] = {"y_true": [], "y_prob": []}
            self.aggregated_predictions[dataset_name][modality]["y_true"].extend(y_true.tolist())
            self.aggregated_predictions[dataset_name][modality]["y_prob"].extend(y_prob.tolist())

            # Compute EER from the full ROC
            try:
                fpr_array, tpr_array, _ = roc_curve(y_true, y_prob, drop_intermediate=False)
                eer = self.compute_eer(fpr_array, tpr_array)
                # If EER came back as NaN, fall back to 0.5 (worst-case placeholder)
                if not np.isfinite(eer):
                    eer = 0.5
            except Exception as roc_err:
                print(f"[{modality}] ROC computation failed: {roc_err} — skipping EER for this modality.")
                eer = float("nan")

            metrics["EER"]      = eer
            metrics["Modality"] = modality
            metrics["Fold"]     = fold_idx
            metrics["Dataset"]  = dataset_name

            print(f"[{modality}] Acc: {metrics['Accuracy']:.4f} | EER: {eer:.4f} | "
                  f"FPR: {metrics['FPR']:.4f} | FNR: {metrics['FNR']:.4f}")
            metrics_log.append(metrics)
        
        # --- Persist fold metrics to CSV (required by assignment deliverables) ---
        # Append mode means each fold adds a new row block without overwriting prior folds
        fold_df = pd.DataFrame(metrics_log)
        write_header = not os.path.exists(ALL_METRICS_CSV) or os.path.getsize(ALL_METRICS_CSV) == 0
        fold_df.to_csv(ALL_METRICS_CSV, mode='a', header=write_header, index=False)
        print(f"[Fold {fold_idx}] Metrics appended to: {ALL_METRICS_CSV}")
            
        # Save ROC curve PNG for this fold (only if there are valid modalities to plot)
        if plot_dict:
            self.plot_and_save_roc(
                f"{dataset_name} - Fold {fold_idx}",
                f"{dataset_name}_fold_{fold_idx}",
                plot_dict
            )
        else:
            print(f"[Fold {fold_idx}] No valid modalities to plot for ROC curve — skipping plot.")
        
        return metrics_log

    def finalize_results(self):
        """
        Reads the accumulated metrics and writes a summary CSV
        showing mean metrics per modality and dataset.
        """
        if not os.path.exists(ALL_METRICS_CSV):
            print("No metrics CSV found yet. Run evaluate_cross_val_fold first.")
            return
        
        # Load all fold metrics
        all_metrics_df = pd.read_csv(ALL_METRICS_CSV)
        
        # Group by Dataset and Modality, then average across the 5 folds
        summary_df = all_metrics_df.groupby(["Dataset", "Modality"]).agg(
            Mean_Accuracy = ("Accuracy", "mean"),
            Mean_EER      = ("EER",      "mean"),
            Mean_FPR      = ("FPR",      "mean"),
            Mean_FNR      = ("FNR",      "mean"),
            Num_Folds     = ("Fold",     "count")
        ).reset_index()
        
        # Save the human-readable summary for the report
        summary_path = os.path.join(self.output_dir, "summary_accuracy_eer.csv")
        summary_df.to_csv(summary_path, index=False)
        print(f"Summary results saved to: {summary_path}")
        print(summary_df.to_string(index=False))
        
        # Plot Aggregated ROC Curves for each dataset dynamically
        print("\nPlotting Aggregated (5-Fold Averaged) Smoothed ROC Curves...")
        for dataset_name, modes in self.aggregated_predictions.items():
            agg_plot_dict = {}
            for modality, lists in modes.items():
                agg_plot_dict[modality] = (lists["y_true"], lists["y_prob"])
            self.plot_and_save_roc(
                f"{dataset_name} - All Folds Aggregated (Smoothed)",
                f"{dataset_name}_aggregated",
                agg_plot_dict
            )
        
        return summary_df

if __name__ == "__main__":
    print("Testing Evaluator Logic...")
    eval_sys = Evaluator()
    # Mock data
    y_t = [1, 1, 0, 0, 1, 0, 0, 1]
    y_p = [0.9, 0.8, 0.2, 0.1, 0.7, 0.3, 0.4, 0.6]
    metrics = eval_sys.calculate_metrics(y_t, y_pred_prob=y_p)
    
    mock_dict = {"Mock Modality": (y_t, y_p)}
    eval_sys.plot_and_save_roc("Test Logic", "test", mock_dict)
    print("Results computed. Evaluator is syntactically sound.")
