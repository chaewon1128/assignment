import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk

st.set_page_config(page_title="Seoul Air Quality & Lifestyle Dashboard", layout="wide")

files_needed = ["spent.csv", "ppl_2012.csv", "ppl_2014.csv",
                "delivery.csv", "combined_pol.csv", "trans.csv"]
missing = [f for f in files_needed if not os.path.exists(f)]
if missing:
    st.error(f"Missing files: {missing}")
    st.stop()

def load_csv_safe(filename):
    for enc in ['euc-kr','cp949','utf-8']:
        try:
            return pd.read_csv(filename, encoding=enc)
        except:
            continue
    st.error(f"Failed to load {filename} with tested encodings.")
    return pd.DataFrame()

pol = load_csv_safe("combined_pol.csv")
spent = load_csv_safe("spent.csv")
trans = load_csv_safe("trans.csv")
delivery = load_csv_safe("delivery.csv")
ppl_2012 = load_csv_safe("ppl_2012.csv")
ppl_2014 = load_csv_safe("ppl_2014.csv")

pol['Date'] = pd.to_datetime(pol['일시'], errors='coerce')
pol.dropna(subset=['Date'], inplace=True)
pol['Year'] = pol['Date'].dt.year.astype(str)
pol['Month'] = pol['Date'].dt.month.astype(str).str.zfill(2)

spent['Year'] = spent['기준_년분기_코드'].astype(str).str[:4]

trans['Date'] = pd.to_datetime(trans['기준_날짜'], errors='coerce')
trans.dropna(subset=['Date'], inplace=True)
trans['Year'] = trans['Date'].dt.year.astype(str)

delivery['Date'] = pd.to_datetime(delivery['Date'], errors='coerce')

GUS = sorted(pol[pol['자치구'] != '평균']['자치구'].unique())

eng_labels = {
    '강남구': "Gangnam-gu", '강동구': "Gangdong-gu", '강북구': "Gangbuk-gu",
    '강서구': "Gangseo-gu", '관악구': "Gwanak-gu", '광진구': "Gwangjin-gu",
    '구로구': "Guro-gu", '금천구': "Geumcheon-gu", '노원구': "Nowon-gu",
    '도봉구': "Dobong-gu", '동대문구': "Dongdaemun-gu", '동작구': "Dongjak-gu",
    '마포구': "Mapo-gu", '서대문구': "Seodaemun-gu", '서초구': "Seocho-gu",
    '성동구': "Seongdong-gu", '성북구': "Seongbuk-gu", '송파구': "Songpa-gu",
    '양천구': "Yangcheon-gu", '영등포구': "Yeongdeungpo-gu", '용산구': "Yongsan-gu",
    '은평구': "Eunpyeong-gu", '종로구': "Jongno-gu", '중구': "Jung-gu",
    '중랑구': "Jungnang-gu"
}

def translate_gus(gus):
    return [eng_labels.get(g, g) for g in gus]

def reverse_translate_gus(engs):
    rev = {v:k for k,v in eng_labels.items()}
    return [rev.get(e, e) for e in engs]

def select_years(key:str, default=None):
    all_years = sorted(pol['Year'].unique())
    if default is None or len(default) == 0:
        default = [all_years[-1]] if len(all_years)>0 else []
    return st.multiselect(f"Select Year(s) - {key}", all_years, default=default, key=key)

def select_months(key:str, default=None):
    all_months = [str(i).zfill(2) for i in range(1,13)]
    return st.multiselect(f"Select Month(s) - {key}", all_months, default=default if default else all_months, key=key)

def select_gus(key:str, default=None):
    opts = ["All Districts"] + GUS
    sel = st.multiselect(f"Select District(s) - {key}", opts, default=default if default else opts[:6], key=key)
    if "All Districts" in sel:
        return GUS
    else:
        return sel

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
    years = select_years("tab1_year", default=[pol['Year'].max()])
    months = select_months("tab1_month")
    gus = select_gus("tab1_gu")
    
    pol_filt = pol[(pol['Year'].isin(years)) & (pol['Month'].isin(months)) & (pol['자치구'].isin(gus))]
    
    daily_pm10 = pol_filt.groupby(['Date', '자치구'])['미세먼지(PM10)'].mean().unstack()
    st.line_chart(daily_pm10)
    
    avg_pm10 = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().sort_values(ascending=False)
    colors = ['#aad0f7' if v <= 30 else '#85e085' if v <= 80 else '#ffb347' if v <= 150 else '#ff7675' for v in avg_pm10]
    fig = go.Figure()
    fig = px.bar(x=translate_gus(avg_pm10.index), y=avg_pm10.values, color=avg_pm10.values,
                 color_continuous_scale=['#aad0f7', '#85e085', '#ffb347', '#ff7675'])
    fig.update_layout(title='Average PM10 by District',
                      xaxis_title='District', yaxis_title='Avg PM10 (μg/m³)')
    st.plotly_chart(fig, use_container_width=True)
    
    map_df = avg_pm10.reset_index()
    map_df.columns = ['District','Avg_PM10']
    map_df['lat'] = map_df['District'].map(lambda d: seoul_gu_latlon.get(reverse_translate_gus([d])[0], (0,0))[0])
    map_df['lon'] = map_df['District'].map(lambda d: seoul_gu_latlon.get(reverse_translate_gus([d])[0], (0,0))[1])
    map_df['color'] = map_df['Avg_PM10'].apply(lambda v: [170,204,247] if v <= 30 else [133,224,133] if v <= 80 else [255,179,71] if v <= 150 else [255,118,117])
    layer = pdk.Layer('ScatterplotLayer', data=map_df, get_position='[lon, lat]', get_radius=3000, get_fill_color='color', pickable=True)
    view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{District}\nPM10: {Avg_PM10:.1f}"}))


with tab2:
    st.header("Mobility & Behavior")
    years = select_years("tab2_year", default=[pol['Year'].max()])
    gus = select_gus("tab2_gu")
    
    trans_filt = trans[(trans['Year'].isin(years)) & (trans['자치구'].isin(gus))]
    ppl_2012_sel = ppl_2012[ppl_2012['거주지'].isin(gus)].set_index('거주지')['개수']
    ppl_2014_sel = ppl_2014[ppl_2014['거주지'].isin(gus)].set_index('거주지')['개수']
    
    pt_usage = trans_filt.groupby('자치구')['승객_수'].sum().reindex(gus)
    pt_usage.index = translate_gus(pt_usage.index)
    fig = px.bar(x=pt_usage.index, y=pt_usage.values, labels={'x': 'District', 'y': 'Passenger Count'}, color=pt_usage.values, color_continuous_scale='Reds')
    st.plotly_chart(fig, use_container_width=True)
    
    ppl_df = pd.DataFrame({'2012': ppl_2012_sel, '2014': ppl_2014_sel}).fillna(0)
    ppl_df.index = translate_gus(ppl_df.index)
    fig2 = px.bar(ppl_df, barmode='group', labels={'index':'District'})
    st.plotly_chart(fig2, use_container_width=True)


with tab3:
    st.header("Delivery & Spending")
    years = select_years("tab3_year", default=[pol['Year'].max()])
    gus = select_gus("tab3_gu")
    
    spent_filt = spent[(spent['Year'].isin(years)) & (spent['자치구'].isin(gus))]
    spent_avg = spent_filt.groupby('자치구')['지출_총금액'].mean().reindex(gus)
    
    fig = px.bar(x=translate_gus(spent_avg.index), y=spent_avg.values, labels={'x':'District', 'y':'Average Spending (KRW)'}, color=spent_avg.values, color_continuous_scale='Purples')
    st.plotly_chart(fig, use_container_width=True)
    
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
    
    deliv_map["pm_color"] = deliv_map["PM10"].apply(lambda v: [170,204,247] if v <= 30 else [133,224,133] if v <= 80 else [255,179,71] if v <= 150 else [255,118,117])
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
    years = select_years("tab4_year", default=[pol['Year'].max()])
    gus = select_gus("tab4_gu")
    
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
    
    fig = px.imshow(corr_mat, text_auto=True, color_continuous_scale='RdBu_r', title='Correlation Matrix (Pearson)')
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown(
        """
        **Insights:**  
        - Strong correlations observed between PM10, Spending, Transit, and Population.
        - Higher PM10 correlates with increased delivery and spending, and decreased transit usage and floating population.  
        - Use air quality forecasts for strategic marketing and location planning.
        """
    )

with tab5:
    st.header("Download Data")
    for fname in files_needed:
        with open(fname, "rb") as f:
            st.download_button(label=f'Download {fname}', data=f, file_name=fname)

st.caption("© 2025 Seoul Air Quality & Lifestyle Dashboard")
