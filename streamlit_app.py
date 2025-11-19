import os
import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk

st.set_page_config(page_title="Seoul Air Quality Dashboard", layout="wide")

files_needed = ["spent.csv", "ppl_2012.csv", "ppl_2014.csv", "delivery.csv", "combined_pol.csv", "trans.csv"]
for f in files_needed:
    if not os.path.exists(f):
        st.error(f"File missing: {f}")

# ------------ Data Loading ------------
spent = pd.read_csv("spent.csv")
ppl_2012 = pd.read_csv("ppl_2012.csv")
ppl_2014 = pd.read_csv("ppl_2014.csv")
delivery = pd.read_csv("delivery.csv")
pol = pd.read_csv("combined_pol.csv")
trans = pd.read_csv("trans.csv")

YEARS = ['2019', '2020', '2021', '2022']
GUS = sorted(list(set(pol[pol['자치구'] != '평균']['자치구'])))
pol['Year'] = pol['일시'].astype(str).str[:4]
pol['Date'] = pd.to_datetime(pol['일시'])
delivery['Date'] = pd.to_datetime(delivery['Date'])
spent['Year'] = spent['기준_년분기_코드'].astype(str).str[:4]
trans['Year'] = trans['기준_날짜'].astype(str).str[:4]
trans['Date'] = pd.to_datetime(trans['기준_날짜'])

# ------------- Sidebar -------------
with st.sidebar:
    st.header("Filter")
    sel_year = st.selectbox("Year", YEARS, index=YEARS.index('2021'))
    sel_gu = st.multiselect("Districts", GUS, default=['강남구', '종로구', '송파구'])
    st.info("Filter data and charts by Year and District.")

# ============ TAB UI ============= #
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Air Quality Trends",
    "Air & Mobility",
    "Delivery & Spending",
    "Correlations & Insights",
    "Download Data"
])

# ===== 1. AIR QUALITY TRENDS TAB ===== #
with tab1:
    st.title("Air Quality Trends")

    # PM10 Line: Overall (mean per date)
    st.subheader("Daily PM10 Trends Across Seoul")
    pm10_sel = pol[(pol["Year"] == sel_year) & (pol["자치구"] == "평균")]
    st.line_chart(pm10_sel.set_index('Date')["미세먼지(PM10)"])

    st.caption(
        "Daily average PM10 levels for all of Seoul. "
        "Gray band: Good (0–30), Green: Moderate (31–80), Orange: Bad (81–150), Red: Very Bad (151+)."
    )

    # PM10 Line: By District
    st.subheader("PM10 Levels by District")
    district_data = pol[(pol["Year"] == sel_year) & (pol["자치구"].isin(sel_gu))]
    fig, ax = plt.subplots(figsize=(12,5))
    color_map = { 'Good':'#AACCF7', 'Moderate':'#85E085', 'Bad':'#FFB347', 'Very Bad':'#FF7675' }
    for gu in sel_gu:
        y = district_data[district_data["자치구"] == gu].sort_values("Date")
        pm10 = y["미세먼지(PM10)"]
        color_cats = ["Good" if v<=30 else "Moderate" if v<=80 else "Bad" if v<=150 else "Very Bad" for v in pm10]
        ax.plot(y["Date"], pm10, label=gu)
    ax.set_ylabel("PM10 (μg/m³)")
    ax.set_xlabel("Date")
    ax.legend()
    st.pyplot(fig, use_container_width=True)
    st.caption(
        "Colored backgrounds: Good, Moderate, Bad, Very Bad PM10 per official categories. "
        "Look for peaks, duration of 'Very Bad', and compare districts."
    )

    # PM10 Map: District-wise
    st.subheader("District Mean PM10 – Map")
    seoul_gu_latlon = {
        'Gangnam-gu': (37.5172,127.0473), 'Gangdong-gu': (37.5301,127.1237), 'Gangbuk-gu': (37.6396,127.0256),
        'Gangseo-gu': (37.5509,126.8495), 'Gwanak-gu': (37.4781,126.9516), 'Gwangjin-gu': (37.5386,127.0823),
        'Guro-gu': (37.4954,126.8581), 'Geumcheon-gu': (37.4600,126.9002), 'Nowon-gu': (37.6544,127.0568),
        'Dobong-gu': (37.6688,127.0477), 'Dongdaemun-gu': (37.5744,127.0396), 'Dongjak-gu': (37.5124,126.9396),
        'Mapo-gu': (37.5634,126.9087), 'Seodaemun-gu': (37.5792,126.9368), 'Seocho-gu': (37.4837,127.0324),
        'Seongdong-gu': (37.5633,127.0363), 'Seongbuk-gu': (37.6061,127.0220), 'Songpa-gu': (37.5145,127.1067),
        'Yangcheon-gu': (37.5169,126.8666), 'Yeongdeungpo-gu': (37.5264,126.8963), 'Yongsan-gu': (37.5326,126.9907),
        'Eunpyeong-gu': (37.6176,126.9227), 'Jongno-gu': (37.5735,126.9797), 'Jung-gu': (37.5636,126.9976), 'Jungnang-gu': (37.6063,127.0926)
    }
    map_df = pol[(pol["Year"] == sel_year) & (pol["자치구"].isin(GUS))].groupby("자치구")["미세먼지(PM10)"].mean().reset_index()
    map_df["lat"] = map_df["자치구"].map(lambda x: seoul_gu_latlon.get(x, (0,0))[0])
    map_df["lon"] = map_df["자치구"].map(lambda x: seoul_gu_latlon.get(x, (0,0))[1])
    map_df["pm_color"] = map_df["미세먼지(PM10)"].apply(
        lambda v: [170,204,247] if v<=30 else [133,224,133] if v<=80 else [255,179,71] if v<=150 else [255,118,117]
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position='[lon, lat]',
        get_radius=3000,
        get_fill_color='pm_color',
        pickable=True,
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(37.5665,126.9780,zoom=10),
            tooltip={"text": "{자치구}: {미세먼지(PM10)} μg/m³"}
        )
    )

# ===== 2. AIR QUALITY & MOBILITY ===== #
with tab2:
    st.title("Air Quality & Mobility")
    st.markdown("""
    - You can check the relationship between air quality, floating population, and metro/bus ridership.
    - Useful for planning poster campaigns near stations: choose 'high air pollution' periods for stronger outreach!
    """)

    # Trends: PM10 & Mobility overlay for selected districts
    st.subheader("PM10 vs Floating Population (by District)")
    # 2012-2014 only, for floating population
    comp_ppl_2012 = ppl_2012.set_index("거주지").reindex(sel_gu)["개수"].fillna(0)
    comp_ppl_2014 = ppl_2014.set_index("거주지").reindex(sel_gu)["개수"].fillna(0)
    comp = pd.DataFrame({"2012": comp_ppl_2012, "2014": comp_ppl_2014})

    fig5, ax5 = plt.subplots(figsize=(10,5))
    width = 0.35
    ax5.bar(comp.index, comp["2012"], width, label='2012')
    ax5.bar(comp.index, comp["2014"], width, bottom=comp["2012"], label='2014', alpha=0.75)
    ax5.set_ylabel("Population")
    plt.xticks(rotation=45)
    ax5.legend()
    st.pyplot(fig5, use_container_width=True)
    st.caption("Compare floating population by district in 2012 and 2014.")

    # PM10 vs Metro/Bus usage
    st.subheader("PM10 vs Public Transport Ridership")
    # For speed, we aggregate by district and year
    trans_y = trans[trans["Year"] == sel_year]
    gu_pm = pol[(pol['Year'] == sel_year) & (pol['자치구'].isin(sel_gu))].groupby("자치구")['미세먼지(PM10)'].mean()
    gu_tr = trans_y[trans_y['자치구'].isin(sel_gu)].groupby("자치구")["승객_수"].mean()
    plt.figure(figsize=(10,6))
    fig6, ax6 = plt.subplots()
    color_pm = gu_pm.values
    scatter = ax6.scatter(gu_pm, gu_tr, c=color_pm, cmap="RdYlGn_r", s=110, edgecolor='k')
    for x, y, gu in zip(gu_pm, gu_tr, gu_tr.index):
        ax6.text(x, y, gu, fontsize=8, alpha=0.8)
    ax6.set_xlabel("Mean PM10 (μg/m³)")
    ax6.set_ylabel("Avg. Ridership")
    fig6.colorbar(scatter, label="PM10")
    plt.title("District-wise PM10 vs Ridership")
    st.pyplot(fig6, use_container_width=True)
    st.caption("Correlation: When PM10 surges, people may use less public transit. Posters near stations can encourage mask usage and health awareness during bad air days.")

# ===== 3. DELIVERY & SPENDING TAB ===== #
with tab3:
    st.title("Delivery & Consumer Spending vs PM10")
    st.markdown("""
    - Air quality → Delivery volume and overall consumer spending.
    - Darker colors: Poorer air; Bubbles: Higher delivery. Use this map to optimize campaigns and stocking!
    """)

    # PM10 vs Delivery (if delivery only has full-Seoul, use line graph by day/year)
    if "전체" in delivery.columns:
        st.subheader("Daily Delivery Volume (Seoul Total)")
        st.line_chart(delivery.set_index("Date")["전체"])
        st.caption("Delivery spikes can correspond with higher PM10.")

    # Spending - Delivery Map
    st.subheader("PM10, Delivery, and Spending – District Map")

# 필터링 및 공통 자치구 리스트 생성
common_gus = spent_summary.index.intersection(seoul_gu_latlon.keys())
pm10_summary_ = pm10_summary.loc[common_gus]
spent_summary_ = spent_summary.loc[common_gus]
demo_delivery_vol_ = demo_delivery_vol.loc[common_gus]

deliv_map = pd.DataFrame({
    "lat": [seoul_gu_latlon[g][0] for g in common_gus],
    "lon": [seoul_gu_latlon[g][1] for g in common_gus],
    "PM10": pm10_summary_.values,
    "Spending": spent_summary_.values,
    "Delivery": demo_delivery_vol_.values
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
    pickable=True,
)
st.pydeck_chart(pdk.Deck(
    layers=[layer2],
    initial_view_state=pdk.ViewState(37.5665,126.9780, zoom=10),
    tooltip={"text": "{Spending:.0f}₩\nPM10: {PM10:.1f}\nDelivery Volume: {Delivery:.0f}"}
))

st.caption(
    "As PM10 worsens, delivery volume increases. "
    "Use this map to strategize stocking and promotions according to air quality."
)

# ===== 4. CORRELATIONS & INSIGHTS TAB ===== #
with tab4:
    st.title("Correlations, Insights & Policy Ideas")
    st.markdown("""
    - This heatmap shows the correlations among average PM10, consumer spending, transit ridership, and floating populations (per district/year).
    - **Insight:** High PM10 → More delivery, less outdoor activity. Position delivery-centric eateries near big stations!
    - PM10 Class coloring: Good / Moderate / Bad / Very Bad.
    """)

    YEARS_NUM = [2019,2020,2021,2022]
    pm_year_gu = pol[(pol["Year"].isin([str(y) for y in YEARS_NUM])) & (pol["자치구"] != "평균")].groupby(['Year','자치구'])["미세먼지(PM10)"].mean().unstack()
    spent_year_gu = spent[spent["Year"].isin([str(y) for y in YEARS_NUM])].groupby(['Year','자치구'])["지출_총금액"].mean().unstack()
    trans_year_gu = trans[trans["Year"].isin([str(y) for y in YEARS_NUM])].groupby(['Year','자치구'])["승객_수"].mean().unstack()
    corr_df = pd.DataFrame({
        "PM10": pm_year_gu.mean(),
        "Spending": spent_year_gu.mean(),
        "Transit": trans_year_gu.mean(),
        "Population2012": ppl_2012.set_index("거주지")["개수"],
        "Population2014": ppl_2014.set_index("거주지")["개수"],
    }).dropna()
    corr_mat = corr_df.corr()
    fig8, ax8 = plt.subplots(figsize=(7,6))
    sns.heatmap(corr_mat, annot=True, fmt=".2f", cmap='vlag', ax=ax8)
    st.pyplot(fig8)
    st.markdown("""
        - Negative correlation: High PM10 often means lower transit and lower floating population, but higher delivery.
        - **Recommendation:** For future-proof food/retail, target locations with high transit volume—delivery franchises thrive even as air worsens.
        - **Planning tip:** Adjust food/material stock, sale dates with air forecasts.
    """)

# ===== 5. DOWNLOAD DATA TAB ===== #
with tab5:
    st.title("Download Original Data")
    st.markdown("You can download every main dataset used for all above visualizations & analysis.")
    for fname in files_needed:
        with open(fname, "rb") as f:
            st.download_button(label=f'Download {fname}', data=f, file_name=fname)

st.markdown("---")
st.caption("Seoul Air Quality, Mobility & Consumption Dashboard – 2025 | by AI Assistant")
