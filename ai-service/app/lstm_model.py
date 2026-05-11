from __future__ import annotations

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - optional dependency fallback
    torch = None
    nn = None


if torch is not None:
    class RNNModel(nn.Module):
        def __init__(
            self,
            vocab_size: int,
            output_dim: int,
            embed_dim: int = 64,
            hidden_dim: int = 128,
            num_layers: int = 1,
            dropout: float = 0.2,
        ):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
            self.rnn = nn.RNN(
                input_size=embed_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim, output_dim)

        def forward(self, x):
            embedded = self.embedding(x)
            out, _ = self.rnn(embedded)
            out = self.dropout(out[:, -1, :])
            return self.fc(out)


    class LSTMModel(nn.Module):
        def __init__(
            self,
            vocab_size: int,
            output_dim: int,
            embed_dim: int = 64,
            hidden_dim: int = 128,
            num_layers: int = 1,
            dropout: float = 0.2,
        ):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
            self.lstm = nn.LSTM(
                input_size=embed_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim, output_dim)

        def forward(self, x):
            embedded = self.embedding(x)
            out, _ = self.lstm(embedded)
            out = self.dropout(out[:, -1, :])
            return self.fc(out)


    class BiLSTMModel(nn.Module):
        def __init__(
            self,
            vocab_size: int,
            output_dim: int,
            embed_dim: int = 64,
            hidden_dim: int = 128,
            num_layers: int = 1,
            dropout: float = 0.2,
        ):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
            self.lstm = nn.LSTM(
                input_size=embed_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                bidirectional=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim * 2, output_dim)

        def forward(self, x):
            embedded = self.embedding(x)
            out, _ = self.lstm(embedded)
            out = self.dropout(out[:, -1, :])
            return self.fc(out)
else:
    class RNNModel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def forward(self, x):
            raise RuntimeError("torch is not installed; RNNModel is unavailable in this environment.")


    class LSTMModel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def forward(self, x):
            raise RuntimeError("torch is not installed; LSTMModel is unavailable in this environment.")


    class BiLSTMModel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def forward(self, x):
            raise RuntimeError("torch is not installed; BiLSTMModel is unavailable in this environment.")
