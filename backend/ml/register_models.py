import mlflow
from mlflow.tracking import MlflowClient

mlflow.set_tracking_uri("http://localhost:5000")
client = MlflowClient()

# Get the latest run from SOC_Anomaly_Detection experiment
experiment = client.get_experiment_by_name("SOC_Anomaly_Detection")
runs = client.search_runs(
    experiment_ids=[experiment.experiment_id],
    order_by=["start_time DESC"],
    max_results=1
)
run_id = runs[0].info.run_id

# 1. Register models
if_uri = f"runs:/{run_id}/isolation_forest"
ae_uri = f"runs:/{run_id}/autoencoder"

if_mv = mlflow.register_model(if_uri, "isolation_forest")
ae_mv = mlflow.register_model(ae_uri, "autoencoder")

# 2. Transition to Production
client.transition_model_version_stage(
    name="isolation_forest",
    version=if_mv.version,
    stage="Production"
)

client.transition_model_version_stage(
    name="autoencoder",
    version=ae_mv.version,
    stage="Production"
)

print(f"Registered isolation_forest v{if_mv.version} -> Production")
print(f"Registered autoencoder v{ae_mv.version} -> Production")
