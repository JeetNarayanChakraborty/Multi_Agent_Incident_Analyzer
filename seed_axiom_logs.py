import os
import random
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

axiom_token = os.getenv("AXIOM_API_TOKEN")
axiom_dataset = os.getenv("AXIOM_DATASET")

if not axiom_token or not axiom_dataset:
    raise ValueError(
        "AXIOM_API_TOKEN or AXIOM_DATASET is not set in environment variables."
    )

headers = {"Authorization": f"Bearer {axiom_token}", "Content-Type": "application/json"}

now = datetime.now(timezone.utc)
events = []

# 1. Generate 30 Normal INFO Logs (Background Traffic)
for i in range(30):
    t = (now - timedelta(minutes=random.randint(1, 14))).isoformat()
    events.append(
        {
            "_time": t,
            "service": "order-service",
            "level": "INFO",
            "message": f"Processed order fulfillment request #{random.randint(1000, 9999)} successfully.",
        }
    )

# 2. Generate 10 WARN Logs (Latency Warnings)
for i in range(10):
    t = (now - timedelta(minutes=random.randint(1, 10))).isoformat()
    events.append(
        {
            "_time": t,
            "service": "order-service",
            "level": "WARN",
            "message": "HikariPool-1 - Connection acquisition time exceeded 1500ms threshold.",
        }
    )

# 3. Generate 60 ERROR Logs (Connection Pool / Lock Spike)
error_types = [
    "org.postgresql.util.PSQLException: ERROR: canceling statement due to statement timeout",
    "com.zaxxer.hikari.pool.HikariPool$PoolInitializationException: Failed to initialize pool within timeout",
    "org.springframework.dao.CannotAcquireLockException: could not execute statement; SQL [n/a]; nested exception is org.hibernate.exception.LockAcquisitionException",
    "org.hibernate.exception.JDBCConnectionException: Unable to acquire JDBC Connection from Hikari DataSource",
]

for i in range(60):
    t = (now - timedelta(minutes=random.randint(1, 8))).isoformat()
    events.append(
        {
            "_time": t,
            "service": "order-service",
            "level": "ERROR",
            "message": random.choice(error_types),
        }
    )

# Ingest batch of 100 logs into Axiom
url = f"https://api.axiom.co/v1/datasets/{axiom_dataset}/ingest"
response = requests.post(url, headers=headers, json=events)
response.raise_for_status()

print(
    f"Successfully ingested {len(events)} telemetry logs into Axiom dataset '{axiom_dataset}'."
)
