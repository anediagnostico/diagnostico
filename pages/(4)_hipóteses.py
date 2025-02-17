import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os 
from dotenv import load_dotenv
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
import plotly.graph_objs as go

load_dotenv()
# ------------------------- CONEXÃO COM O BANCO DE DADOS -----------------
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
database = os.getenv('DB_NAME')

connection_string = f'mysql+pymysql://{user}:{password}@{host}/{database}'
engine = create_engine(connection_string)


query = """
WITH alunos_totais AS (
    SELECT 
        c.id AS turma_id,
        c.name AS nome_turma,
        t.id AS professor_id,
        COUNT(DISTINCT s.id) AS total_alunos
    FROM 
        class c
    INNER JOIN 
        student s ON s.class_id = c.id
    INNER JOIN
        teacher t ON t.id = c.teacher_id
    GROUP BY 
        c.id, c.name, t.id
),
contagem_sondagens AS (
    SELECT 
        c.id AS turma_id,
        COUNT(DISTINCT da.id) AS sondagens_realizadas
    FROM 
        diagnostic_assessment da
    INNER JOIN 
        class c ON da.class_id = c.id
    INNER JOIN 
        teacher t ON da.teacher_id = t.id
    GROUP BY 
        c.id
),
alunos_detalhes AS (
    SELECT 
        s.id AS aluno_id,
        s.name AS nome_aluno,
        c.id AS turma_id,
        c.year AS ano_turma,
        t.id AS professor_id,
        sc.name AS nome_escola,
        sc.municipio AS cidade_escola,
        sc.uf AS estado_escola,
        s.created_at AS data_cadastro_aluno,
        t.onboarding_completed
    FROM 
        student s
    INNER JOIN 
        class c ON s.class_id = c.id
    INNER JOIN 
        teacher t ON t.id = c.teacher_id
    LEFT JOIN 
        school sc ON c.cod_inep = sc.cod_inep
),
ranked_hypotheses AS (
    SELECT
        das.student_id,
        s.name AS nome_aluno,
        s.class_id AS id_turma,
        t.id AS id_professor,
        t.auth_id AS id_nova_escola,
        c.name AS nome_turma,
        c.year AS ano_turma,
        sc.cod_inep AS cod_inep,
        sc.name AS nome_escola,
        sc.municipio AS cidade_escola,
        sc.uf AS estado_escola,
        dh.name AS nome_hipotese,
        da.month AS mes_de_aplicacao,
        da.created_at,
        da.updated_at,
        ROW_NUMBER() OVER(PARTITION BY das.student_id ORDER BY da.created_at ASC) AS num_sondagem
    FROM
        diagnostic_assessment_students das
    INNER JOIN
        diagnostic_assessment da ON das.diagnostic_assessment_id = da.id
    INNER JOIN
        diagnostic_assessment_type_hypothesis dh ON das.hypothesis_id = dh.id
    INNER JOIN
        student s ON das.student_id = s.id
    INNER JOIN
        class c ON s.class_id = c.id
    INNER JOIN
        teacher t ON t.id = c.teacher_id  
    INNER JOIN
        school sc ON c.cod_inep = sc.cod_inep
    WHERE t.auth_id NOT IN ('3','6','18','64','1466346', '1581795','175689','1980922','2051263','2241909','2347872','2607842','2988478','3457137','3693288','3693431','3912304','4681737','4813648','5106338','5326020','5331581','5722986','5726715','5740041','5844577','6132779', '6183405', '6361801','6447188','6470829','6491287')
)
SELECT 
    ad.turma_id AS id_turma,
    ad.ano_turma,
    ad.professor_id AS id_professor,
    ad.nome_escola,
    ad.cidade_escola,
    ad.estado_escola,
    ad.aluno_id AS id_aluno,
    ad.nome_aluno,
    ad.data_cadastro_aluno,
    CASE 
        WHEN ad.onboarding_completed = 1 THEN 'Onboarding Completo'
        ELSE 'Onboarding Não Completo'
    END AS flag_onboarding,
    CASE 
        WHEN ad.turma_id IS NOT NULL THEN 'Tem Turma'
        ELSE 'Sem Turma'
    END AS flag_turma,
    COALESCE(cs.sondagens_realizadas, 0) AS flag_sondagens,  -- Número de sondagens realizadas (0 se nenhuma)
    rh.nome_hipotese,
    rh.mes_de_aplicacao,
    rh.created_at AS data_criacao_sondagem,
    rh.updated_at AS data_atualizacao_sondagem,
    rh.num_sondagem,
    rh.cod_inep
FROM 
    alunos_detalhes ad
LEFT JOIN 
    contagem_sondagens cs ON ad.turma_id = cs.turma_id  -- Contagem de sondagens por turma
LEFT JOIN 
    ranked_hypotheses rh ON ad.aluno_id = rh.student_id  -- Dados de sondagens para cada aluno
ORDER BY 
    ad.turma_id, ad.aluno_id, rh.num_sondagem;
"""
df = pd.read_sql(query, engine)

# tratar colunas que são inteiros
# integer_columns = ['id_aluno', 'id_turma', 'ano_turma', 'num_sondagem']
# for col in integer_columns:
#     if col in df.columns:
#         df[col] = df[col].astype(int)

# função para filtrar o DataFrame
def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    modify = st.sidebar.checkbox("Adicionar Filtros", key="filter_checkbox")

    if not modify:
        return df

    df = df.copy()

    for col in df.columns:
        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

        if is_numeric_dtype(df[col]):
            if df[col].isnull().any():  
                df[col] = df[col].fillna(0) 
            if (df[col] == df[col].astype(int)).all():  
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

# Exibir a página com filtros
st.markdown("## Hipóteses da evidência de aprendizagem ")

filtered_df = filter_dataframe(df)

st.write("Dados Filtrados:")
st.dataframe(filtered_df)

st.write("###Resumo dos Dados Filtrados:")

# Resumo
total_alunos = filtered_df['id_aluno'].nunique()
st.write(f"Total de Alunos: {total_alunos}")

total_turmas = filtered_df['id_turma'].nunique()
st.write(f"Total de Turmas: {total_turmas}")

total_escolas = filtered_df['cod_inep'].nunique()
st.write(f"Total de Escolas: {total_escolas}")

resumo_hipoteses = filtered_df.groupby(['num_sondagem', 'nome_hipotese']).size().unstack(fill_value=0)
st.markdown("### Resumo de Hipóteses por Ranking:")
st.dataframe(resumo_hipoteses)

df = pd.read_sql(query, engine)

# Tratar colunas que são inteiros
integer_columns = ['id_aluno', 'id_turma', 'ano_turma', 'cod_inep', 'num_sondagem']
for col in integer_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce') #Forçando conversão para número, transformando erros em NaN
        df[col] = df[col].fillna(0).astype(int) # Aqui substituindo NaN por 0 e convertendo para inteiro
        #df[col] = df[col].astype(int)

# Função para criar o gráfico de gauge
def criar_gauge(df_filtered, ranking_desejado):
    # Resumo das hipóteses para o ranking desejado
    resumo_hipoteses = df_filtered['nome_hipotese'].value_counts()

    # Calcula o total acumulado das hipóteses
    total_acumulado = resumo_hipoteses.sum()

    # Cria o gráfico de gauge com todas as hipóteses em um único gauge
    steps = []
    annotations = []
    limite_inferior = 0

    colors = ['lightgray', 'gray', 'yellow', 'orange', 'red']

    for i, (hipotese, valor) in enumerate(resumo_hipoteses.items()):
        limite_superior = limite_inferior + valor
        steps.append({
            'range': [limite_inferior, limite_superior],
            'color': colors[i % len(colors)]
        })
        annotations.append(dict(
            x=(limite_inferior + limite_superior) / 2 / total_acumulado,
            y=0.2,
            text=f'{hipotese} ({valor})',
            showarrow=False,
            font=dict(size=10)
        ))
        limite_inferior = limite_superior

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=total_acumulado,
        title={'text': f"Total de Hipóteses - Ranking {ranking_desejado}"},
        gauge={
            'axis': {'range': [None, total_acumulado]},
            'steps': steps,
            'bar': {'color': "black"}
        }
    ))

    # Adiciona anotações ao gráfico
    fig.update_layout(annotations=annotations)

    st.plotly_chart(fig)

# Filtrar o DataFrame para o ranking desejado (num_sondagem=1)
ranking_desejado = 1

# Sidebar para filtros adicionais
st.sidebar.title("Filtros")
selected_turma = st.sidebar.multiselect("Filtrar por Turma:", df['nome_turma'].unique())
selected_escola = st.sidebar.multiselect("Filtrar por Escola:", df['nome_escola'].unique())

# Aplicar filtros
df_filtered = df[df['num_sondagem'] == ranking_desejado]

if selected_turma:
    df_filtered = df_filtered[df_filtered['nome_turma'].isin(selected_turma)]

if selected_escola:
    df_filtered = df_filtered[df_filtered['nome_escola'].isin(selected_escola)]

# Criar e exibir o gráfico de gauge atualizado com os filtros aplicados
# st.title("Visualização do Resumo de Hipóteses por Ranking")
# criar_gauge(df_filtered, ranking_desejado)

# Supondo que você já tenha carregado o DataFrame df com as colunas 'student_id', 'nome_hipotese', e 'num_sondagem'

# Criar um mapeamento para a ordem das hipóteses
ordem_hipoteses = {
    'Não se aplica': 1,
    'Pré-silábica': 2,
    'Silábica s/ valor': 3,
    'Silábica c/ valor': 4,
    'Silábico-alfabética': 5,
    'Alfabética': 6
}

# Adicionar uma coluna de ordem ao DataFrame
df['ordering'] = df['nome_hipotese'].map(ordem_hipoteses)

# Agrupar por aluno e calcular a primeira e a última hipótese
progresso_alunos = df.groupby('id_aluno')['ordering'].agg(['min', 'max'])

# Identificar alunos que tiveram qualquer melhoria
alunos_com_melhoria = progresso_alunos[progresso_alunos['min'] < progresso_alunos['max']]

# Contar o número total de alunos que tiveram melhoria
total_alunos_com_melhoria = len(alunos_com_melhoria)

# Mapeando cada etapa do funil
funil_etapas = {}

for etapa in ordem_hipoteses.keys():
    etapa_order = ordem_hipoteses[etapa]
    alunos_na_etapa = progresso_alunos[(progresso_alunos['min'] < etapa_order) & 
                                       (progresso_alunos['max'] >= etapa_order)]
    funil_etapas[etapa] = len(alunos_na_etapa)


st.write(f"Total de alunos com qualquer melhoria: {total_alunos_com_melhoria}")

st.write("Mapa de Funil de Progressão:")
for etapa, quantidade in funil_etapas.items():
    st.write(f"Alunos que atingiram {etapa}: {quantidade}")

st.dataframe(alunos_com_melhoria)

# Adicionar uma coluna de ordem ao DataFrame
df['ordering'] = df['nome_hipotese'].map(ordem_hipoteses)

# Agrupar por aluno e calcular a primeira e a última hipótese
progresso_alunos = df.groupby('id_aluno')['ordering'].agg(['min', 'max'])

# Identificar alunos que tiveram qualquer melhoria
alunos_com_melhoria_ids = progresso_alunos[progresso_alunos['min'] < progresso_alunos['max']].index

# Filtrar o DataFrame original para esses alunos
alunos_com_melhoria = df[df['id_aluno'].isin(alunos_com_melhoria_ids)]

# Ordenar os dados por aluno e pela ordem das hipóteses (num_sondagem)
alunos_com_melhoria = alunos_com_melhoria.sort_values(by=['id_aluno', 'num_sondagem'])

colunas_selecionadas = [
    'id_aluno', 'nome_aluno', 'nome_turma', 'ano_turma',
    'cod_inep', 'nome_escola', 'cidade_escola', 'estado_escola',
    'nome_hipotese', 'num_sondagem', 'ordering', 'created_at'
]

alunos_com_melhoria_evolucao = alunos_com_melhoria[colunas_selecionadas]

# Exibir a evolução no Streamlit
import streamlit as st

st.write("Evolução Completa dos Alunos com Melhoria:")
st.dataframe(alunos_com_melhoria_evolucao)

from pyecharts import options as opts
from pyecharts.charts import Pie
from streamlit_echarts import st_pyecharts

# Supondo que você já tenha os dados das hipóteses em um DataFrame
import pandas as pd

# Exemplo de dados baseados nas hipóteses dos alunos
hipoteses_resumo = filtered_df.groupby('nome_hipotese').size().reset_index(name='count')

def create_nightingale_chart(df):
    # Ordenar o DataFrame por 'count' em ordem decrescente
    df = df.sort_values(by='count', ascending=False)
    
    pie = (
        Pie()
        .add(
            series_name="Nightingale Chart",
            data_pair=[(row['nome_hipotese'].strip(), row['count']) for _, row in df.iterrows()],
            radius=[20, 120],  # Ajusta o raio para evitar corte dos rótulos
            center=["50%", "45%"],  # Centraliza e ajusta verticalmente o gráfico
            rosetype="area",
        )
        .set_global_opts(
            legend_opts=opts.LegendOpts(pos_bottom="0%"),  # Ajusta a posição da legenda
            toolbox_opts=opts.ToolboxOpts(is_show=True, feature={
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }),
            title_opts=opts.TitleOpts(pos_left="center")  # Centraliza o título
        )
        .set_series_opts(
            label_opts=opts.LabelOpts(formatter="{b}: {c}", position="outside"),  # Garante que os rótulos fiquem fora
            itemstyle_opts=opts.ItemStyleOpts(border_radius=4)
        )
    )
    return pie

import streamlit as st

st.title("Gráfico de Rosas das Hipóteses dos Alunos")

nightingale_chart = create_nightingale_chart(hipoteses_resumo)

st_pyecharts(nightingale_chart)