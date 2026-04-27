import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# Configuration
st.set_page_config(page_title="Dashboard Educativo Bogotá", layout="wide", page_icon="🎓")

# Custom CSS for Premium Look
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #1f2937;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #374151;
    }
    h1, h2, h3 {
        color: #f3f4f6;
    }
    </style>
    """, unsafe_allow_html=True)

# Data for Centroids
localidades_info = {
    'SUBA': {'area': 100.5, 'lat': 4.7411, 'lon': -74.0840},
    'ENGATIVA': {'area': 35.8, 'lat': 4.7001, 'lon': -74.1132},
    'KENNEDY': {'area': 38.5, 'lat': 4.6303, 'lon': -74.1534},
    'USAQUEN': {'area': 65.3, 'lat': 4.7402, 'lon': -74.0305},
    'BOSA': {'area': 23.9, 'lat': 4.6075, 'lon': -74.1915},
    'FONTIBON': {'area': 33.2, 'lat': 4.6732, 'lon': -74.1435},
    'RAFAEL URIBE URIBE': {'area': 13.8, 'lat': 4.5772, 'lon': -74.1162},
    'CIUDAD BOLIVAR': {'area': 130.0, 'lat': 4.5000, 'lon': -74.1500},
    'SAN CRISTOBAL': {'area': 49.0, 'lat': 4.5500, 'lon': -74.0800},
    'PUENTE ARANDA': {'area': 17.3, 'lat': 4.6200, 'lon': -74.1100},
    'TEUSAQUILLO': {'area': 14.1, 'lat': 4.6400, 'lon': -74.0800},
    'TUNJUELITO': {'area': 9.9, 'lat': 4.5800, 'lon': -74.1300},
    'BARRIOS UNIDOS': {'area': 11.9, 'lat': 4.6700, 'lon': -74.0700},
    'USME': {'area': 215.0, 'lat': 4.4500, 'lon': -74.1200},
    'ANTONIO NARIÑO': {'area': 4.8, 'lat': 4.5900, 'lon': -74.1000},
    'LOS MARTIRES': {'area': 6.5, 'lat': 4.6000, 'lon': -74.0800},
    'CHAPINERO': {'area': 38.0, 'lat': 4.6500, 'lon': -74.0500},
    'LA CANDELARIA': {'area': 1.8, 'lat': 4.5900, 'lon': -74.0700},
    'SANTAFE': {'area': 45.0, 'lat': 4.6000, 'lon': -74.0600}
}

@st.cache_data
def load_data():
    file_path = "Establecimientos educativos 1_8_2025 (1).xls"
    # Read everything as string to avoid type conflicts
    df = pd.read_excel(file_path, skiprows=1, dtype=str)
    
    # Fill all NaNs with a standard string
    df = df.fillna("No especificado")
    
    # Clean whitespace
    for col in df.columns:
        df[col] = df[col].str.strip()
        
    # Convert specifically needed numeric columns safely
    if 'CANTIDAD DE SEDES ACTIVAS' in df.columns:
        df['CANTIDAD DE SEDES ACTIVAS'] = pd.to_numeric(df['CANTIDAD DE SEDES ACTIVAS'], errors='coerce').fillna(0)
            
    return df

# Main Logic
st.title("🎓 Dashboard Educativo Bogotá")
st.markdown("---")

try:
    df = load_data()
    
    # --- SIDEBAR FILTERS ---
    st.sidebar.header("🔍 Filtros de Búsqueda")
    
    # 1. Filter by Localidad
    all_localidades = sorted([str(x) for x in df['NOMBRE LOCALIDAD'].unique() if str(x) != 'No especificado'])
    selected_localidades = st.sidebar.multiselect("Seleccionar Localidad", all_localidades, default=all_localidades[:3])
    
    # 2. Filter by Level
    # Extract all possible levels
    raw_levels = df['NIVELES'].str.split('--', expand=True).stack().unique()
    all_levels = sorted([str(x) for x in raw_levels if str(x) != 'No especificado'])
    selected_levels = st.sidebar.multiselect("Niveles Educativos", all_levels, default=all_levels)
    
    # 3. Filter by Calendar
    calendars = sorted([str(x) for x in df['CALENDARIOS'].unique()])
    selected_calendars = st.sidebar.multiselect("Calendario", calendars, default=calendars)

    # Apply Filters
    mask = (df['NOMBRE LOCALIDAD'].isin(selected_localidades)) & \
           (df['CALENDARIOS'].isin(selected_calendars))
    
    # Filter by level (this is a bit trickier since it's a joined string)
    def has_level(levels_str, selected):
        if pd.isna(levels_str): return False
        current_levels = levels_str.split('--')
        return any(lvl in selected for lvl in current_levels)

    df_filtered = df[mask]
    df_filtered = df_filtered[df_filtered['NIVELES'].apply(lambda x: has_level(x, selected_levels))]

    # --- SEARCH BOX ---
    search_query = st.text_input("🔎 Buscar colegio por nombre...", "")
    if search_query:
        df_filtered = df_filtered[df_filtered['NOMBRE ESTABLECIMIENTO'].str.contains(search_query, case=False, na=False)]

    # --- METRICS ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Colegios Filtrados", len(df_filtered))
    with col2:
        st.metric("% del Total", f"{(len(df_filtered)/len(df)*100):.1f}%")
    with col3:
        st.metric("Sedes Activas", df_filtered['CANTIDAD DE SEDES ACTIVAS'].sum())
    with col4:
        # A simple "Density" metric for selected areas
        total_area = sum([localidades_info.get(loc, {}).get('area', 0) for loc in selected_localidades])
        if total_area > 0:
            st.metric("Densidad (Col/km²)", f"{(len(df_filtered)/total_area):.2f}")

    # --- CALCULATE AGGREGATES FOR TABS ---
    map_counts = df_filtered['NOMBRE LOCALIDAD'].value_counts().reset_index()
    map_counts.columns = ['Localidad', 'Count']

    # --- TABS FOR DIFFERENT VIEWS ---
    tab_stats, tab_data, tab_map = st.tabs(["📊 Estadísticas", "📋 Explorador de Datos", "🗺️ Mapa Territorial"])

    with tab_stats:
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            st.subheader("Top Localidades (Filtradas)")
            fig_bar = px.bar(map_counts.head(10), x='Count', y='Localidad', orientation='h', 
                             color='Count', color_continuous_scale='Viridis', template="plotly_dark")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_s2:
            st.subheader("Oferta por Calendario")
            fig_pie = px.pie(df_filtered, names='CALENDARIOS', hole=0.5, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Combinaciones de Jornadas más comunes")
        jornadas_counts = df_filtered['JORNADAS'].value_counts().head(10).reset_index()
        fig_jor = px.bar(jornadas_counts, x='count', y='JORNADAS', orientation='h', template="plotly_dark")
        st.plotly_chart(fig_jor, use_container_width=True)

    with tab_data:
        st.subheader("Listado Detallado")
        st.dataframe(df_filtered[['NOMBRE ESTABLECIMIENTO', 'NOMBRE LOCALIDAD', 'DIRECCION CATASTRO', 'TELEFONO', 'CALENDARIOS', 'NIVELES']], 
                     use_container_width=True)
        
        # Download Option
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar datos filtrados (CSV)",
            data=csv,
            file_name='colegios_filtrados.csv',
            mime='text/csv',
        )

    with tab_map:
        st.subheader("Distribución Espacial")
        
        # Determine view mode
        single_mode = len(selected_localidades) == 1
        
        if single_mode:
            locality_name = selected_localidades[0]
            loc_info = localidades_info.get(locality_name, {'lat': 4.6097, 'lon': -74.0817})
            
            st.info(f"📍 Ubicando colegios en **{locality_name}**...")
            
            geolocator = Nominatim(user_agent="bogota_edu_app_v2")
            
            if 'geocoded_data' not in st.session_state:
                st.session_state.geocoded_data = {}
            
            to_map = df_filtered.copy()
            limit = 40 
            if len(to_map) > limit:
                st.warning(f"Mostrando muestra de {limit} colegios para mayor velocidad.")
                to_map = to_map.head(limit)
            
            progress_bar = st.progress(0)
            
            points = []
            for i, (idx, row) in enumerate(to_map.iterrows()):
                # Clean address: remove -- and extra spaces
                clean_addr = str(row['DIRECCION CATASTRO']).replace('--', ' ').strip()
                full_query = f"{clean_addr}, {row['NOMBRE LOCALIDAD']}, Bogota, Colombia"
                
                if full_query in st.session_state.geocoded_data:
                    location = st.session_state.geocoded_data[full_query]
                else:
                    try:
                        # Try searching with just the cleaned address
                        location = geolocator.geocode(full_query, timeout=5)
                        st.session_state.geocoded_data[full_query] = location
                    except:
                        location = None
                
                if location:
                    points.append({
                        'name': row['NOMBRE ESTABLECIMIENTO'],
                        'lat': location.latitude,
                        'lon': location.longitude,
                        'info': f"<b>{row['NOMBRE ESTABLECIMIENTO']}</b><br>{row['NIVELES']}"
                    })
                
                progress_bar.progress((i + 1) / len(to_map))
            
            progress_bar.empty()

            # Create Map centered on Locality Centroid
            m = folium.Map(location=[loc_info['lat'], loc_info['lon']], zoom_start=14, tiles="CartoDB dark_matter")
            
            for p in points:
                folium.Marker(
                    location=[p['lat'], p['lon']],
                    popup=p['info'],
                    icon=folium.Icon(color='blue', icon='graduation-cap', prefix='fa')
                ).add_to(m)
            
            if not points:
                st.warning("No se encontraron coordenadas exactas para los colegios de esta muestra, pero puedes ver el área general.")
        
        else:
            # Use pre-calculated aggregates
            geo_df = pd.DataFrame.from_dict(localidades_info, orient='index').reset_index()
            geo_df.columns = ['Localidad', 'area', 'lat', 'lon']
            map_data = pd.merge(map_counts, geo_df, on='Localidad')
            
            m = folium.Map(location=[4.6097, -74.0817], zoom_start=11, tiles="CartoDB dark_matter")
            
            for idx, row in map_data.iterrows():
                color = '#ef4444' if row['Count'] > 50 else '#3b82f6'
                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=row['Count'] / 5 if row['Count'] < 200 else 40,
                    popup=f"<b>{row['Localidad']}</b><br>Colegios: {row['Count']}",
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.6
                ).add_to(m)
        
        st_folium(m, width="100%", height=500)
except Exception as e:
    st.error(f"Error cargando los datos: {e}")
    st.info("Asegúrate de que el archivo 'Establecimientos educativos 1_8_2025 (1).xls' esté en la misma carpeta.")

st.markdown("---")
st.caption("Prototipo generado por Antigravity - Analista de Datos Senior")
