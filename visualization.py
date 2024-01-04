import pandas as pd
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

    # Show the plot
    plt.show()