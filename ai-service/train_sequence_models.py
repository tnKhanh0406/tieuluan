from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, top_k_accuracy_score
from sklearn.model_selection import train_test_split

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
except Exception as exc:
    raise RuntimeError(
        "PyTorch is required for RNN/LSTM/BiLSTM training. Install dependencies from training-requirements.txt"
    ) from exc

from app.lstm_model import BiLSTMModel, LSTMModel, RNNModel


ACTION_TO_WEIGHT = {
    "view": 1.0,
    "click": 1.5,
    "search": 1.2,
    "compare": 1.2,
    "wishlist": 1.8,
    "add_to_cart": 2.4,
    "purchase": 3.0,
}


@dataclass
class Sample:
    sequence: list[int]
    label: int
    sample_weight: float


class SequenceDataset(Dataset):
    def __init__(self, samples: list[Sample]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        item = self.samples[index]
        return (
            torch.tensor(item.sequence, dtype=torch.long),
            torch.tensor(item.label, dtype=torch.long),
            torch.tensor(item.sample_weight, dtype=torch.float32),
        )


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def normalize_action(action: str) -> str:
    action = str(action).lower()
    aliases = {
        "add-to-cart": "add_to_cart",
        "cart": "add_to_cart",
        "buy": "purchase",
    }
    return aliases.get(action, action)


def build_samples(df: pd.DataFrame, sequence_len: int) -> tuple[list[Sample], dict[int, int], dict[int, int]]:
    ordered = df.sort_values(["user_id", "timestamp", "product_id"]).copy()

    unique_products = sorted(ordered["product_id"].astype(int).unique().tolist())
    product_to_idx = {pid: idx + 1 for idx, pid in enumerate(unique_products)}
    idx_to_product = {idx: pid for pid, idx in product_to_idx.items()}

    samples: list[Sample] = []
    for _, group in ordered.groupby("user_id"):
        items = group["product_id"].astype(int).tolist()
        actions = [normalize_action(action) for action in group["action"].astype(str).tolist()]
        if len(items) <= sequence_len:
            continue

        mapped_items = [product_to_idx[item] for item in items]
        for end in range(sequence_len, len(mapped_items)):
            seq = mapped_items[end - sequence_len : end]
            target = mapped_items[end]
            event_action = actions[end]
            sample_weight = ACTION_TO_WEIGHT.get(event_action, 1.0)
            samples.append(Sample(sequence=seq, label=target, sample_weight=sample_weight))

    return samples, product_to_idx, idx_to_product


def split_samples(samples: list[Sample], seed: int) -> tuple[list[Sample], list[Sample], list[Sample]]:
    if len(samples) < 30:
        raise ValueError("Dataset too small for train/val/test split. Need at least 30 sequence samples.")

    indices = np.arange(len(samples))
    labels = np.array([s.label for s in samples])
    label_counts = pd.Series(labels).value_counts()
    can_stratify = int(label_counts.min()) >= 2

    if not can_stratify:
        print("[WARN] Some classes have < 2 samples. Falling back to non-stratified split.")

    train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=seed, stratify=labels if can_stratify else None)
    train_labels = labels[train_idx]
    train_label_counts = pd.Series(train_labels).value_counts()
    can_stratify_train = int(train_label_counts.min()) >= 2

    if can_stratify and not can_stratify_train:
        print("[WARN] Train split has sparse classes. Falling back to non-stratified train/val split.")

    train_idx, val_idx = train_test_split(
        train_idx,
        test_size=0.2,
        random_state=seed,
        stratify=train_labels if can_stratify and can_stratify_train else None,
    )

    train = [samples[i] for i in train_idx]
    val = [samples[i] for i in val_idx]
    test = [samples[i] for i in test_idx]
    return train, val, test


def create_model(name: str, vocab_size: int, output_dim: int, hidden_dim: int, num_layers: int, dropout: float):
    if name == "rnn":
        return RNNModel(vocab_size=vocab_size, output_dim=output_dim, hidden_dim=hidden_dim, num_layers=num_layers, dropout=dropout)
    if name == "lstm":
        return LSTMModel(vocab_size=vocab_size, output_dim=output_dim, hidden_dim=hidden_dim, num_layers=num_layers, dropout=dropout)
    if name == "bilstm":
        return BiLSTMModel(vocab_size=vocab_size, output_dim=output_dim, hidden_dim=hidden_dim, num_layers=num_layers, dropout=dropout)
    raise ValueError(f"Unsupported model: {name}")


def count_params(model: nn.Module) -> int:
    return sum(param.numel() for param in model.parameters() if param.requires_grad)


def evaluate_model(model: nn.Module, loader: DataLoader, criterion: nn.Module, device: torch.device, class_labels: np.ndarray) -> dict[str, float]:
    model.eval()
    total_loss = 0.0
    y_true: list[int] = []
    y_pred: list[int] = []
    y_prob: list[np.ndarray] = []

    with torch.no_grad():
        for features, targets, sample_weights in loader:
            features = features.to(device)
            targets = targets.to(device)
            sample_weights = sample_weights.to(device)

            logits = model(features)
            loss_vector = criterion(logits, targets)
            loss = (loss_vector * sample_weights).mean()
            total_loss += loss.item()

            probabilities = torch.softmax(logits, dim=1)
            predictions = torch.argmax(probabilities, dim=1)

            y_true.extend(targets.cpu().numpy().tolist())
            y_pred.extend(predictions.cpu().numpy().tolist())
            y_prob.extend(probabilities.cpu().numpy())

    average_loss = total_loss / max(1, len(loader))
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)

    prob_matrix = np.array(y_prob)
    y_true_np = np.array(y_true)
    top3 = top_k_accuracy_score(y_true_np, prob_matrix, k=3, labels=class_labels)

    return {
        "loss": float(average_loss),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision),
        "recall_macro": float(recall),
        "f1_macro": float(f1),
        "top3_accuracy": float(top3),
    }


def train_one_model(
    model_name: str,
    train_loader: DataLoader,
    val_loader: DataLoader,
    test_loader: DataLoader,
    vocab_size: int,
    output_dim: int,
    hidden_dim: int,
    num_layers: int,
    dropout: float,
    learning_rate: float,
    epochs: int,
    device: torch.device,
    model_output_dir: Path,
) -> dict[str, object]:
    start_time = time.perf_counter()
    model = create_model(model_name, vocab_size, output_dim, hidden_dim, num_layers, dropout).to(device)
    criterion = nn.CrossEntropyLoss(reduction="none")
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    history = {
        "train_loss": [],
        "val_loss": [],
        "val_accuracy": [],
        "val_f1_macro": [],
        "val_top3_accuracy": [],
    }

    best_state = None
    best_f1 = -1.0
    class_labels = np.arange(output_dim)

    for _ in range(epochs):
        model.train()
        running_loss = 0.0

        for features, targets, sample_weights in train_loader:
            features = features.to(device)
            targets = targets.to(device)
            sample_weights = sample_weights.to(device)

            optimizer.zero_grad()
            logits = model(features)
            loss_vector = criterion(logits, targets)
            loss = (loss_vector * sample_weights).mean()
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

        train_loss = running_loss / max(1, len(train_loader))
        val_metrics = evaluate_model(model, val_loader, criterion, device, class_labels)

        history["train_loss"].append(float(train_loss))
        history["val_loss"].append(val_metrics["loss"])
        history["val_accuracy"].append(val_metrics["accuracy"])
        history["val_f1_macro"].append(val_metrics["f1_macro"])
        history["val_top3_accuracy"].append(val_metrics["top3_accuracy"])

        if val_metrics["f1_macro"] > best_f1:
            best_f1 = val_metrics["f1_macro"]
            best_state = {key: value.cpu().clone() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    test_metrics = evaluate_model(model, test_loader, criterion, device, class_labels)

    model_output_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_output_dir / f"{model_name}.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "model_name": model_name,
            "vocab_size": vocab_size,
            "output_dim": output_dim,
            "hidden_dim": hidden_dim,
            "num_layers": num_layers,
            "dropout": dropout,
        },
        model_path,
    )
    training_seconds = float(time.perf_counter() - start_time)

    return {
        "model": model_name,
        "params": int(count_params(model)),
        "history": history,
        "test_metrics": test_metrics,
        "checkpoint": str(model_path),
        "training_seconds": training_seconds,
    }


def plot_histories(results: list[dict[str, object]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for result in results:
        model_name = result["model"]
        history = result["history"]
        epochs = np.arange(1, len(history["train_loss"]) + 1)

        axes[0, 0].plot(epochs, history["train_loss"], label=f"{model_name} train")
        axes[0, 0].plot(epochs, history["val_loss"], linestyle="--", label=f"{model_name} val")
        axes[0, 1].plot(epochs, history["val_accuracy"], label=model_name)
        axes[1, 0].plot(epochs, history["val_f1_macro"], label=model_name)
        axes[1, 1].plot(epochs, history["val_top3_accuracy"], label=model_name)

    axes[0, 0].set_title("Loss")
    axes[0, 1].set_title("Validation Accuracy")
    axes[1, 0].set_title("Validation F1 Macro")
    axes[1, 1].set_title("Validation Top-3 Accuracy")

    for axis in axes.ravel():
        axis.set_xlabel("Epoch")
        axis.grid(alpha=0.25)
        axis.legend()

    plt.tight_layout()
    plt.savefig(output_dir / "training_curves.png", dpi=180)
    plt.close(fig)

    comparison_metrics = [
        {
            "model": result["model"],
            "params": result["params"],
            **result["test_metrics"],
        }
        for result in results
    ]
    comparison_df = pd.DataFrame(comparison_metrics).sort_values(["f1_macro", "top3_accuracy", "accuracy"], ascending=False)

    fig2, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(comparison_df))
    width = 0.18
    metrics = ["accuracy", "f1_macro", "top3_accuracy", "precision_macro"]
    for idx, metric in enumerate(metrics):
        ax.bar(x + idx * width, comparison_df[metric], width=width, label=metric)

    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(comparison_df["model"].tolist())
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Test Metrics Comparison")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_dir / "model_comparison.png", dpi=180)
    plt.close(fig2)


def save_epoch_metrics(results: list[dict[str, object]], output_dir: Path) -> None:
    rows: list[dict[str, float | int | str]] = []
    for result in results:
        model_name = str(result["model"])
        history = result["history"]
        total_epochs = len(history["train_loss"])
        for idx in range(total_epochs):
            rows.append(
                {
                    "model": model_name,
                    "epoch": idx + 1,
                    "train_loss": float(history["train_loss"][idx]),
                    "val_loss": float(history["val_loss"][idx]),
                    "val_accuracy": float(history["val_accuracy"][idx]),
                    "val_f1_macro": float(history["val_f1_macro"][idx]),
                    "val_top3_accuracy": float(history["val_top3_accuracy"][idx]),
                }
            )

    pd.DataFrame(rows).to_csv(output_dir / "epoch_metrics.csv", index=False)


def write_report_markdown(output_dir: Path, metadata: dict[str, object]) -> None:
    comparison = metadata["comparison"]
    best = metadata["model_best"]

    lines = [
        "# Sequence Model Comparison Report",
        "",
        "## Dataset and setup",
        f"- Dataset: {metadata['dataset']}",
        f"- Sequence length: {metadata['sequence_len']}",
        f"- Number of classes: {metadata['num_classes']}",
        f"- Train/Val/Test samples: {metadata['train_samples']}/{metadata['val_samples']}/{metadata['test_samples']}",
        f"- Device: {metadata['device']}",
        "",
        "## Ranking rule",
        "- Primary metric: f1_macro",
        "- Tie-break 1: top3_accuracy",
        "- Tie-break 2: accuracy",
        "",
        "## Test set comparison",
        "| Model | Params | Train time (s) | Loss | Accuracy | Precision macro | Recall macro | F1 macro | Top-3 accuracy |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in comparison:
        lines.append(
            "| "
            + f"{row['model']} | {int(row['params'])} | {float(row.get('training_seconds', 0.0)):.2f} | "
            + f"{float(row['loss']):.4f} | {float(row['accuracy']):.4f} | {float(row['precision_macro']):.4f} | "
            + f"{float(row['recall_macro']):.4f} | {float(row['f1_macro']):.4f} | {float(row['top3_accuracy']):.4f} |"
        )

    lines.extend(
        [
            "",
            "## Selected best model",
            f"- Best model: {best['model']}",
            f"- Checkpoint: {best['checkpoint']}",
            f"- F1 macro: {float(best['metrics']['f1_macro']):.4f}",
            f"- Top-3 accuracy: {float(best['metrics']['top3_accuracy']):.4f}",
            f"- Accuracy: {float(best['metrics']['accuracy']):.4f}",
            "",
            "## Plots to include in thesis/report",
            "- training_curves.png: compare convergence and overfitting behavior.",
            "- model_comparison.png: compare final test metrics across RNN/LSTM/BiLSTM.",
            "",
            "## Notes",
            "- Use f1_macro as the primary score for multi-class imbalance robustness.",
            "- Report top3_accuracy because recommendation often accepts multiple candidates.",
            "- Params and training_seconds help justify accuracy-latency tradeoff.",
        ]
    )

    (output_dir / "report_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and compare RNN/LSTM/BiLSTM for next-item classification.")
    parser.add_argument("--data", type=str, default="./user_behavior.csv")
    parser.add_argument("--output", type=str, default="./artifacts/sequence_models")
    parser.add_argument("--sequence-len", type=int, default=5)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--num-layers", type=int, default=1)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)

    data_path = Path(args.data)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(data_path)
    required_cols = {"user_id", "product_id", "action", "timestamp"}
    if not required_cols.issubset(set(df.columns)):
        raise ValueError(f"Input CSV must contain columns: {sorted(required_cols)}")

    samples, product_to_idx, idx_to_product = build_samples(df, sequence_len=args.sequence_len)
    train_samples, val_samples, test_samples = split_samples(samples, seed=args.seed)

    train_loader = DataLoader(SequenceDataset(train_samples), batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(SequenceDataset(val_samples), batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(SequenceDataset(test_samples), batch_size=args.batch_size, shuffle=False)

    vocab_size = len(product_to_idx) + 1
    output_dim = len(product_to_idx) + 1
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    results = []
    for model_name in ["rnn", "lstm", "bilstm"]:
        result = train_one_model(
            model_name=model_name,
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=test_loader,
            vocab_size=vocab_size,
            output_dim=output_dim,
            hidden_dim=args.hidden_dim,
            num_layers=args.num_layers,
            dropout=args.dropout,
            learning_rate=args.learning_rate,
            epochs=args.epochs,
            device=device,
            model_output_dir=output_dir,
        )
        results.append(result)

    plot_histories(results, output_dir)

    comparison = [
        {
            "model": result["model"],
            "params": result["params"],
            "training_seconds": result["training_seconds"],
            **result["test_metrics"],
            "checkpoint": result["checkpoint"],
        }
        for result in results
    ]

    comparison_sorted = sorted(comparison, key=lambda item: (item["f1_macro"], item["top3_accuracy"], item["accuracy"]), reverse=True)
    best = comparison_sorted[0]

    model_best_path = output_dir / "model_best.pt"
    source_best_path = Path(best["checkpoint"])
    model_best_path.write_bytes(source_best_path.read_bytes())

    metadata = {
        "dataset": str(data_path),
        "sequence_len": args.sequence_len,
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "test_samples": len(test_samples),
        "num_classes": len(product_to_idx),
        "device": str(device),
        "ranking_rule": ["f1_macro", "top3_accuracy", "accuracy"],
        "comparison": comparison_sorted,
        "model_best": {
            "model": best["model"],
            "params": best["params"],
            "checkpoint": str(model_best_path),
            "metrics": {
                "accuracy": best["accuracy"],
                "precision_macro": best["precision_macro"],
                "recall_macro": best["recall_macro"],
                "f1_macro": best["f1_macro"],
                "top3_accuracy": best["top3_accuracy"],
                "loss": best["loss"],
            },
        },
        "id_mapping": {
            "product_to_idx": product_to_idx,
            "idx_to_product": idx_to_product,
        },
    }

    with (output_dir / "metrics.json").open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)

    save_epoch_metrics(results, output_dir)
    pd.DataFrame(comparison_sorted).to_csv(output_dir / "comparison.csv", index=False)
    write_report_markdown(output_dir, metadata)

    print("Training complete")
    print(f"Best model: {best['model']}")
    print(f"Best F1-macro: {best['f1_macro']:.4f}")
    print(f"Artifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()
