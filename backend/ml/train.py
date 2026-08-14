import argparse
import os
import pickle
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
import numpy as np

from .autoencoder import Autoencoder


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame()
    features['event_count_1m'] = df.get(' Total Fwd Packets', 0).astype(float)
    features['event_count_5m'] = features['event_count_1m'] * 5
    features['event_count_1h'] = features['event_count_1m'] * 60
    features['failed_auth_ratio'] = 0.0
    features['distinct_dest_ports'] = df.get(' Destination Port', 0).astype(float)
    features['dest_ip_fanout'] = 0.0
    features['bytes_transferred'] = df.get(' Flow Bytes/s', 0).replace([np.inf, -np.inf], 0).fillna(0).astype(float)
    features['tod_zscore'] = 0.0
    features['geo_velocity_kmh'] = 0.0
    features = features.replace([np.inf, -np.inf], np.nan).fillna(0)
    for col in features.columns:
        max_val = features[col].max()
        if max_val > 0:
            features[col] = features[col] / max_val
    return features


def train_isolation_forest(X_train: pd.DataFrame):
    model = IsolationForest(n_estimators=200, contamination=0.01, random_state=42)
    model.fit(X_train)
    return model


def train_autoencoder(X_train: pd.DataFrame):
    input_dim = X_train.shape[1]
    model = Autoencoder(input_dim)
    X_train_tensor = torch.tensor(X_train.values, dtype=torch.float32)
    dataset = TensorDataset(X_train_tensor, X_train_tensor)
    dataloader = DataLoader(dataset, batch_size=256, shuffle=True)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    model.train()
    for epoch in range(5):
        total_loss = 0
        for batch_x, _ in dataloader:
            optimizer.zero_grad()
            reconstructed = model(batch_x)
            loss = criterion(reconstructed, batch_x)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
    return model


def train_models(data_dir: str = "./data/cicids2017", output_dir: str = None):
    from ..config import MODEL_DIR
    if output_dir is None:
        output_dir = str(MODEL_DIR)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("[*] Loading CICIDS2017 data...")
    train_path = Path(data_dir) / "Wednesday-workingHours.pcap_IANA_labels.csv"
    test_path = Path(data_dir) / "Friday-WorkingHours-Afternoon-DDos.pcap_IANA_labels.csv"

    try:
        df_train = pd.read_csv(train_path).sample(n=10000, random_state=42)
        df_test = pd.read_csv(test_path).sample(n=10000, random_state=42)
    except (FileNotFoundError, OSError) as e:
        print(f"Data files not found ({e}). Creating dummy models for testing.")
        df_train = pd.DataFrame({' Total Fwd Packets': np.random.randint(1, 10, 1000),
                                  ' Destination Port': 80,
                                  ' Flow Bytes/s': 100,
                                  ' Label': 'BENIGN'})
        df_test_benign = pd.DataFrame({' Total Fwd Packets': np.random.randint(1, 10, 500),
                                        ' Destination Port': 80,
                                        ' Flow Bytes/s': 100,
                                        ' Label': 'BENIGN'})
        df_test_attack = pd.DataFrame({' Total Fwd Packets': np.random.randint(100, 1000, 500),
                                        ' Destination Port': 8080,
                                        ' Flow Bytes/s': 10000,
                                        ' Label': 'DDoS'})
        df_test = pd.concat([df_test_benign, df_test_attack])

    df_train_benign = df_train[df_train[' Label'] == 'BENIGN']
    if len(df_train_benign) == 0:
        df_train_benign = df_train

    X_train = extract_features(df_train_benign)
    X_test = extract_features(df_test)
    y_test = (df_test[' Label'] != 'BENIGN').astype(int)

    print(f"Training data shape: {X_train.shape}")
    print(f"Testing data shape: {X_test.shape} (Anomalies: {y_test.sum()})")

    print("\n[*] Training Isolation Forest...")
    if_model = train_isolation_forest(X_train)
    with open(out / "isolation_forest.pkl", "wb") as f:
        pickle.dump(if_model, f)
    print(f"    -> saved {out}/isolation_forest.pkl")

    print("\n[*] Training Autoencoder...")
    ae_model = train_autoencoder(X_train)
    torch.save(ae_model.state_dict(), out / "autoencoder.pt")
    print(f"    -> saved {out}/autoencoder.pt")

    try:
        y_pred_if = (if_model.predict(X_test) == -1).astype(int)
        precision = precision_score(y_test, y_pred_if, zero_division=0)
        recall = recall_score(y_test, y_pred_if, zero_division=0)
        f1 = f1_score(y_test, y_pred_if, zero_division=0)
        print(f"\nIF sanity check -> Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}")
    except Exception as exc:
        print(f"Evaluation skipped: {exc}")

    print("\n[+] Training complete.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, default="./data/cicids2017")
    parser.add_argument("--model-dir", type=str, default=None)
    args = parser.parse_args()
    train_models(data_dir=args.data_dir, output_dir=args.model_dir)


if __name__ == "__main__":
    main()

