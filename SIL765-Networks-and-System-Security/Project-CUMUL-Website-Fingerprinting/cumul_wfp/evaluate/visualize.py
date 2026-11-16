"""
Evaluation Visualizer
====================
Generate charts and visualizations from evaluation results.
"""

import os
import sys
import json
import glob
import warnings

# Suppress matplotlib warnings
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

os.environ['WIRESHARK_MANUF'] = r'C:\Program Files\Wireshark\manuf'
if 'SSLKEYLOGFILE' in os.environ:
    del os.environ['SSLKEYLOGFILE']

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def get_results_dir():
    """Get results directory path."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "results")


def get_latest_results():
    """Get the latest evaluation results."""
    results_dir = get_results_dir()
    
    # Find latest report
    reports = glob.glob(os.path.join(results_dir, "evaluation_report_*.json"))
    if not reports:
        return None
    latest_report = max(reports)
    
    with open(latest_report, 'r') as f:
        report = json.load(f)
    
    # Find corresponding confusion matrix
    timestamp = report['timestamp']
    cm_files = glob.glob(os.path.join(results_dir, f"confusion_matrix_{timestamp}.csv"))
    cm_data = None
    if cm_files:
        cm_data = load_confusion_matrix(cm_files[0])
    
    return report, cm_data, timestamp


def load_confusion_matrix(filepath):
    """Load confusion matrix from CSV."""
    import numpy as np
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    classes = lines[0].strip().split(',')[1:]
    cm = []
    for line in lines[1:]:
        row = list(map(int, line.strip().split(',')[1:]))
        cm.append(row)
    
    return np.array(cm), classes


def plot_cv_results(report, timestamp):
    """Plot cross-validation fold results."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    results_dir = get_results_dir()
    
    # Find CV results
    cv_files = glob.glob(os.path.join(results_dir, f"cv_results_{timestamp}.json"))
    if not cv_files:
        print("  [SKIP] No CV results found")
        return
    
    with open(cv_files[0], 'r') as f:
        cv_data = json.load(f)
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    
    # Fold accuracy bar chart
    fold_scores = cv_data['fold_scores']
    folds = list(range(1, len(fold_scores) + 1))
    mean_acc = cv_data['mean_accuracy']
    std_acc = cv_data['std_deviation']
    
    colors = ['#2ecc71' if s >= mean_acc else '#e74c3c' for s in fold_scores]
    axes[0].bar(folds, fold_scores, color=colors, edgecolor='black')
    axes[0].axhline(y=mean_acc, color='blue', linestyle='--', linewidth=2, label=f'Mean: {mean_acc:.1%}')
    axes[0].fill_between([-0.5, len(folds) + 0.5], mean_acc - std_acc, mean_acc + std_acc, 
                         alpha=0.2, color='blue', label=f'Std: {std_acc:.1%}')
    axes[0].set_xlabel('Fold')
    axes[0].set_ylabel('Accuracy')
    axes[0].set_title(f'Cross-Validation Results ({cv_data["cv_folds"]}-Fold)')
    axes[0].set_ylim(0, 1)
    axes[0].legend()
    axes[0].set_xticks(folds)
    
    # Summary statistics
    metrics = ['Mean\nAccuracy', 'Std Dev']
    values = [mean_acc, std_acc]
    colors = ['#3498db', '#9b59b6']
    bars = axes[1].bar(metrics, values, color=colors, edgecolor='black')
    axes[1].set_ylabel('Score')
    axes[1].set_title('CV Summary')
    axes[1].set_ylim(0, 1)
    
    for bar, val in zip(bars, values):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.1%}', ha='center', va='bottom', fontsize=12)
    
    plt.tight_layout()
    
    output_path = os.path.join(results_dir, f"cv_visualization_{timestamp}.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  [Saved] {output_path}")
    return output_path


def plot_per_class_metrics(report, timestamp):
    """Plot per-class performance metrics."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    
    results_dir = get_results_dir()
    
    classes = report['classes']
    sorted_classes = sorted(classes.items(), key=lambda x: x[1]['f1'], reverse=True)
    
    class_names = [c[0] for c in sorted_classes]
    precision = [c[1]['precision'] for c in sorted_classes]
    recall = [c[1]['recall'] for c in sorted_classes]
    f1 = [c[1]['f1'] for c in sorted_classes]
    support = [c[1]['support'] for c in sorted_classes]
    
    # Bar chart with grouped metrics
    x = np.arange(len(class_names))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(16, 8))
    
    bars1 = ax.bar(x - width, precision, width, label='Precision', color='#3498db', alpha=0.8)
    bars2 = ax.bar(x, recall, width, label='Recall', color='#2ecc71', alpha=0.8)
    bars3 = ax.bar(x + width, f1, width, label='F1-Score', color='#e74c3c', alpha=0.8)
    
    ax.set_xlabel('Website', fontsize=12)
    ax.set_ylabel('Score', fontsize=12)
    ax.set_title('Per-Class Classification Performance', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(class_names, rotation=45, ha='right', fontsize=8)
    ax.set_ylim(0, 1.1)
    ax.legend(loc='lower right')
    ax.grid(axis='y', alpha=0.3)
    
    # Add macro average line
    ax.axhline(y=report['macro_avg']['f1'], color='gray', linestyle='--', alpha=0.7,
               label=f"Macro F1: {report['macro_avg']['f1']:.1%}")
    
    plt.tight_layout()
    
    output_path = os.path.join(results_dir, f"per_class_metrics_{timestamp}.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  [Saved] {output_path}")
    return output_path


def plot_confusion_matrix(cm_data, report, timestamp):
    """Plot confusion matrix heatmap."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    
    if cm_data is None:
        print("  [SKIP] No confusion matrix data")
        return
    
    results_dir = get_results_dir()
    cm, classes = cm_data
    
    # Normalize by row (true class)
    cm_normalized = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    np.nan_to_num(cm_normalized, copy=False)
    
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    
    # Raw counts
    im1 = axes[0].imshow(cm, cmap='Blues', aspect='auto')
    axes[0].set_title('Confusion Matrix (Counts)', fontsize=14)
    axes[0].set_xticks(range(len(classes)))
    axes[0].set_yticks(range(len(classes)))
    axes[0].set_xticklabels(classes, rotation=45, ha='right', fontsize=7)
    axes[0].set_yticklabels(classes, fontsize=7)
    axes[0].set_xlabel('Predicted Class')
    axes[0].set_ylabel('True Class')
    plt.colorbar(im1, ax=axes[0], shrink=0.8)
    
    # Normalized
    im2 = axes[1].imshow(cm_normalized, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
    axes[1].set_title('Confusion Matrix (Normalized by Row)', fontsize=14)
    axes[1].set_xticks(range(len(classes)))
    axes[1].set_yticks(range(len(classes)))
    axes[1].set_xticklabels(classes, rotation=45, ha='right', fontsize=7)
    axes[1].set_yticklabels(classes, fontsize=7)
    axes[1].set_xlabel('Predicted Class')
    axes[1].set_ylabel('True Class')
    plt.colorbar(im2, ax=axes[1], shrink=0.8)
    
    plt.tight_layout()
    
    output_path = os.path.join(results_dir, f"confusion_matrix_{timestamp}.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  [Saved] {output_path}")
    return output_path


def plot_summary_dashboard(report, timestamp):
    """Create a summary dashboard."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    
    results_dir = get_results_dir()
    
    fig = plt.figure(figsize=(14, 10))
    
    # Title
    fig.suptitle('Website Fingerprinting - Evaluation Summary\n' + 
                 f'Evaluated: {report["timestamp"]}', fontsize=16, fontweight='bold')
    
    # Grid layout
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # 1. Key metrics (top left)
    ax1 = fig.add_subplot(gs[0, 0])
    metrics = ['CV Accuracy', 'Train Acc', 'Macro F1', 'Weighted F1']
    values = [report['cv_accuracy_mean'], report['training_accuracy_monitored'],
               report['macro_avg']['f1'], report['weighted_avg']['f1']]
    colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']
    
    bars = ax1.barh(metrics, values, color=colors, edgecolor='black')
    ax1.set_xlim(0, 1)
    ax1.set_title('Key Metrics', fontsize=12, fontweight='bold')
    for bar, val in zip(bars, values):
        ax1.text(val + 0.02, bar.get_y() + bar.get_height()/2, 
                f'{val:.1%}', va='center', fontsize=10)
    
    # 2. Class distribution (top middle)
    ax2 = fig.add_subplot(gs[0, 1])
    n_monitored = report['n_monitored']
    n_background = report['n_background']
    sizes = [n_monitored, n_background]
    labels = [f'Monitored\n({n_monitored})', f'Background\n({n_background})']
    colors = ['#3498db', '#95a5a6']
    ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax2.set_title('Data Distribution', fontsize=12, fontweight='bold')
    
    # 3. F1 score distribution (top right)
    ax3 = fig.add_subplot(gs[0, 2])
    f1_scores = [c['f1'] for c in report['classes'].values()]
    ax3.hist(f1_scores, bins=10, color='#9b59b6', edgecolor='black', alpha=0.7)
    ax3.axvline(x=np.mean(f1_scores), color='red', linestyle='--', 
                label=f'Mean: {np.mean(f1_scores):.1%}')
    ax3.set_xlabel('F1-Score')
    ax3.set_ylabel('Count')
    ax3.set_title('F1-Score Distribution', fontsize=12, fontweight='bold')
    ax3.legend()
    
    # 4. Top/Bottom performing sites (middle row)
    ax4 = fig.add_subplot(gs[1, :])
    sorted_classes = sorted(report['classes'].items(), key=lambda x: x[1]['f1'], reverse=True)
    top5 = sorted_classes[:5]
    bottom5 = sorted_classes[-5:]
    
    combined = top5 + [('...', {'f1': 0})] + bottom5
    names = [c[0] for c in combined]
    f1s = [c[1]['f1'] for c in combined]
    
    colors_bar = ['#2ecc71'] * 5 + ['white'] + ['#e74c3c'] * 5
    bars = ax4.bar(names, f1s, color=colors_bar, edgecolor='black')
    ax4.set_ylabel('F1-Score')
    ax4.set_title('Top 5 vs Bottom 5 Performing Sites', fontsize=12, fontweight='bold')
    ax4.set_xticks(range(len(names)))
    ax4.set_xticklabels(names, rotation=45, ha='right')
    ax4.set_ylim(0, 1.1)
    ax4.axhline(y=report['macro_avg']['f1'], color='blue', linestyle='--', 
                label=f"Macro Avg: {report['macro_avg']['f1']:.1%}")
    ax4.legend()
    
    # 5. Precision vs Recall scatter (bottom row)
    ax5 = fig.add_subplot(gs[2, :2])
    for name, metrics in sorted_classes:
        p, r = metrics['precision'], metrics['recall']
        ax5.scatter(p, r, alpha=0.7, s=100)
        ax5.annotate(name, (p, r), fontsize=7, alpha=0.7)
    
    ax5.set_xlabel('Precision')
    ax5.set_ylabel('Recall')
    ax5.set_title('Precision vs Recall by Site', fontsize=12, fontweight='bold')
    ax5.set_xlim(-0.05, 1.05)
    ax5.set_ylim(-0.05, 1.05)
    ax5.grid(True, alpha=0.3)
    
    # 6. Summary stats box (bottom right)
    ax6 = fig.add_subplot(gs[2, 2])
    ax6.axis('off')
    
    f1_scores_list = [c['f1'] for c in report['classes'].values()]
    stats_text = f"""
    Summary Statistics
    -----------------
    Total Classes: {len(report['classes'])}
    Monitored Sites: {report['n_monitored']}
    Background Sites: {report['n_background']}
    
    F1-Score:
      Mean: {np.mean(f1_scores_list):.1%}
      Min: {np.min(f1_scores_list):.1%}
      Max: {np.max(f1_scores_list):.1%}
      Std: {np.std(f1_scores_list):.1%}
    
    Best Site: {sorted_classes[0][0]} ({sorted_classes[0][1]['f1']:.1%})
    Worst Site: {sorted_classes[-1][0]} ({sorted_classes[-1][1]['f1']:.1%})
    """
    ax6.text(0.1, 0.9, stats_text, transform=ax6.transAxes, fontsize=10,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    fig.subplots_adjust(hspace=0.35, wspace=0.3)
    
    output_path = os.path.join(results_dir, f"evaluation_dashboard_{timestamp}.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  [Saved] {output_path}")
    return output_path


def run():
    """Generate all visualizations."""
    print("=" * 60)
    print("  GENERATING EVALUATION VISUALIZATIONS")
    print("=" * 60)
    
    results = get_latest_results()
    if results is None:
        print("\n  [ERROR] No evaluation results found.")
        print("  Run evaluation first (Option 4 in main menu).")
        return
    
    report, cm_data, timestamp = results
    
    print(f"\n  Found results from: {timestamp}")
    print("\n  Generating visualizations...")
    print("-" * 60)
    
    plot_cv_results(report, timestamp)
    plot_per_class_metrics(report, timestamp)
    plot_confusion_matrix(cm_data, report, timestamp)
    plot_summary_dashboard(report, timestamp)
    
    print("\n" + "=" * 60)
    print("  VISUALIZATIONS COMPLETE")
    print("=" * 60)
    print(f"  Saved to: {get_results_dir()}/")
    print("=" * 60)


if __name__ == "__main__":
    run()
