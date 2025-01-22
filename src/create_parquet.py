import pandas as pd

# Sample data
data = {
    "name": ["John Doe", "Jane Smith", "Alice Johnson"],
    "email": ["john.doe@example.com", "jane.smith@example.com", "alice.johnson@example.com"],
    "address": ["123 Main St", "456 Elm St", "789 Oak St"],
}

# Create a DataFrame
df = pd.DataFrame(data)

# Write to Parquet
df.to_parquet("data.parquet")

print("Parquet file created: data.parquet")