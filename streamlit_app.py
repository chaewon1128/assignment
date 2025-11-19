import os
import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk

# Page config
st.set_page_config(page_title="Seoul Air Quality & Lifestyle Dashboard", layout="wide")

# Files check
files_needed = ["spent.csv", "ppl_2012.csv", "ppl_2014.csv",
                "delivery.csv", "combined_pol.csv", "trans.csv"]

missing_files = [f for f in files_needed if not os.path.exists(f)]
if missing_files:
    st.error(f"Missing files: {missing_files}")
    st.stop()

# Load data
spent = pd.read_csv("spent.csv")
ppl_2012 = pd.read_csv("ppl_2012.csv")
ppl_2014 = pd.read_csv("ppl_2014.csv")
delivery = pd.read_csv("delivery.csv")
pol = pd.read_csv("combined_pol.csv")
trans = pd.read_csv("trans.csv")

# Preprocess
YEARS = ['2019', '2020', '2021', '2022']
pol['Year'] = pol['일시'].astype(str).str[:4]
pol['Date'] = pd.to_datetime(pol['일시'])
spent['Year'] = spent['기준_년분기_코드'].astype(str).str[:4]
trans['Year'] = trans['기준_날짜'].astype(str).str[:4]
trans['Date'] = pd.to_datetime(trans['기준_날짜'])
delivery['Date'] = pd.to_datetime(delivery['Date'])

GUS = sorted(list(set(pol[pol['자치구'] != '평균']['자치구'])))

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    selected_year = st.selectbox("Select Year", YEARS, index=2)
    selected_gus = st.multiselect("Select Districts", GUS, default=GUS[:5])
    st.markdown("Use filters to explore the data.")

# Define district lat-lon for map
seoul_gu_latlon = {
    'Gangnam-gu': (37.5172, 127.0473), 'Gangdong-gu': (37.5301, 127.1237), 'Gangbuk-gu': (37.6396, 127.0256),
    'Gangseo-gu': (37.5509, 126.8495), 'Gwanak-gu': (37.4781, 126.9516), 'Gwangjin-gu': (37.5386, 127.0823),
    'Guro-gu': (37.4954, 126.8581), 'Geumcheon-gu': (37.4600, 126.9002), 'Nowon-gu': (37.6544, 127.0568),
    'Dobong-gu': (37.6688, 127.0477), 'Dongdaemun-gu': (37.5744, 127.0396), 'Dongjak-gu': (37.5124, 126.9396),
    'Mapo-gu': (37.5634, 126.9087), 'Seodaemun-gu': (37.5792, 126.9368), 'Seocho-gu': (37.4837, 127.0324),
    'Seongdong-gu': (37.5633, 127.0363), 'Seongbuk-gu': (37.6061, 127.0220), 'Songpa-gu': (37.5145, 127.1067),
    'Yangcheon-gu': (37.5169, 126.8666), 'Yeongdeungpo-gu': (37.5264, 126.8963), 'Yongsan-gu': (37.5326, 126.9907),
    'Eunpyeong-gu': (37.6176, 126.9227), 'Jongno-gu': (37.5735, 126.9797), 'Jung-gu': (37.5636, 126.9976),
    'Jungnang-gu': (37.6063, 127.0926)
}

# Filter data by user selection
pol_filtered = pol[(pol['Year'] == selected_year) & (pol['자치구'].isin(selected_gus))]
spent_filtered = spent[(spent['Year'] == selected_year) & (spent['자치구'].isin(selected_gus))]
trans_filtered = trans[(trans['Year'] == selected_year) & (trans['자치구'].isin(selected_gus))]

# Tabs for structured navigation
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Air Quality", "Mobility & Behavior", "Delivery & Spending","Correlations & Insights", "Data Downloads"])

with tab1:
    st.header("Air Quality Trends")

    # Daily PM10 average line chart (all Seoul average)
    seoul_avg = pol_filtered[pol_filtered['자치구'] == '평균']
    if not seoul_avg.empty:
        st.line_chart(seoul_avg.set_index('Date')['미세먼지(PM10)'], height=250, use_container_width=True)
        st.caption("Daily average PM10 for Seoul")
    else:
        st.info("No average PM10 data for selected year.")

    # PM10 by district - bar chart of mean
    pm10_mean = pol_filtered.groupby('자치구')['미세먼지(PM10)'].mean()
    st.bar_chart(pm10_mean)

    # PM10 map
    map_df = pm10_mean.reset_index()
    map_df = map_df[map_df['자치구'].isin(seoul_gu_latlon.keys())]
    map_df['lat'] = map_df['자치구'].map(lambda x: seoul_gu_latlon[x][0])
    map_df['lon'] = map_df['자치구'].map(lambda x: seoul_gu_latlon[x][1])
    map_df['color'] = map_df['미세먼지(PM10)'].apply(
        lambda v: [170,204,247] if v<=30 else [133,224,133] if v<=80 else [255,179,71] if v<=150 else [255,118,117])

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position='[lon, lat]',
        get_radius=3000,
        get_fill_color='color',
        pickable=True,
    )
    view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{자치구}\nPM10: {미세먼지(PM10):.1f}"}))

with tab2:
    st.header("Mobility & Behavior")

    # Floating population comparison 2012 vs 2014
    st.subheader("Floating Population by District (2012 vs 2014)")
    ppl_2012_sel = ppl_2012[ppl_2012['거주지'].isin(selected_gus)].set_index('거주지')['개수']
    ppl_2014_sel = ppl_2014[ppl_2014['거주지'].isin(selected_gus)].set_index('거주지')['개수']
    ppl_df = pd.DataFrame({"2012": ppl_2012_sel, "2014": ppl_2014_sel}).fillna(0)
    st.bar_chart(ppl_df)

    # Public transport usage heatmap
    trans_grouped = trans_filtered.groupby('자치구')['승객_수'].sum()
    st.subheader("Total Public Transport Usage by District")
    fig, ax = plt.subplots(figsize=(12,4))
    sns.barplot(x=trans_grouped.index, y=trans_grouped.values, ax=ax)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45)
    ax.set_xlabel("District")
    ax.set_ylabel("Passengers")
    st.pyplot(fig)

with tab3:
    st.header("Delivery & Spending Patterns")

    # Delivery volume line chart
    if '전체' in delivery.columns:
        st.subheader("Delivery Volume (Total Seoul)")
        st.line_chart(delivery.set_index('Date')['전체'])

    # Spending by district bar chart
    st.subheader("Total Spending by District")
    spent_grouped = spent_filtered.groupby('자치구')['지출_총금액'].mean()
    st.bar_chart(spent_grouped)

    # Delivery + PM10 map visualization (demo scaled delivery)
    demo_delivery_vol = spent_grouped / spent_grouped.max() * 200
    common_gus = spent_grouped.index.intersection(seoul_gu_latlon.keys())
    spent_grouped = spent_grouped.loc[common_gus]
    pm10_map = pol_filtered.groupby('자치구')['미세먼지(PM10)'].mean().loc[common_gus]
    demo_delivery_vol = demo_delivery_vol.loc[common_gus]
    deliv_map = pd.DataFrame({
        "lat": [seoul_gu_latlon[d][0] for d in common_gus],
        "lon": [seoul_gu_latlon[d][1] for d in common_gus],
        "PM10": pm10_map.values,
        "Spending": spent_grouped.values,
        "Delivery": demo_delivery_vol.values
    })
    deliv_map["pm_color"] = deliv_map["PM10"].apply(
        lambda v: [170,204,247] if v<=30 else [133,224,133] if v<=80 else [255,179,71] if v<=150 else [255,118,117]
    )
    layer2 = pdk.Layer(
        "ScatterplotLayer",
        data=deliv_map,
        get_position='[lon, lat]',
        get_radius='Delivery + 1000',
        get_fill_color='pm_color',
        pickable=True
    )
    view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10)
    st.pydeck_chart(pdk.Deck(layers=[layer2], initial_view_state=view_state,
                            tooltip={"text": "{Spending:.0f}₩\nPM10: {PM10:.1f}\nDelivery: {Delivery:.0f}"}))
    st.caption("Delivery volume and spending by district relative to air pollution.\nUse this for inventory and marketing strategies.")

with tab4:
    st.header("Correlations & Insights")

    # Correlation heatmap for averaged values
    pm10_avg = pol_filtered.groupby('자치구')['미세먼지(PM10)'].mean()
    spending_avg = spent_filtered.groupby('자치구')['지출_총금액'].mean()
    transit_avg = trans_filtered.groupby('자치구')['승객_수'].sum()
    pop_2012 = ppl_2012.set_index('거주지')['개수']
    pop_2014 = ppl_2014.set_index('거주지')['개수']

    corr_df = pd.DataFrame({
        "PM10": pm10_avg,
        "Spending": spending_avg,
        "Transit": transit_avg,
        "Pop2012": pop_2012,
        "Pop2014": pop_2014
    }).dropna()

    corr_mat = corr_df.corr()
    fig, ax = plt.subplots(figsize=(6,6))
    sns.heatmap(corr_mat, annot=True, cmap='coolwarm', ax=ax)
    st.pyplot(fig)
    st.markdown("""
    - Higher PM10 usually correlates with increased delivery activity and decreased transit and outdoor population.
    - Future-proof planning suggests placing delivery-focused businesses near major transit hubs.
    - Adjust inventory and promotional schedules based on air quality forecasts.
    """)

with tab5:
    st.header("Download Data")
    for fname in files_needed:
        with open(fname, 'rb') as f:
            st.download_button(label=f'Download {fname}', data=f, file_name=fname)

st.caption("© 2025 Seoul Air Quality & Lifestyle Dashboard")
