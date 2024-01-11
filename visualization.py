import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.graph_objs as go

from plotly.subplots import make_subplots
from matplotlib.colors import LinearSegmentedColormap



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
    ax2.plot(data.index, data['simple_risk'], label='Risk Levels', color='red', alpha=0.7)
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

def plot_risk_and_price(data):
    # Create a new figure and a twin Axes sharing the xaxis
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Plot the Price and SMAs on the left y-axis
    ax1.plot(data.index, data['Price'], label='Daily Price', alpha=0.7, linewidth=2)

    # Set the y-axis label, the title and the legend
    ax1.set_yscale('log')
    ax1.set_ylabel('Price (Log Scale)', fontsize=14)
    ax1.set_title('Bitcoin Price, and Risk Levels', fontsize=16)
    ax1.legend(loc='upper left')

    # Create the second y-axis for the risk levels
    ax2 = ax1.twinx()
    ax2.plot(data.index, data['risk_levels'], label='Risk Levels', color='red', alpha=0.7)
    ax2.set_ylabel('Risk Levels', fontsize=14, color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    ax2.legend(loc='upper right')

    # Set the x-axis label and grid
    ax1.set_xlabel('Date', fontsize=14)
    ax1.grid(True)

    # Annotate the latest risk score on the plot outside the graph
    latest_risk = data['risk_levels'].iloc[-1]
    textstr = f'Latest Risk Score: {latest_risk:.2f}'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax1.text(0.01, 1.05, textstr, transform=ax1.transAxes, fontsize=14,
             verticalalignment='top', bbox=props)

    # Save the plot to a file
    plt.savefig('viz/bitcoin_risk_sma.png')

    # Show the plot
    plt.show()


def plot_risk_color_coded(data):
    # Assuming 'Date' is already the index and is a datetime object
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Create custom color map
    colors = ["darkblue", "blue", "lightblue", "lightgreen", "yellow", "orange", "red", "darkred"]
    cmap = LinearSegmentedColormap.from_list('risk_cmap', colors, N=256)

    # Normalize risk levels for colormap
    norm = plt.Normalize(data['risk_levels'].min(), data['risk_levels'].max())

    # Scatter plot for color-coded risk levels
    points = ax1.scatter(data.index, data['Price'], c=data['risk_levels'], cmap=cmap, norm=norm, s=25, alpha=0.7, edgecolors='none')

    # Color bar for risk levels
    cbar = plt.colorbar(points, ax=ax1)
    cbar.set_label('Risk Levels')

    # Set y-scale to logarithmic
    ax1.set_yscale('log')
    ax1.set_ylabel('Price (Log Scale)', fontsize=14)
    ax1.set_title('Bitcoin Price Color-Coded by Risk Levels', fontsize=16)

    ax1.set_xlabel('Date', fontsize=14)
    ax1.grid(True)

    # Annotate the latest risk score on the plot
    latest_risk = data['risk_levels'].iloc[-1]
    ax1.annotate(f'Latest Risk Score: {latest_risk:.2f}',
                 xy=(1, 0), xycoords='axes fraction',
                 xytext=(-10, 10), textcoords='offset points',
                 horizontalalignment='right',
                 verticalalignment='bottom',
                 fontsize=12)

    plt.savefig('viz/bitcoin_risk_color_coded.png')
    plt.show()

def interactive_color_coded_risk(data):
    # Create a figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add the Bitcoin price line
    fig.add_trace(
        go.Scatter(x=data.index, y=data['Price'], name='BTC Price', line=dict(color='darkgrey'), showlegend=False),
        secondary_y=False,
    )

    # Create traces for the risk levels based on thresholds
    thresholds = [(i/10.0, (i+1)/10.0) for i in range(10)]  # Create thresholds
    colors = ["indigo", "darkblue", "blue", "lightblue", "lightgreen", "yellow", "orange", "salmon", "red", "darkred"]

    for i, (low, high) in enumerate(thresholds):
        mask = (data['risk_levels'] >= low) & (data['risk_levels'] < high)
        fig.add_trace(
            go.Scatter(
                x=data.index[mask],
                y=data['Price'][mask],
                mode='markers',
                marker=dict(size=6, color=colors[i % len(colors)]),
                name=f'Risk: {low:.1f}-{high:.1f}'
            ),
            secondary_y=False,
        )

    # Set x-axis title
    fig.update_xaxes(title_text="Date")

    # Set y-axes titles
    fig.update_yaxes(title_text="BTC Price", secondary_y=False)

    # Set y-axis to logarithmic scale
    fig.update_yaxes(type="log", secondary_y=False)

    # Set layout for the figure
    fig.update_layout(
        title_text="Interactive Color-Coded Bitcoin Risk Levels",
        hovermode="x",
        template="plotly_dark"
    )

    # Show the figure
    fig.show()