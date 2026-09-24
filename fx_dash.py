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

    # 1. Format the sparkline data
    sparkline_data = last_week_df.reset_index()

    # 2. Configure your custom Min and Max bounds
    y_min = float(sparkline_data['rate_eur'].min() * 0.995)
    y_max = float(sparkline_data['rate_eur'].max() * 1.005)

    # 3. Base configuration shared by the line and the text
    base = alt.Chart(sparkline_data).encode(
        x=alt.X('rates_date:T', axis=None),
        y=alt.Y('rate_eur:Q', title=None, scale=alt.Scale(domain=[y_min, y_max], clamp=True))
    )

    # 4. Create the line
    line = base.mark_line(color="#29B6F6", strokeWidth=2)

    # 5. 🔥 Create the value text labels (placed slightly above the points)
    text_labels = base.mark_text(
        align='center',
        baseline='bottom',
        dy=-6,                  # Shifts the text up by 6 pixels so it sits on top of the line
        fontSize=11,
        color="#FFFFFF"         # Adjust text color to match your theme
    ).encode(
        text=alt.Text('rate_eur:Q', format='.4f') # Formats to 4 decimal places
    )

    # 6. Layer them together and style as a sparkline
    sparkline = (
        (line + text_labels)
        .properties(height=180) # Slightly increased height to allow room for text
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False)
    )

    st.caption("📈 7-Day Trend with Values")
    st.altair_chart(sparkline, use_container_width=True)