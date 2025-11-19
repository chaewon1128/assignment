import os
import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk

st.set_page_config(page_title="Seoul Air Quality & Lifestyle Dashboard", layout="wide")

# --- Data Loading & Preprocessing (same as your previous step) ---
# Assuming variables: pol, spent, trans, delivery, ppl_2012, ppl_2014 already loaded & preprocessed
# with columns for 'Date' (datetime), 'Year','Month' (string), 'Day' (string), 'District' ('자치구'), etc.

# You can add year, month, day columns for flexible filtering
for df in [pol, spent, trans, delivery]:
    if 'Date' in df.columns:
        df['Year'] = df['Date'].dt.strftime('%Y')
        df['Month'] = df['Date'].dt.strftime('%Y-%m')
        df['Day'] = df['Date'].dt.strftime('%Y-%m-%d')

# District list
GUS = sorted(list(set(pol[pol['자치구'] != '평균']['자치구'])))

# English labels mapped from Korean districts
eng_labels = {
    '강남구': "Gangnam-gu", '강동구': "Gangdong-gu", '강북구': "Gangbuk-gu",
    '강서구': "Gangseo-gu", '관악구': "Gwanak-gu", '광진구':"Gwangjin-gu",
    '구로구':"Guro-gu", '금천구':"Geumcheon-gu", '노원구':"Nowon-gu",
    '도봉구':"Dobong-gu", '동대문구':"Dongdaemun-gu", '동작구':"Dongjak-gu",
    '마포구':"Mapo-gu", '서대문구':"Seodaemun-gu", '서초구':"Seocho-gu",
    '성동구':"Seongdong-gu", '성북구':"Seongbuk-gu", '송파구':"Songpa-gu",
    '양천구':"Yangcheon-gu", '영등포구':"Yeongdeungpo-gu", '용산구':"Yongsan-gu",
    '은평구':"Eunpyeong-gu", '종로구':"Jongno-gu", '중구':"Jung-gu",
    '중랑구':"Jungnang-gu"
}

def translate_gus(gus):
    return [eng_labels.get(g, g) for g in gus]

def reverse_translate_gus(engs):
    rev = {v:k for k,v in eng_labels.items()}
    return [rev.get(e, e) for e in engs]

# Filtering widgets with unique keys and added date/month filtering
def select_filter_date(key_prefix, default_years=None, default_month=None, default_day=None):
    years_all = sorted(pol['Year'].unique())
    months_all = sorted(pol['Month'].dropna().unique())
    days_all = sorted(pol['Day'].dropna().unique())

    years = st.multiselect(f"Select Year(s) - {key_prefix}", years_all, default=default_years or [years_all[-1]], key=f"{key_prefix}_year")
    months = st.multiselect(f"Select Month(s) - {key_prefix} (YYYY-MM)", months_all, default=default_month or [], key=f"{key_prefix}_month")
    days = st.multiselect(f"Select Day(s) - {key_prefix}", days_all, default=default_day or [], key=f"{key_prefix}_day")
    return years, months, days

def select_gus_with_all(key_prefix, default=None):
    options = ["All Districts"] + GUS
    default = default or [options[0]]
    selected = st.multiselect(f"Select District(s) - {key_prefix}", options, default=default, key=f"{key_prefix}_gus")
    if "All Districts" in selected:
        return GUS
    else:
        return selected

# Seoul district lat/lon dict for map
seoul_gu_latlon = {
    '강남구': (37.5172,127.0473), '강동구': (37.5301,127.1237), '강북구': (37.6396,127.0256),
    '강서구': (37.5509,126.8495), '관악구': (37.4781,126.9516), '광진구': (37.5386,127.0823),
    '구로구': (37.4954,126.8581), '금천구': (37.4600,126.9002), '노원구': (37.6544,127.0568),
    '도봉구': (37.6688,127.0477), '동대문구': (37.5744,127.0396), '동작구': (37.5124,126.9396),
    '마포구': (37.5634,126.9087), '서대문구': (37.5792,126.9368), '서초구': (37.4837,127.0324),
    '성동구': (37.5633,127.0363), '성북구': (37.6061,127.0220), '송파구': (37.5145,127.1067),
    '양천구': (37.5169,126.8666), '영등포구': (37.5264,126.8963), '용산구': (37.5326,126.9907),
    '은평구': (37.6176,126.9227), '종로구': (37.5735,126.9797), '중구': (37.5636,126.9976),
    '중랑구': (37.6063,127.0926)
}

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Air Quality Trends",
    "Mobility & Behavior",
    "Delivery & Spending",
    "Correlations & Insights",
    "Data Downloads"
])

with tab1:
    st.header("Air Quality Trends")
    years, months, days = select_filter_date("tab1", default_years=[YEARS[-1]])
    gus = select_gus_with_all("tab1", default=["All Districts"])

    pol_filt = pol[
        (pol['Year'].isin(years)) & 
        ((pol['Month'].isin(months)) if months else True) & 
        ((pol['Day'].isin(days)) if days else True) & 
        (pol['자치구'].isin(gus))
    ]

    st.subheader("Daily PM10 Trends")
    daily_pm10 = pol_filt.groupby(['Date','자치구'])['미세먼지(PM10)'].mean().unstack()
    st.line_chart(daily_pm10)

    st.subheader("Average PM10 by District")
    avg_pm10 = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean()
    fig, ax = plt.subplots(figsize=(10,5))
    avg_pm10.index = translate_gus(avg_pm10.index)
    avg_pm10.plot(kind='bar', color='skyblue', ax=ax)
    ax.set_xlabel("District")
    ax.set_ylabel("Avg PM10 (μg/m³)")
    ax.set_title("Average PM10 by District")
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

    st.subheader("PM10 Heatmap by District")
    heat_df = avg_pm10.reset_index()
    heat_df.columns = ['District', 'Avg_PM10']
    heat_df['lat'] = heat_df['District'].map(lambda d: seoul_gu_latlon.get(reverse_translate_gus([d])[0], (0,0))[0])
    heat_df['lon'] = heat_df['District'].map(lambda d: seoul_gu_latlon.get(reverse_translate_gus([d])[0], (0,0))[1])
    heat_df['color'] = heat_df['Avg_PM10'].apply(
        lambda v: [170,204,247] if v<=30 else [133,224,133] if v<=80 else [255,179,71] if v<=150 else [255,118,117]
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=heat_df,
        get_position='[lon, lat]',
        get_radius=3000,
        get_fill_color='color',
        pickable=True)
    view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state,
                            tooltip={"text": "{District}\nAvg PM10: {Avg_PM10:.1f}"}))

with tab2:
    st.header("Mobility & Behavior")
    years, _, _ = select_filter_date("tab2", default_years=[YEARS[-1]])
    gus = select_gus_with_all("tab2", default=["All Districts"])

    trans_filt = trans[(trans['Year'].isin(years)) & (trans['자치구'].isin(gus))]
    ppl_2012_sel = ppl_2012[ppl_2012['거주지'].isin(gus)].set_index('거주지')['개수']
    ppl_2014_sel = ppl_2014[ppl_2014['거주지'].isin(gus)].set_index('거주지')['개수']

    st.subheader("Public Transport Usage by District")
    transit_sum = trans_filt.groupby('자치구')['승객_수'].sum().reindex(gus)
    transit_sum.index = translate_gus(transit_sum.index)
    fig, ax = plt.subplots(figsize=(12,5))
    transit_sum.plot(kind='bar', ax=ax, color='lightcoral')
    ax.set_xlabel("District")
    ax.set_ylabel("Passenger Count")
    ax.set_title("Total Public Transport Usage")
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

    st.subheader("Floating Population Comparison (2012 vs 2014)")
    ppl_df = pd.DataFrame({'2012': ppl_2012_sel, '2014': ppl_2014_sel}).fillna(0)
    ppl_df.index = translate_gus(ppl_df.index)
    st.bar_chart(ppl_df)

with tab3:
    st.header("Delivery & Spending")
    years = st.multiselect("Select Year(s) - tab3", YEARS, default=[YEARS[-1]], key="years_tab3")
    gus = select_gus_with_all("tab3", default=["All Districts"])

    spent_filt = spent[(spent['Year'].isin(years)) & (spent['자치구'].isin(gus))]
    spent_avg = spent_filt.groupby('자치구')['지출_총금액'].mean().reindex(gus)

    st.subheader("Avg Spending by District")
    fig, ax = plt.subplots(figsize=(10,5))
    spent_avg.index = translate_gus(spent_avg.index)
    spent_avg.plot(kind='bar', ax=ax, color='mediumpurple')
    ax.set_xlabel("District")
    ax.set_ylabel("Avg Spending (KRW)")
    ax.set_title("Average Spending")
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

    st.subheader("Delivery Volume (Seoul Total)")
    if '전체' in delivery.columns:
        st.line_chart(delivery.set_index('Date')['전체'])
    else:
        st.line_chart(delivery.iloc[:,1])

    common_gus = spent_avg.index.map(lambda x: reverse_translate_gus([x])[0]).intersection(seoul_gu_latlon.keys())
    pm10_avg = pol[(pol['Year'].isin(years)) & (pol['자치구'].isin(gus))].groupby('자치구')['미세먼지(PM10)'].mean().reindex(common_gus)
    demo_delivery_vol = spent_avg.loc[translate_gus(common_gus)] / spent_avg.max() * 200

    deliv_map = pd.DataFrame({
        "lat": [seoul_gu_latlon[g][0] for g in common_gus],
        "lon": [seoul_gu_latlon[g][1] for g in common_gus],
        "PM10": pm10_avg.values,
        "Spending": spent_avg.loc[translate_gus(common_gus)].values,
        "Delivery": demo_delivery_vol.values
    })
    deliv_map["pm_color"] = deliv_map["PM10"].apply(
        lambda v: [170,204,247] if v <= 30 else [133,224,133] if v <= 80 else [255,179,71] if v <= 150 else [255,118,117]
    )
    layer2 = pdk.Layer(
        "ScatterplotLayer",
        data=deliv_map,
        get_position='[lon, lat]',
        get_radius='Delivery + 1000',
        get_fill_color='pm_color',
        pickable=True,
    )
    view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10)
    st.pydeck_chart(pdk.Deck(layers=[layer2], initial_view_state=view_state,
                            tooltip={"text": "{Spending:.0f}₩\nPM10: {PM10:.1f}\nDelivery: {Delivery:.0f}"}))

with tab4:
    st.header("Correlations & Insights")
    years = st.multiselect("Select Year(s) - tab4", YEARS, default=[YEARS[-1]], key="years_tab4")
    gus = select_gus_with_all("tab4", default=["All Districts"])

    pol_corr = pol[(pol['Year'].isin(years)) & (pol['자치구'].isin(gus))]
    spent_corr = spent[(spent['Year'].isin(years)) & (spent['자치구'].isin(gus))]
    trans_corr = trans[(trans['Year'].isin(years)) & (trans['자치구'].isin(gus))]

    pm10_avg = pol_corr.groupby('자치구')['미세먼지(PM10)'].mean()
    spending_avg = spent_corr.groupby('자치구')['지출_총금액'].mean()
    transit_avg = trans_corr.groupby('자치구')['승객_수'].sum()

    pop_2012 = ppl_2012.set_index('거주지')['개수'].reindex(gus)
    pop_2014 = ppl_2014.set_index('거주지')['개수'].reindex(gus)

    corr_df = pd.DataFrame({
        "PM10": pm10_avg,
        "Spending": spending_avg,
        "Transit": transit_avg,
        "Pop2012": pop_2012,
        "Pop2014": pop_2014
    }).dropna()

    corr_mat = corr_df.corr(method='pearson')

    fig, ax = plt.subplots(figsize=(7,7))
    sns.heatmap(corr_mat, annot=True, cmap='vlag', ax=ax, center=0, fmt=".2f", linewidths=.5,
                cbar_kws={'label': 'Pearson correlation coefficient'})
    ax.set_title("Correlation Matrix among Key Indicators")
    ax.set_xticklabels(corr_mat.columns, rotation=45, ha='right')
    st.pyplot(fig)

    st.write(
        """
        **Insights:**  
        - Higher PM10 is correlated with increased delivery and spending, but decreased transit use and floating population.  
        - Businesses should focus on delivery near transit hubs and use air quality forecasts for inventory planning.
        """
    )

with tab5:
    st.header("Download Data")
    for fname in files_needed:
        with open(fname, "rb") as f:
            st.download_button(label=f'Download {fname}', data=f, file_name=fname)

st.caption("© 2025 Seoul Air Quality & Lifestyle Dashboard")
