import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os 
from dotenv import load_dotenv
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
import plotly.graph_objs as go
import pydeck as pdk
import geopandas as gpd

load_dotenv()
# ------------------------- CONEXÃO COM O BANCO DE DADOS -----------------
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
database = os.getenv('DB_NAME')

connection_string = f'mysql+pymysql://{user}:{password}@{host}/{database}'
engine = create_engine(connection_string)

query = '''

WITH alunos_totais AS (
    SELECT 
        c.id AS turma_id,
        c.name AS nome_turma,
        t.id AS professor_id,  -- Incluir o ID do professor
        COUNT(DISTINCT s.id) AS total_alunos
    FROM 
        class c
    INNER JOIN 
        student s ON s.class_id = c.id
    INNER JOIN
        teacher t ON t.id = c.teacher_id  -- Associação entre professor e turma
    GROUP BY 
        c.id, c.name, t.id
),
alunos_melhoria AS (
    SELECT 
        s.id AS aluno_id,
        c.id AS turma_id,
        c.year AS ano_turma,
        c.cod_inep AS cod_inep_turma,
        t.id AS professor_id,  
        CAST(da.month as UNSIGNED) AS mes_sondagem,
        MIN(dh.ordering) AS min_ordering,
        MAX(dh.ordering) AS max_ordering
    FROM 
        diagnostic_assessment_students das
    INNER JOIN 
        student s ON das.student_id = s.id
    INNER JOIN 
        class c ON s.class_id = c.id
    INNER JOIN
        teacher t ON t.id = c.teacher_id  
    INNER JOIN 
        diagnostic_assessment_type_hypothesis dh ON das.hypothesis_id = dh.id
	INNER JOIN 
		diagnostic_assessment  da ON das.diagnostic_assessment_id  = da.id
    WHERE t.auth_id NOT IN ('3','6','18','64','1466346', '1581795','5844577','5273215', '6317922', '5844577','175689','1980922','2051263','2241909','2347872','2607842','2988478','3457137','3693288','3693431','3912304','4681737','4813648','5106338','5326020','5331581','5722986','5726715','5740041','6132779', '6183405', '6361801','6447188','6470829','6491287')
    GROUP BY 
        s.id, c.id, t.id
),
alunos_com_melhoria AS (
    SELECT 
        turma_id,
        ano_turma,
        cod_inep_turma,
        professor_id,
        mes_sondagem, 
        COUNT(aluno_id) AS alunos_com_melhoria
    FROM 
        alunos_melhoria
    WHERE 
        min_ordering < max_ordering  -- Filtra alunos que melhoraram de nível
    GROUP BY 
        turma_id, professor_id, mes_sondagem
)
SELECT 
    t.turma_id as id_turma,
    m.cod_inep_turma,
    t.nome_turma,
    m.ano_turma,
    sc.name AS nome_escola,
    sc.municipio AS cidade_escola,
    sc.uf AS estado_escola,
    t.professor_id as id_professor,  
    t.total_alunos,
    COALESCE(m.alunos_com_melhoria, 0) AS alunos_com_melhoria,
    ROUND((COALESCE(m.alunos_com_melhoria, 0) / t.total_alunos) * 100, 2) AS porcentagem_melhoria,
    CASE 
        WHEN m.mes_sondagem = '1' THEN 'Janeiro'
        WHEN m.mes_sondagem = '2' THEN 'Fevereiro'
        WHEN m.mes_sondagem = '3' THEN 'Março'
        WHEN m.mes_sondagem = '4' THEN 'Abril'
        WHEN m.mes_sondagem = '5' THEN 'Maio'
        WHEN m.mes_sondagem = '6' THEN 'Junho'
        WHEN m.mes_sondagem = '7' THEN 'Julho'
        WHEN m.mes_sondagem = '8' THEN 'Agosto'
        WHEN m.mes_sondagem = '9' THEN 'Setembro'
        WHEN m.mes_sondagem = '10' THEN 'Outubro'
        WHEN m.mes_sondagem = '11' THEN 'Novembro'
        WHEN m.mes_sondagem = '12' THEN 'Dezembro'
    END AS mes_sondagem
FROM 
    alunos_totais t
LEFT JOIN 
    alunos_com_melhoria m ON t.turma_id = m.turma_id
INNER JOIN
    school sc ON m.cod_inep_turma = sc.cod_inep

WHERE 
    COALESCE(m.alunos_com_melhoria, 0) > 0;
    '''

def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    modify = st.sidebar.checkbox("Adicionar Filtros", key="filter_checkbox")

    if not modify:
        return df

    df = df.copy()

    for col in df.columns:
        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

        if is_numeric_dtype(df[col]) and (df[col] == df[col].astype(int)).all():
            df[col] = df[col].astype(int)

    modification_container = st.sidebar.container()

    with modification_container:
        to_filter_columns = st.multiselect(
            "Filtrar pela Coluna: ", 
            df.columns,
            key="multiselect_columns"
        )
        for i, column in enumerate(to_filter_columns):
            left, right = st.columns((1, 20))

            if isinstance(df[column].dtype, pd.CategoricalDtype) or df[column].nunique() < 10:
                user_cat_input = right.multiselect(
                    f"Values for {column}",
                    df[column].unique(),
                    default=list(df[column].unique()),
                    key=f"multiselect_{column}_{i}"
                )
                df = df[df[column].isin(user_cat_input)]
            elif is_numeric_dtype(df[column]):
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                    f"Values for {column}",
                    min_value=_min,
                    max_value=_max,
                    value=(_min, _max),
                    step=step,
                    key=f"slider_{column}_{i}"
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f"Values for {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                    key=f"date_input_{column}_{i}"
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Digite uma substring pelo que quer filtrar de {column}",
                    key=f"text_input_{column}_{i}"
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input)]

    return df

df = pd.read_sql(query, engine)

turmas = filter_dataframe(df)

st.markdown("## Dados de evidência de aprendizagem 📝")

col1, col2, col3, col4, col5 = st.columns(5)
total_professores = turmas['id_professor'].nunique()
total_turmas = turmas['id_turma'].nunique()
df_filtrado = turmas[turmas['porcentagem_melhoria'] >= 50]
soma_alunos = turmas['total_alunos'].sum()
alunos_evid = turmas['alunos_com_melhoria'].sum()
total_professores_50 = df_filtrado['id_professor'].nunique()

# st.markdown(f"#### Quantidade de Professores com Turma cadastrada com evidência de aprendizagem: {total_professores}")

with col1:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;"> Total de Alunos <br> nas Turmas com Evid. <br> de Aprendizagem </span><br>
            <span style="font-size: 36px; font-weight: bold;">{soma_alunos}</span>
        </div>
        """, unsafe_allow_html=True)
    # st.metric("Total de Profs com Turma Cadastrada", total_professores)

with col2:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;"> Total de Alunos <br> com Evidência <br> de Aprendizagem </span><br>
            <span style="font-size: 36px; font-weight: bold;">{alunos_evid}</span>
        </div>
        """, unsafe_allow_html=True)
    # st.metric("Total de Profs com Turma Cadastrada", total_professores)


with col3:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;"> Total de Profs <br> com Turmas <br> Avançando </span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_professores}</span>
        </div>
        """, unsafe_allow_html=True)
    # st.metric("Total de Profs com Turma Cadastrada", total_professores)


with col4:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;"> Total de Turmas <br>Com Evidência <br> de Aprendizagem </span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_turmas}</span>
        </div>
        """, unsafe_allow_html=True)
    
with col5:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;">Profs com Turmas<br>Evid. de Aprend. maior<br> que 50 %</span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_professores_50}</span>
        </div>
        """, unsafe_allow_html=True)

# st.markdown(f"#### Quantidade de Turmas Únicas com evidência de aprendizagem: {total_turmas}")

with st.expander("Clique aqui para os dados das turmas com evidência de aprendizagem"):
    st.dataframe(turmas)

#print(f"Percentual total de alunos que melhoraram (excluindo turmas sem melhoria): {percentual_total_melhoria:.2f}%")


# total_alunos = turmas['id_aluno'].nunique()
# st.markdown(f"#### Quantidade de alunos Únicos cadastrados: {total_alunos}")

# Número de sondagens por mês
df_sondagens_diarias = turmas.groupby(turmas['mes_sondagem']).size().reset_index(name='total_sondagens')
df_sondagens_diarias = df_sondagens_diarias.sort_values(by='mes_sondagem')

fig_sondagens_diarias = go.Figure(data=[go.Scatter(x=df_sondagens_diarias['mes_sondagem'], y=df_sondagens_diarias['total_sondagens'])])
fig_sondagens_diarias.update_layout(title='Número de Sondagens Realizadas', xaxis_title='Mês', yaxis_title='Número de Sondagens')

st.plotly_chart(fig_sondagens_diarias, use_container_width=True)

# Número de professores que realizaram sondagens por mês
df_professores_sondagens_diarias = turmas.groupby(turmas['mes_sondagem'])['id_professor'].nunique().reset_index(name='total_professores')
df_professores_sondagens_diarias = df_professores_sondagens_diarias.sort_values(by='mes_sondagem')

fig_professores_sondagens_diarias = go.Figure(data=[go.Bar(x=df_professores_sondagens_diarias['mes_sondagem'], y=df_professores_sondagens_diarias['total_professores'])])
fig_professores_sondagens_diarias.update_layout(title='Número de Professores(únicos) que Realizaram Sondagens', xaxis_title='Mês', yaxis_title='Número de Professores')

st.plotly_chart(fig_professores_sondagens_diarias, use_container_width=True)

# Número de turmas que realizaram sondagens por mês
df_turmas_sondagens_diarias = turmas.groupby(turmas['mes_sondagem'])['id_turma'].nunique().reset_index(name='total_turmas')
df_turmas_sondagens_diarias = df_turmas_sondagens_diarias.sort_values(by='mes_sondagem')

fig_turmas_sondagens_diarias = go.Figure(data=[go.Bar(x=df_turmas_sondagens_diarias['mes_sondagem'], y=df_turmas_sondagens_diarias['total_turmas'])])
fig_turmas_sondagens_diarias.update_layout(title='Número de Turmas que Realizaram Sondagens', xaxis_title='Mês', yaxis_title='Número de Turmas')

st.plotly_chart(fig_turmas_sondagens_diarias, use_container_width=True)


# Crie um GeoDataFrame com os dados
gdf = gpd.GeoDataFrame(turmas, geometry=gpd.points_from_xy(turmas['cidade_escola'], turmas['estado_escola']))

# Geocodifique os campos cidade_escola e estado_escola
gdf = gdf.assign(geometry=gpd.tools.geocode(gdf['cidade_escola'] + ', ' + gdf['estado_escola']))

# Crie o mapa
layers = [
    pdk.Layer(
        "ScatterplotLayer",
        gdf,
        pickable=True,
        opacity=0.8,
        stroked=True,
        filled=True,
        radius_scale=6,
        radius_min_pixels=1,
        radius_max_pixels=100,
        line_width_min_pixels=1,
        get_position='[geometry.x, geometry.y]',
        get_radius='total_turmas',
        get_fill_color=[255, 140, 0], # Laranja
        get_line_color=[0, 0, 0] # Preto
    )
]

r = pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=-14, longitude=-53, zoom=4, pitch=0))

# Exiba o mapa
st.pydeck_chart(r)
