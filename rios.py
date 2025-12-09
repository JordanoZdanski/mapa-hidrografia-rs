import geopandas as gpd
import geobr
import os
import folium
from folium import plugins
import branca.colormap as cm
from shapely.geometry import box


PASTA_DADOS = "dados_rios_rs_v2023"
ARQUIVO_SAIDA = "portfolio_mapa_rs_gold_v2.html" 
URL_BANDEIRA = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Bandeira_do_Rio_Grande_do_Sul.svg/200px-Bandeira_do_Rio_Grande_do_Sul.svg.png"


CORES_REGIOES = ['#EF9A9A', '#CE93D8', '#90CAF9', '#80CBC4', '#E6EE9C', '#FFE082', '#FFAB91']


print(">> 1. Carregando dados...")

# Localiza arquivo
shp_rios = None
if os.path.exists(PASTA_DADOS):
    for root, dirs, files in os.walk(PASTA_DADOS):
        for f in files:
            if f.endswith('.shp') and ('trecho_drenagem' in f.lower() or 'hidrografia' in f.lower()):
                shp_rios = os.path.join(root, f)
                break
        if shp_rios: break

if not shp_rios:
    print("ERRO: Dados não encontrados.")
    exit()


rs_limite = geobr.read_state(code_state='RS', year=2020).to_crs("EPSG:4326")
rs_meso = geobr.read_meso_region(code_meso='RS', year=2020).to_crs("EPSG:4326")


print("   Processando geometria dos rios...")
gdf_rios = gpd.read_file(shp_rios, bbox=rs_limite).to_crs("EPSG:4326")
gdf_rios = gpd.clip(gdf_rios, rs_limite)
gdf_rios = gdf_rios[gdf_rios.geom_type.isin(['LineString', 'MultiLineString'])]


print(f"   Rios antes do filtro: {len(gdf_rios)}")
gdf_rios = gdf_rios[gdf_rios.geometry.length > 0.015]
print(f"   Rios após filtro de 1.6km: {len(gdf_rios)}")

# Classificação
coluna_nome = 'nome' if 'nome' in gdf_rios.columns else 'geodenom'
principais = gdf_rios[gdf_rios[coluna_nome].str.contains('Rio ', case=False, na=False)].copy()
secundarios = gdf_rios[~gdf_rios.index.isin(principais.index)].copy()


principais['geometry'] = principais.simplify(tolerance=0.0005) 
secundarios['geometry'] = secundarios.simplify(tolerance=0.002) 


print(">> 2. Montando mapa...")

m = folium.Map(location=[-30.5, -53.0], zoom_start=7, tiles=None, prefer_canvas=True)

# Base Satélite
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri', name='Satélite', control=True
).add_to(m)


folium.map.CustomPane('pane_sombra', z_index=200).add_to(m)
folium.map.CustomPane('pane_regioes', z_index=300).add_to(m)
folium.map.CustomPane('pane_sec', z_index=400).add_to(m)
folium.map.CustomPane('pane_princ', z_index=450).add_to(m)
folium.map.CustomPane('pane_borda', z_index=500).add_to(m)

#MÁSCARA (control=False)
lyr_sombra = folium.FeatureGroup(name="Sombra", control=False)
world_box = box(-180, -90, 180, 90)
mask_geom = gpd.GeoSeries([world_box.difference(rs_limite.geometry.iloc[0])], crs="EPSG:4326")
folium.GeoJson(
    mask_geom,
    style_function=lambda x: {'fillColor': 'black', 'color': 'none', 'fillOpacity': 0.65},
    interactive=False,
    pane='pane_sombra'
).add_to(lyr_sombra)
lyr_sombra.add_to(m)

# REGIÕES
lyr_regioes = folium.FeatureGroup(name="Divisão Regional", show=True)
colormap = cm.LinearColormap(colors=CORES_REGIOES, vmin=0, vmax=len(rs_meso))
folium.GeoJson(
    rs_meso,
    style_function=lambda x: {
        'fillColor': colormap(x['properties']['code_meso']),
        'color': 'white',
        'weight': 1.5,
        'fillOpacity': 0.4, 
    },
    tooltip=folium.GeoJsonTooltip(fields=['name_meso'], aliases=['Região:']),
    pane='pane_regioes'
).add_to(lyr_regioes)
lyr_regioes.add_to(m)

#SECUNDÁRIOS (icnerteza sobre a tolêrancia disso)
lyr_sec = folium.FeatureGroup(name="Rede Secundária", show=False)
folium.GeoJson(
    secundarios,
    style_function=lambda x: {'color': '#00BFFF', 'weight': 1.0, 'opacity': 0.8},
    pane='pane_sec'
).add_to(lyr_sec)
lyr_sec.add_to(m)

# RIOS PRINCIPAIS
lyr_princ = folium.FeatureGroup(name="Rede Principal", show=True)
folium.GeoJson(
    principais,
    style_function=lambda x: {'color': '#1E90FF', 'weight': 2.0, 'opacity': 1.0},
    tooltip=folium.GeoJsonTooltip(fields=[coluna_nome], aliases=['Rio:']),
    pane='pane_princ'
).add_to(lyr_princ)
lyr_princ.add_to(m)

# BORDA (control=False)
lyr_borda = folium.FeatureGroup(name="Borda", control=False)
folium.GeoJson(
    rs_limite,
    style_function=lambda x: {'color': 'white', 'weight': 2.5, 'fill': False},
    interactive=False,
    pane='pane_borda'
).add_to(lyr_borda)
lyr_borda.add_to(m)


print(">> 3. Finalizando UI...")
folium.LayerControl(collapsed=False, position='topright').add_to(m)
plugins.Fullscreen().add_to(m)

legend_html = f'''
     <div style="position: fixed; bottom: 30px; left: 30px; width: 300px; z-index: 9999;
         background: rgba(20, 20, 20, 0.8); backdrop-filter: blur(8px);
         padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2);
         font-family: 'Segoe UI', sans-serif; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
         
         <div style="display:flex; align-items:center; margin-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:10px;">
             <img src="{URL_BANDEIRA}" style="height:40px; border-radius:4px; margin-right:15px;">
             <div>
                 <h4 style="margin:0; font-weight:700; letter-spacing: -0.5px;">RIO GRANDE DO SUL</h4>
                 <div style="font-size:10px; opacity:0.7; letter-spacing:1px; margin-top:2px;">HIDROGRAFIA & SATÉLITE</div>
             </div>
         </div>
         
         <div style="font-size:12px; line-height:1.9;">
             <div style="display:flex; align-items:center;">
                 <span style="display:inline-block; width:15px; height:3px; background:#1E90FF; margin-right:8px;"></span>
                 Rios Principais
             </div>
             <div style="display:flex; align-items:center;">
                 <span style="display:inline-block; width:15px; height:1px; background:#00BFFF; margin-right:8px;"></span>
                 Rede Secundária <i style="font-size:10px; opacity:0.6; margin-left:5px">(Menu)</i>
             </div>
             <div style="display:flex; align-items:center;">
                 <span style="display:inline-block; width:12px; height:12px; background:linear-gradient(45deg, #EF9A9A, #80CBC4); border-radius:50%; margin-right:8px; border:1px solid #fff;"></span>
                 Regiões (Transparente)
             </div>
         </div>
         <div style="margin-top:15px; font-size:10px; opacity:0.6; text-align:right; border-top:1px solid rgba(255,255,255,0.1); padding-top:5px;">
             FONTE: IBGE BC250<br> 
             <span style="color:#fff; font-weight:600;">Jordano Zdanski Ficht</span>
         </div>
     </div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

m.save(ARQUIVO_SAIDA)
print(f">> SUCESSO! Mapa gerado: {ARQUIVO_SAIDA}")