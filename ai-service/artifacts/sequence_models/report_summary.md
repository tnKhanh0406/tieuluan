# Sequence Model Comparison Report

## Dataset and setup
- Dataset: ..\user_behavior.csv
- Sequence length: 5
- Number of classes: 100
- Train/Val/Test samples: 864/216/270
- Device: cpu

## Ranking rule
- Primary metric: f1_macro
- Tie-break 1: top3_accuracy
- Tie-break 2: accuracy

## Test set comparison
| Model | Params | Train time (s) | Loss | Accuracy | Precision macro | Recall macro | F1 macro | Top-3 accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bilstm | 231077 | 2.75 | 5.4556 | 0.0556 | 0.0295 | 0.0637 | 0.0347 | 0.1778 |
| rnn | 44325 | 2.58 | 5.4543 | 0.0481 | 0.0272 | 0.0519 | 0.0317 | 0.1593 |
| lstm | 118821 | 1.68 | 5.4943 | 0.0407 | 0.0194 | 0.0354 | 0.0213 | 0.1630 |

## Selected best model
- Best model: bilstm
- Checkpoint: artifacts\sequence_models\model_best.pt
- F1 macro: 0.0347
- Top-3 accuracy: 0.1778
- Accuracy: 0.0556

## Plots to include in thesis/report
- training_curves.png: compare convergence and overfitting behavior.
- model_comparison.png: compare final test metrics across RNN/LSTM/BiLSTM.

## Notes
- Use f1_macro as the primary score for multi-class imbalance robustness.
- Report top3_accuracy because recommendation often accepts multiple candidates.
- Params and training_seconds help justify accuracy-latency tradeoff.