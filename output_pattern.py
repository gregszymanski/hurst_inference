import numpy as np
import matplotlib.pyplot as plt
import random

from data_handler import DataHandler
from dates import FOMC_announcement, trading_halt
from price import Price
from volatility import VolatilityEstimator, volatility_pattern, bipower_average_V, Volatility

# Initialize the data handler
DH = DataHandler(prices_folder="~/Documents/data/SPY/price/1s/daily_csv/", 
                tmp_folder="~/Documents/data/tmp/hurst_inference")

# Remove all FOMC announcement dates from the data
for date in FOMC_announcement:
    DH.remove_date(date)

# Remove all trading halt dates from the data
for date in trading_halt:
    DH.remove_date(date)

asset = 'spy'
subsampling = 1
window = 300
truncation_method = 'STD3'
window_pattern = 20
vol_DT = None
N_examples = 2
delta = 1.0 / (252.0 * 23400) * subsampling

# Construct the volatility estimator
ve = VolatilityEstimator(delta=delta, 
                         window=window, 
                         price_truncation=truncation_method)

# Choose randomly N_examples dates in DH for the example
# Extract all dates from the price filenames in DH
# Filenames look like: asset_YYYY-MM-DD.csv
all_price_files = [f for f in DH.price_files if f.startswith(asset+'_')]
all_dates = [f.split('_')[1].replace('.csv','') for f in all_price_files]
if len(all_dates) < N_examples:
    raise ValueError("Not enough dates to choose from.")

example_dates = random.sample(all_dates, N_examples)

# For each chosen date, get price and compute volatility
# Also plot price and volatility together, highlighting truncation points
for d in example_dates:
    y, m, day = map(int, d.split('-'))
    # Get price data as a DataFrame
    price = DH.get_price(asset, y, m, day)
    price.subsample(subsampling)
    price_array = price.get_price()  # numpy array of prices

    # Before computing volatility, let's see where truncation will happen
    # To highlight truncation, we need increments before and after truncation
    # We'll replicate the steps in ve.compute to identify truncated increments
    log_price = np.log(price_array)
    increments = log_price[1:] - log_price[:-1]

    # Compute truncation threshold
    truncationValue = np.inf
    if truncation_method == 'STD3':
        truncationValue = 3 * np.std(increments)
    elif truncation_method == 'STD5':
        truncationValue = 5 * np.std(increments)
    elif truncation_method == 'BIVAR3':
        bav = bipower_average_V(log_price, window, delta)
        truncationValue = 3 * np.sqrt(bav * delta)
    elif truncation_method == 'BIVAR5':
        bav = bipower_average_V(log_price, window, delta)
        truncationValue = 5 * np.sqrt(bav * delta)

    # Identify truncation points
    truncated_points = np.abs(increments) > truncationValue

    # Compute volatility using VolatilityEstimator
    vol = ve.compute(price_array)  
    vol_DT = price.get_DT()[:len(price_array) - window]

    # Plot price and volatility
    fig, ax1 = plt.subplots()
    ax1.set_xlabel('Time Index')
    ax1.set_ylabel('Price', color='tab:blue')
    ax1.plot(price.get_DT(), price_array, color='tab:blue', label='Price')
    ax1.tick_params(axis='y', labelcolor='tab:blue')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Volatility', color='tab:red')
    ax2.plot(vol_DT, vol.get_values(), color='tab:red', label='Volatility')
    ax2.tick_params(axis='y', labelcolor='tab:red')

    # Highlight points where price truncation happened:
    # We'll mark those increments on the price subplot (ax1) or just highlight them.
    # The increments array corresponds to intervals between points, so let's 
    # highlight those times on the price chart. For simplicity, place a red dot 
    # at the points after which truncation occurred.
    truncated_indices = np.where(truncated_points)[0] + 1  # increment indexing offset
    ax1.scatter(price.df['DT'].iloc[truncated_indices], price_array[truncated_indices],
                color='red', marker='o', s=10, label='Truncated Increment')

    plt.title(f"Price and Volatility on {d}")
    plt.tight_layout()
    plt.show()


# all_vols now contains the computed volatilities for each chosen date
# Compute a "full_pattern" from all_vols. 
# Note: volatility_pattern expects Volatility objects with the same DT.
# If these are different days, they may have different lengths and DT arrays.
# For simplicity, let's assume they have the same length or that 
# we handle only those with matching lengths.


all_vols = []
for d in all_dates:
    y, m, day = map(int, d.split('-'))
    # Get price data as a DataFrame
    price = DH.get_price(asset, y, m, day)
    price.subsample(subsampling)
    price_array = price.get_price()  # numpy array of prices

    # Compute volatility using VolatilityEstimator
    vol = ve.compute(price_array)  
    all_vols.append(vol)

full_pattern = volatility_pattern(all_vols)

# Compute smaller patterns with window_pattern days at a time (rolling)
# Here we assume "days" correspond to indices in the Volatility arrays.
# We'll create patterns of length window_pattern and slide over the full pattern.


small_patterns = []
for start in range(0, len(all_vols) - window_pattern + 1, window_pattern):
    slice_vols = all_vols[start:start+window_pattern]
    small_patterns.append(volatility_pattern(slice_vols))

# Plot the full pattern
plt.figure(figsize=(10,6))

# Add in very light lines for all smaller_patterns
for sp in small_patterns:
    plt.plot(vol_DT, sp.get_values(), color='red', alpha=0.3)

plt.plot(vol_DT, full_pattern.get_values(), 'k-', color='black', linewidth=2, label='Full Pattern')

plt.title("Full Pattern with Smaller Patterns Overlaid")
plt.xlabel("Index")
plt.ylabel("Normalized Volatility")
plt.legend()
plt.tight_layout()
plt.show()
