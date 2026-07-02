import pandas as pd
import numpy as np

file = 'sample_raw_data.csv'

# checking the raw structure first
with open(file, 'r') as f:
    for i in range(5):
        print(f.readline().strip())

# read it in, force everything to string to avoid parsing errors
df = pd.read_csv(
    file,
    header=None,
    names=['ts','open','high','low','close'],
    dtype=str
).dropna(how='any')

print(f"rows after drop: {len(df)}")
if len(df) == 0:
    raise ValueError("empty file, check the raw print above")

# convert timestamp - handles both ms and ns depending on the feed
df['ts'] = pd.to_numeric(df['ts'], errors='coerce')
if (df['ts'] > 1e15).any():
    df['ts'] = pd.to_datetime(df['ts'], unit='ns', utc=True)
else:
    df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)

# convert price cols
for c in ['open','high','low','close']:
    df[c] = pd.to_numeric(df[c], errors='coerce')

df = df.dropna().set_index('ts').sort_index()

# quick sanity check
print(f"clean rows: {len(df):,}")
print(f"date range: {df.index[0]} -> {df.index[-1]}")
print(f"dupes: {df.index.duplicated().sum()}")
print(f"high<low errors: {(df['high'] < df['low']).sum()}")

print(df.head(3))