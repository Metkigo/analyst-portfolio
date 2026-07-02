import pandas as pd
import numpy as np
from tqdm import tqdm

# configs
SIGNAL_FILE = 'master_signals.csv'
M15_FILE = 'asset_m15_data.csv'
M1_FILE = 'asset_m1_data.csv'
SL_MULT = 1.5
TPS = [0.5, 1.0, 2.0, 3.0, 5.0]
MAX_BARS = 60
COST = 0.4

# atr calc - standard
def get_atr(df, period=14):
    h = df['high']; l = df['low']; c = df['close']
    tr = np.maximum(h-l, np.maximum(abs(h-c.shift(1)), abs(l-c.shift(1))))
    tr.iloc[0] = h.iloc[0]-l.iloc[0]
    return tr.rolling(period).mean()

# loaders
def load_m15(p):
    df = pd.read_csv(p)
    df['time'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('time').sort_index()
    if df.index.tz is None: df.index = df.index.tz_localize('UTC')
    df['atr'] = get_atr(df)
    return df.dropna()

def load_m1(p):
    df = pd.read_csv(p)
    df['time'] = pd.to_datetime(df['timestamp'], utc=True)
    return df.set_index('time').sort_index()

def get_window(m1, t, hours=4):
    end = t + pd.Timedelta(hours=hours)
    s = m1.index.get_indexer([t], method='bfill')[0]
    e = m1.index.get_indexer([end], method='ffill')[0]
    if s == -1 or e == -1 or s > e: return pd.DataFrame()
    return m1.iloc[s:e+1]

# main sweep
print("loading data...")
m15 = load_m15(M15_FILE)
m1 = load_m1(M1_FILE)
print(f"m15: {len(m15)}, m1: {len(m1)}")

master = pd.read_csv(SIGNAL_FILE)
master['entry_time'] = pd.to_datetime(master['entry_time'])

# filter out weekends and late nights (standard practice)
master['hour'] = master['entry_time'].dt.hour
master['dow'] = master['entry_time'].dt.day_name()
master = master[(~master['dow'].isin(['Monday','Sunday'])) & (master['hour'].between(5,20))]
master = master.dropna(subset=['entry_price'])
print(f"signals left: {len(master)}")

# pre-index for speed
master['idx'] = m15.index.get_indexer(master['entry_time'], method='nearest')
master = master[master['idx'] != -1].reset_index(drop=True)

print("running sweep...")
print("tp  count  win%  avgR  pf")

best_avg = -999
best_tp = None

for tp in TPS:
    tp_hits = sl_hits = tos = wins = total = 0
    sum_r = 0.0
    
    for _, row in tqdm(master.iterrows(), total=len(master)):
        try:
            entry = float(row['entry_price'])
            dir = str(row['direction']).strip().lower()
            et = row['entry_time']
            atr = float(m15['atr'].iloc[int(row['idx'])])
            if pd.isna(atr): continue
            
            w = get_window(m1, et)
            if len(w) < 5: continue
            
            sl = entry - SL_MULT*atr if dir=='buy' else entry + SL_MULT*atr
            tp_pr = entry + tp*atr if dir=='buy' else entry - tp*atr
            total += 1
            out = None
            
            for j, (_, bar) in enumerate(w.iterrows()):
                if j >= MAX_BARS: break
                if dir == 'buy':
                    if bar['low'] <= sl: out = -SL_MULT; sl_hits += 1; break
                    if bar['high'] >= tp_pr: out = tp; tp_hits += 1; break
                else:
                    if bar['high'] >= sl: out = -SL_MULT; sl_hits += 1; break
                    if bar['low'] <= tp_pr: out = tp; tp_hits += 1; break
            
            if out is None:
                last_close = w.iloc[min(MAX_BARS-1, len(w)-1)]['close']
                out = (last_close-entry)/atr if dir=='buy' else (entry-last_close)/atr
                out = max(-SL_MULT, out)
                tos += 1
            
            r_net = out - COST
            sum_r += r_net
            if r_net > 0: wins += 1
        except:
            pass
    
    if total > 0:
        wr = wins/total*100
        avg = sum_r/total
        pf = (tp_hits*(tp-COST)) / (sl_hits*(SL_MULT+COST)) if sl_hits > 0 else float('inf')
        star = ' *' if avg > best_avg and avg > 0 else ''
        if avg > best_avg and avg > 0:
            best_avg = avg; best_tp = tp
        print(f"{tp}  {total}  {wr:.1f}%  {avg:.3f}  {pf:.2f}{star}")
    else:
        print(f"{tp}  --- no trades")

if best_tp:
    print(f"\nbest tp: {best_tp}")