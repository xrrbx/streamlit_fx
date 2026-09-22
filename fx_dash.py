import streamlit as st
from google.cloud import bigquery
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta
import altair as alt

st. set_page_config(page_title="FX dashboard", page_icon=":bar_chart:", layout="wide")
st.title("FX dashboard")

# load data from bigquery
@st.cache_data
def load_bq_data():
    load_dotenv()
    client = bigquery.Client()
    query = """
        select 
        rates_date,
        rate_eur,
        rate_pen
        from `exchange-rate-502712.exchange_rates_dev.fx_rates`
    """
    return client.query(query).to_dataframe()

df = load_bq_data()

# --- METRIC CALCULATION LOGIC ---

# 1. Ensure rates_date is treated as a datetime object
df['rates_date'] = pd.to_datetime(df['rates_date'])

# 2. Get the latest date present in your data to anchor "last week"
# (Using df['rates_date'].max() prevents issues if the database hasn't updated today yet)
latest_date = df['rates_date'].max()

# 3. Define the date boundaries for the two windows (trailing 7-day periods)
last_week_start = latest_date - timedelta(days=6)
prev_week_start = latest_date - timedelta(days=13)

# 4. Filter the dataframe and calculate the averages
last_week_df = df[(df['rates_date'] >= last_week_start) & (df['rates_date'] <= latest_date)]
prev_week_df = df[(df['rates_date'] >= prev_week_start) & (df['rates_date'] < last_week_start)]

# Calculate average Euro rates (change 'rate_eur' to 'rate_pen' if displaying PEN)
avg_last_week = last_week_df['rate_eur'].mean()
avg_prev_week = prev_week_df['rate_eur'].mean()

# 5. Calculate the delta (the absolute or relative difference)
delta_value = avg_last_week - avg_prev_week


# --- DISPLAY IN STREAMLIT ---

# Display each currency's data in separate columns
left_col, middle_col, right_col = st.columns(3)

# Dollars / Euro in the left column
with left_col:
    st.metric(label="Euro", value=f"€{avg_last_week:.4f}", delta=f"{delta_value:.4f}")
    
    # Isolate last week's raw trend line directly under the metric card

    # 1. Clean up data format for the chart
    trend_data = last_week_df.reset_index()

    # 2. Create the interactive line chart
    chart = (
    alt.Chart(trend_data)
    # 🔥 point=True explicitly adds visible dots right onto the line
    .mark_line(
        color="#29B6F6", 
        strokeWidth=2,
        point={"size": 70, "filled": True, "fill": "#1565C0"} 
    )
    .encode(
        x=alt.X('rates_date:T', title="Date"),
        y=alt.Y(
            'rate_eur:Q', 
            title="Euro Rate",
            scale=alt.Scale(zero=False) # Zooms in on your data range
        ),
        # This adds interactive popups when hovering over the dots
        tooltip=[
            alt.Tooltip('rates_date:T', title='Date', format='%Y-%m-%d'),
            alt.Tooltip('rate_eur:Q', title='Rate', format='.4f')
        ]
    )
    # 🔥 Increased height to make the graph taller and take up more space
    .properties(height=280) 
    )

# 3. Render it inside your column layout
    st.caption("📈 7-Day Trend (Detailed View)")
    st.altair_chart(chart, use_container_width=True)