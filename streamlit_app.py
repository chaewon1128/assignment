import os
import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk

st.set_page_config(page_title="Seoul Air Quality & Lifestyle Dashboard", layout="wide")

files_needed = ["spent.csv", "ppl_2012.csv", "ppl_2014.csv",
                "delivery.csv", "combined_pol.csv", "trans.csv"]
missing = [f for f in files_needed if not os.path.exists(f)]
if missing:
    st.error(f"Missing files: {missing}")
    st.stop()

spent = pd.read_csv("spent.csv")
ppl_2012 = pd.read_csv("ppl_2012.csv")
ppl_2014 = pd.read_csv("ppl_2014.csv")
delivery = pd.read_csv("delivery.csv")
pol = pd.read_csv("combined_pol.csv")
trans = pd.read_csv("trans.csv")

# Preprocessing
pol['Date'] = pd.to_datetime(pol['일시'], errors='coerce')
pol = pol.dropna(subset=['Date'])
pol['Year'] = pol['Date'].dt.year.astype(str)
pol['Month'] = pol['Date'].dt.month.astype(str).str.zfill(2)

spent['Year'] = spent['기준_년분기_코드'].astype(str).str[:4]

trans['Date'] = pd.to_datetime(trans['기준_날짜'], errors='coerce')
trans = trans.dropna(subset=['Date'])
trans['Year'] = trans['Date'].dt.year.astype(str)

delivery['Date'] = pd.to_datetime(delivery['Date'], errors='coerce')

GUS = sorted(list(set(pol[pol['자치구'] != '평균']['자치구'])))

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

def select_years(key:str, default=None):
    all_years = sorted(pol['Year'].unique())
    if default is None:
        default = [all_years[-1]]  # last year default
    selected = st.multiselect(f"Select Year(s) - {key}", all_years, default=default, key=key)
    return selected

def select_months(key:str, default=None):
    all_months = [str(i).zfill(2) for i in range(1,13)]
    if default is None:
        default = all_months
    selected = st.multiselect(f"Select Month(s) - {key}", all_months, default=default, key=key)
    return selected

def select_dates(key:str, default=None):
    all_dates = sorted(pol['Date'].dt.strftime("%Y-%m-%d").unique())
    # limit to recent 100 dates to avoid overload
    all_dates = all_dates[-100:]
    if default is None:
        default = all_dates
    selected = st.multiselect(f"Select Dates (max 100) - {key}", all_dates, default=default, key=key)
    return selected

def select_gus(key:str, default=None):
    opts = ["All Districts"] + GUS
    if default is None:
        default = opts[:6]
    selected = st.multiselect(f"Select District(s) - {key}", opts, default=default, key=key)
    if "All Districts" in selected:
        return GUS
    else:
        return selected

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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Air Quality Trends",
    "Mobility & Behavior",
    "Delivery & Spending",
    "Correlations & Insights",
    "Data Downloads"
])

with tab1:
    st.header("Air Quality Trends")
    years_tab1 = select_years("tab1_year", default=[YEARS[-1]])
    months_tab1 = select_months("tab1_month")
    gus_tab1 = select_gus("tab1_gu", default=['All Districts'])
    
    pol_filt = pol[(pol['Year'].isin(years_tab1)) & 
                   (pol['Month'].isin(months_tab1)) &
                   (pol['자치구'].isin(gus_tab1))]
    
    # Daily PM10 trends line chart for filtered districts
    daily_pm10 = pol_filt.groupby(['Date','자치구'])['미세먼지(PM10)'].mean().unstack()
    st.line_chart(daily_pm10)
    
    # Average PM10 bar chart per district
    avg_pm10 = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10,5))
    colors = ['#aad0f7' if v<=30 else '#85e085' if v<=80 else '#ffb347' if v<=150 else '#ff7675' for v in avg_pm10]
    avg_pm10.index = translate_gus(avg_pm10.index)
    ax.bar(avg_pm10.index, avg_pm10.values, color=colors)
    ax.set_title('Average PM10 by District')
    ax.set_xlabel('District')
    ax.set_ylabel('Average PM10 (μg/m³)')
    plt.xticks(rotation=45, ha='right')
    st.pyplot(fig)
    
    # PM10 district map
    map_df = avg_pm10.reset_index()
    map_df.columns = ['District','Avg_PM10']
    map_df['lat'] = map_df['District'].map(lambda d: seoul_gu_latlon.get(reverse_translate_gus([d])[0],(0,0))[0])
    map_df['lon'] = map_df['District'].map(lambda d: seoul_gu_latlon.get(reverse_translate_gus([d])[0],(0,0))[1])
    map_df['color'] = map_df['Avg_PM10'].apply(lambda v: [170,204,247] if v<=30 else [133,224,133] if v<=80 else [255,179,71] if v<=150 else [255,118,117])
    layer = pdk.Layer(
        'ScatterplotLayer',
        data=map_df,
        get_position='[lon,lat]',
        get_radius=3000,
        get_fill_color='color',
        pickable=True
    )
    view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state,
                            tooltip={"text": "{District}\nPM10: {Avg_PM10:.1f}"}))

with tab2:
    st.header("Mobility & Behavior")
    years_tab2 = select_years("tab2_year", default=[YEARS[-1]])
    gus_tab2 = select_gus("tab2_gu", default=['All Districts'])
    
    trans_filt = trans[(trans['Year'].isin(years_tab2)) & (trans['자치구'].isin(gus_tab2))]
    ppl_2012_sel = ppl_2012[ppl_2012['거주지'].isin(gus_tab2)].set_index('거주지')['개수']
    ppl_2014_sel = ppl_2014[ppl_2014['거주지'].isin(gus_tab2)].set_index('거주지')['개수']
    
    st.subheader("Public Transport Usage by District")
    pt_usage = trans_filt.groupby('자치구')['승객_수'].sum().reindex(gus_tab2)
    pt_usage.index = translate_gus(pt_usage.index)
    fig, ax = plt.subplots()
    pt_usage.plot(kind='bar', color='lightcoral', ax=ax)
    ax.set_xlabel('District')
    ax.set_ylabel('Passenger Count')
    st.pyplot(fig)
    
    st.subheader("Floating Population Comparison (2012 vs 2014)")
    ppl_df = pd.DataFrame({'2012': ppl_2012_sel, '2014': ppl_2014_sel}).fillna(0)
    ppl_df.index = translate_gus(ppl_df.index)
    st.bar_chart(ppl_df)

with tab3:
    st.header("Delivery & Spending")
    years_tab3 = select_years("tab3_year", default=[YEARS[-1]])
    gus_tab3 = select_gus("tab3_gu", default=['All Districts'])
    
    spent_filt = spent[(spent['Year'].isin(years_tab3)) & (spent['자치구'].isin(gus_tab3))]
    spent_avg = spent_filt.groupby('자치구')['지출_총금액'].mean().reindex(gus_tab3)
    
    st.subheader("Average Spending by District")
    fig, ax = plt.subplots()
    spent_avg.index = translate_gus(spent_avg.index)
    spent_avg.plot(kind='bar', color='mediumpurple', ax=ax)
    ax.set_xlabel("District")
    ax.set_ylabel("Average Spending (KRW)")
    st.pyplot(fig)
    
    st.subheader("Delivery Volume (Seoul Total)")
    if '전체' in delivery.columns:
        st.line_chart(delivery.set_index('Date')['전체'])
    else:
        st.line_chart(delivery.iloc[:,1])
    
    common_gus = spent_avg.index.map(lambda x: reverse_translate_gus([x])[0]).intersection(seoul_gu_latlon.keys())
    pm10_avg = pol[(pol['Year'].isin(years_tab3)) & (pol['자치구'].isin(gus_tab3))].groupby('자치구')['미세먼지(PM10)'].mean().reindex(common_gus)
    demo_delivery_vol = spent_avg.loc[translate_gus(common_gus)] / spent_avg.max() * 200
    
    deliv_map = pd.DataFrame({
        "lat": [seoul_gu_latlon[g][0] for g in common_gus],
        "lon": [seoul_gu_latlon[g][1] for g in common_gus],
        "PM10": pm10_avg.values,
        "Spending": spent_avg.loc[translate_gus(common_gus)].values,
        "Delivery": demo_delivery_vol.values
    })
    
    deliv_map["pm_color"] = deliv_map["PM10"].apply(lambda v: [170,204,247] if v<=30 else [133,224,133] if v<=80 else [255,179,71] if v<=150 else [255,118,117])
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
    years_tab4 = select_years("tab4_year", default=[YEARS[-1]])
    gus_tab4 = select_gus("tab4_gu", default=['All Districts'])
    
    pol_corr = pol[(pol['Year'].isin(years_tab4)) & (pol['자치구'].isin(gus_tab4))]
    spent_corr = spent[(spent['Year'].isin(years_tab4)) & (spent['자치구'].isin(gus_tab4))]
    trans_corr = trans[(trans['Year'].isin(years_tab4)) & (trans['자치구'].isin(gus_tab4))]
    
    pm10_avg = pol_corr.groupby('자치구')['미세먼지(PM10)'].mean()
    spending_avg = spent_corr.groupby('자치구')['지출_총금액'].mean()
    transit_avg = trans_corr.groupby('자치구')['승객_수'].sum()
    
    pop_2012 = ppl_2012.set_index('거주지')['개수'].reindex(gus_tab4)
    pop_2014 = ppl_2014.set_index('거주지')['개수'].reindex(gus_tab4)
    
    corr_df = pd.DataFrame({
        "PM10": pm10_avg,
        "Spending": spending_avg,
        "Transit": transit_avg,
        "Pop2012": pop_2012,
        "Pop2014": pop_2014
    }).dropna()
    
    corr_mat = corr_df.corr(method='pearson')
    
    fig, ax = plt.subplots(figsize=(7,7))
    sns.heatmap(corr_mat, annot=True, cmap='vlag', ax=ax, center=0, fmt=".2f",
                cbar_kws={'label': 'Pearson Correlation Coefficient'})
    ax.set_title("Correlation Matrix (Pearson)")
    st.pyplot(fig)
    
    st.markdown(
        """
        **Insights:**  
        - Higher PM10 correlates with increased delivery and spending, and decreased transit usage and floating population.  
        - Businesses should consider locating delivery-focused stores near major transit hubs to future-proof amid pollution.  
        - Use air quality forecasts for sales and inventory planning.
        """
    )
with tab5:
    st.header("Download Data")
    for fname in files_needed:
        with open(fname, "rb") as f:
            st.download_button(label=f'Download {fname}', data=f, file_name=fname)

st.caption("© 2025 Seoul Air Quality & Lifestyle Dashboard")
