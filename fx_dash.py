import streamlit as st
from google.cloud import bigquery
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
from google.oauth2 import service_account

st.set_page_config(page_title="FX dashboard", page_icon=":bar_chart:", layout="wide")
st.title("FX dashboard")

# load data from bigquery
@st.cache_data
def load_bq_data():
    load_dotenv()
    
    # 1. Fallback authentication logic
    # Check if running in the cloud using Streamlit secrets, otherwise fallback to local configuration
    if "gcp_service_account" in st.secrets:
        # Construct authentication key mapping on the fly from Streamlit Cloud Secrets
        credentials_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        client = bigquery.Client(credentials=credentials, project=credentials_info["project_id"])
    else:
        # Fallback local environment activation route
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

# --- CALCULATE THE EUR/PEN CROSS RATE ---
# Soles per Euro = rate_pen / rate_eur
df['rate_eur_pen'] = df['rate_pen'] / df['rate_eur']


# --- INTERACTIVE CONTROLS ---

control_col1, control_col2 = st.columns(2)

with control_col1:
    time_unit = st.select_slider(
        "📅 Select Time Unit:",
        options=["Days", "Weeks", "Months", "Years"],
        value="Weeks"
    )

with control_col2:
    intervals = st.selectbox(
        "🔢 Number of Periods:",
        options=[4, 7, 12],
        index=1
    )


# --- TIME INTERPOLATION & RESAMPLING MAP ---

resample_map = {"Days": "D", "Weeks": "W", "Months": "ME", "Years": "YE"}
chosen_rule = resample_map[time_unit]

buffer_multiplier = {"Days": 1, "Weeks": 7, "Months": 31, "Years": 366}
total_lookback_days = (intervals + 1) * buffer_multiplier[time_unit]


# --- UNIFIED DATA LOGIC ---

df['rates_date'] = pd.to_datetime(df['rates_date'])
latest_date = df['rates_date'].max()

start_date = latest_date - timedelta(days=total_lookback_days)
historical_df = df[(df['rates_date'] >= start_date) & (df['rates_date'] <= latest_date)]

# Aggregate rows into the chosen bucketing timeframe rule (now includes rate_eur_pen)
aggregated_data = historical_df.resample(chosen_rule, on='rates_date').mean()

# Isolate metric card numbers
eur_avg_last_period = aggregated_data['rate_eur'].iloc[-1]
eur_avg_prev_period = aggregated_data['rate_eur'].iloc[-2]
eur_delta_value = eur_avg_last_period - eur_avg_prev_period

pen_avg_last_period = aggregated_data['rate_pen'].iloc[-1]
pen_avg_prev_period = aggregated_data['rate_pen'].iloc[-2]
pen_delta_value = pen_avg_last_period - pen_avg_prev_period

eur_pen_avg_last_period = aggregated_data['rate_eur_pen'].iloc[-1]
eur_pen_avg_prev_period = aggregated_data['rate_eur_pen'].iloc[-2]
eur_pen_delta_value = eur_pen_avg_last_period - eur_pen_avg_prev_period

# Slice dataframe down to lookback constraints for layout visualizations
sparkline_df = aggregated_data.tail(intervals).copy().reset_index()


# --- STYLE IMPLEMENTATION BLOCK ---

st.html(
    """
    <style>
    [data-testid="stMetric"] {
        text-align: left !important;
        align-items: flex-start !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #0E1117 !important;
        border: 1px solid #262730 !important;
        border-radius: 12px !important;
        padding: 20px !important;
    }
    </style>
    """
)


# --- DISPLAY TOP SCORECARDS (EXPANDED TO 3 COLUMNS) ---

left_col, middle_col, right_col = st.columns(3)

# Euro Card Box
with left_col:
    with st.container(border=True):
        st.metric(
            label=f"Euro (Avg Last {time_unit[:-1]})", 
            value=f"€{eur_avg_last_period:.4f}", 
            delta=f"{eur_delta_value:.4f}"
        )
        st.caption(f"📈 Trend over the Last {intervals} {time_unit}")
        euro_chart_data = sparkline_df[['rates_date', 'rate_eur']].rename(columns={'rate_eur': 'Euro rate'})
        st.line_chart(euro_chart_data.set_index('rates_date'), height=120)

# Peruvian Sol Card Box
with middle_col:
    with st.container(border=True):
        st.metric(
            label=f"Peruvian Sol (Avg Last {time_unit[:-1]})", 
            value=f"S/. {pen_avg_last_period:.4f}", 
            delta=f"{pen_delta_value:.4f}"
        )
        st.caption(f"📈 Trend over the Last {intervals} {time_unit}")
        pen_chart_data = sparkline_df[['rates_date', 'rate_pen']].rename(columns={'rate_pen': 'Sol rate'})
        st.line_chart(pen_chart_data.set_index('rates_date'), height=120)

# EUR/PEN Cross Rate Card Box
with right_col:
    with st.container(border=True):
        st.metric(
            label=f"EUR / PEN (Soles per Euro)", 
            value=f"{eur_pen_avg_last_period:.4f} S/.", 
            delta=f"{eur_pen_delta_value:.4f}"
        )
        st.caption(f"📈 Conversion Trend over {intervals} {time_unit}")
        cross_chart_data = sparkline_df[['rates_date', 'rate_eur_pen']].rename(columns={'rate_eur_pen': 'Conversion rate'})
        st.line_chart(cross_chart_data.set_index('rates_date'), height=120)


# --- DISPLAY VISUALIZATIONS ---

# Split into two clean layout sections or tabs if preferred
tab1, tab2 = st.tabs(["📊 Isolated EUR/PEN Conversion Analysis", "🔗 Base Currencies Correlation Chart"])

with tab1:
    st.markdown("### Soles Obtained per 1 Euro")
    
    # Calculate tight dynamic padding bounds for the direct cross-rate scale
    cross_min = float(sparkline_df['rate_eur_pen'].min() * 0.995)
    cross_max = float(sparkline_df['rate_eur_pen'].max() * 1.005)

    # Build an standalone chart for the calculated cross rate
    cross_rate_chart = (
        alt.Chart(sparkline_df)
        .mark_line(color="#10B981", strokeWidth=3, point=True) # Sleek green conversion trend line
        .encode(
            x=alt.X('rates_date:T', title="Timeline Window"),
            y=alt.Y('rate_eur_pen:Q', title="Soles per 1 Euro", scale=alt.Scale(domain=[cross_min, cross_max])),
            tooltip=[
                alt.Tooltip('rates_date:T', title='Date', format='%Y-%m-%d'),
                alt.Tooltip('rate_eur_pen:Q', title='Exchange Value', format='.4f')
            ]
        )
        .properties(height=380)
        .configure_axis(grid=True)
    )
    st.altair_chart(cross_rate_chart, use_container_width=True)

with tab2:
    # Keeps your prior dual-axis chart cleanly available on tab 2
    euro_min = float(sparkline_df['rate_eur'].min() * 0.995)
    euro_max = float(sparkline_df['rate_eur'].max() * 1.005)
    pen_min = float(sparkline_df['rate_pen'].min() * 0.995)
    pen_max = float(sparkline_df['rate_pen'].max() * 1.005)

    base_timeline = alt.Chart(sparkline_df).encode(x=alt.X('rates_date:T', title="Timeline Window"))
    euro_line = base_timeline.mark_line(color="#29B6F6", strokeWidth=3).encode(
        y=alt.Y('rate_eur:Q', title="Euro Value (Left Axis)", scale=alt.Scale(domain=[euro_min, euro_max]))
    )
    sol_line = base_timeline.mark_line(color="#FFB300", strokeWidth=3).encode(
        y=alt.Y('rate_pen:Q', title="Peruvian Sol Value (Right Axis)", scale=alt.Scale(domain=[pen_min, pen_max]))
    )
    legend_layer = base_timeline.mark_point(opacity=0).encode(
        color=alt.Color('Currency:N', title="Currencies").scale(domain=["Euro", "Peruvian Sol"], range=["#29B6F6", "#FFB300"])
    ).transform_calculate(Currency="datum.rate_eur ? 'Euro' : 'Peruvian Sol'")

    combined_macro_chart = alt.layer(euro_line, sol_line, legend_layer).resolve_scale(y='independent').properties(height=380).configure_axis(grid=True)
    st.altair_chart(combined_macro_chart, use_container_width=True)
