# AI Service

FastAPI microservice for e-commerce recommendations and chatbot suggestions.

## Architecture
- Sequence model: trained from `user_behavior.csv` on startup (next-item transition model).
- Graph model: Neo4j (`User`, `Product`, `INTERACT`, `SIMILAR`) with in-memory fallback.
- Retrieval model: FAISS over TF-IDF embeddings from product metadata.
- RAG response: retrieve candidates then generate a concise advisory answer.

## Endpoints
- `GET /ai/health`
- `GET /ai/summary`
- `GET /ai/recommend?user_id=3&limit=5&query=laptop gaming`
- `POST /ai/chatbot`
- `POST /ai/track`

## Data source
- `user_behavior.csv` is mounted into the container and used as the behavior dataset.
- Product metadata is fetched from `product-service`.

## Deep sequence experiments (RNN, LSTM, BiLSTM)
Use this offline training pipeline to compare 3 architectures for next-item classification.

### Install training dependencies
```bash
pip install -r training-requirements.txt
```

### Train and evaluate
```bash
python train_sequence_models.py --data ./user_behavior.csv --output ./artifacts/sequence_models --epochs 12 --sequence-len 5
```

### Artifacts
- `artifacts/sequence_models/rnn.pt`
- `artifacts/sequence_models/lstm.pt`
- `artifacts/sequence_models/bilstm.pt`
- `artifacts/sequence_models/model_best.pt`
- `artifacts/sequence_models/metrics.json`
- `artifacts/sequence_models/comparison.csv`
- `artifacts/sequence_models/training_curves.png`
- `artifacts/sequence_models/model_comparison.png`

`model_best` is selected by ranking: `f1_macro` -> `top3_accuracy` -> `accuracy`.

## Notes
- `GET /ai/summary` includes `sequence_trained`, `sequence_rows`, and `graph_synced` so you can verify training and graph ingestion status.
