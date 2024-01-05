import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


def plot_simple_risk(data):
    # Create a new figure and a twin Axes sharing the xaxis
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Plot the Price and SMAs on the left y-axis
    ax1.plot(data.index, data['Price'], label='Daily Price', alpha=0.7, linewidth=2)
    ax1.plot(data.index, data['Daily_SMA'], label='50-day SMA', color='orange')
    ax1.plot(data.index, data['Weekly_SMA'], label='50-week SMA', color='green')

    # Set the y-axis label, the title and the legend
    ax1.set_yscale('log')
    ax1.set_ylabel('Price (Log Scale)', fontsize=14)
    ax1.set_title('Bitcoin Price, SMAs and Risk Levels', fontsize=16)
    ax1.legend(loc='upper left')

    # Create the second y-axis for the risk levels
    ax2 = ax1.twinx()
    ax2.plot(data.index, data['risk levels'], label='Risk Levels', color='red', alpha=0.7)
    ax2.set_ylabel('Risk Levels', fontsize=14, color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    ax2.legend(loc='upper right')

    # Set the x-axis label and grid
    ax1.set_xlabel('Date', fontsize=14)
    ax1.grid(True)

    # Save the plot to a file
    plt.savefig('viz/bitcoin_simple_risk.png')

    # Show the plot
    plt.show()

def plot_log_fit(data):
    fig, ax = plt.subplots(figsize=(14, 7))

    # Plot the actual prices
    ax.plot(data.index, data['Price'], label='Actual Price', color='blue', alpha=0.7)

    # Plot the model prices from the logarithmic fit
    ax.plot(data.index, data['Model_Price'], label='Logarithmic Fit', color='red', linestyle='-')

    ax.set_yscale('log')  # Log scale for y-axis
    ax.set_xlabel('Date', fontsize=14)
    ax.set_ylabel('Price (Log Scale)', fontsize=14)
    ax.set_title('Bitcoin Price and Logarithmic Fit', fontsize=16)
    ax.legend()
    ax.grid(True)

    plt.show()

def plot_overvaluation(data):
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Plot the price on the left y-axis with a logarithmic scale
    color = 'tab:blue'
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Price', color=color)
    ax1.plot(data.index, data['Price'], label='Price', color=color)
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_yscale('log')
    ax1.grid(True)

    # Create a twin Axes sharing the same x-axis for log overvaluation
    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Log Overvaluation', color=color)

    # Calculate the log overvaluation, handling negative and zero values appropriately
    log_overvaluation = np.log(data['Overvaluation'].replace(0, np.nan))
    ax2.plot(data.index, log_overvaluation, label='Log Overvaluation', color=color)
    ax2.tick_params(axis='y', labelcolor=color)

    # Add the zero line (which is now log(1) = 0) at y=0
    ax2.axhline(0, color='grey', linewidth=0.8, linestyle='--')

    # Set titles and legends
    ax1.set_title('Price and Log Overvaluation Metric')
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')

    # Save the plot to a file in the viz directory
    plt.savefig('viz/price_with_log_overvaluation.png')

    plt.show()

