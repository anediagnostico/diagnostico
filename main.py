# Description: Script para gerar um relatório de diagnóstico com informações de logins, onboardings, alunos e turmas.

import os
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine 
import pymysql
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)
import plotly.express as px
import plotly.graph_objects as go

load_dotenv()
# ------------------------- CONEXÃO COM O BANCO DE DADOS -----------------
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
database = os.getenv('DB_NAME')

connection_string = f'mysql+pymysql://{user}:{password}@{host}/{database}'
engine = create_engine(connection_string)

user_1 = os.getenv('DB_USER_DASH')
password_1 = os.getenv('DB_PASSWORD_DASH')
host_1 = os.getenv('DB_HOST_DASH')
database_1 = os.getenv('DB_DATABASE_DASH')

connection_string_ne = f'mysql+pymysql://{user_1}:{password_1}@{host_1}/{database_1}'
engine_ne = create_engine(connection_string_ne)
# ------------------------- TESTE DE CONEXÃO ---------------------------
# try:
#     engine = create_engine(connection_string_cdc)
#     connection = engine.connect()
#     print("Conexão bem-sucedida!")
#     connection.close()
# except Exception as e:
#     print(f"Erro ao conectar ao banco de dados: {e}")

# ------------------------- INTERFACE GRÁFICA --------------------------

st.set_page_config(
    page_title="Relatório de Sondagens Diagnósticas",  
    page_icon="📊", 
    layout="wide",  
    initial_sidebar_state="expanded",  
)
st.markdown("## Dados Gerais da Sondagem Diagnóstica 👩🏾‍🏫")
st.sidebar.markdown("# Dados de Diagnóstico")
st.sidebar.markdown('## Filtros: ')
# modify = st.sidebar.checkbox("Adicionar Filtros")


# ------------------------- SQL QUERIES --------------------------------
logins_query = '''SELECT distinct
    t.id as id_professor,
    t.auth_id as id_nova_escola,
    t.confirmed as confirmado,
    t.active as ativo,
    t.created_at as data_criacao,
    t.updated_at as data_atualizacao,
    t.onboarding_completed as onboarding_completo
FROM teacher t
WHERE t.auth_id NOT IN ('3','6','18','64','1466346', '1581795','175689','1980922','2051263','2241909','2347872','2607842','2988478','3457137','3693288','3693431','3912304','4681737','4813648','5106338','5326020','5331581','5722986','5726715','5740041','5844577','6132779', '6183405', '6361801','6447188','6470829','6491287')'''


onboardings_query = "SELECT COUNT(t.auth_id) AS total_onboardings FROM teacher t WHERE t.onboarding_completed = 1 AND t.auth_id NOT IN ('3','6','18','64','1466346', '1581795','175689','1980922','2051263','2241909','2347872','2607842','2988478','3457137','3693288','3693431','3912304','4681737','4813648','5106338','5326020','5331581','5722986','5726715','5740041','6132779', '6183405', '6361801','6447188','6470829','6491287');"
students_query = "SELECT COUNT(distinct s.id) AS total_students FROM student s WHERE s.active = 1;"
diagnostics_query = "SELECT COUNT(distinct da.id) AS total_diagnosis FROM diagnostic_assessment da;"	
classes_query = "SELECT COUNT(distinct cl.id) AS total_classes FROM class cl;"
students_by_class_query = """SELECT
    t.id AS id_professor,
    c.id AS id_turma,
    c.name AS nome_turma,
    c.year AS ano_turma,
    s.id AS id_aluno,
    s.name AS nome_aluno,
    sc.cod_inep AS cod_inep,
    sc.name AS nome_escola,
    sc.municipio AS cidade_escola,
    sc.uf AS estado_escola,
    da.id AS id_avaliacao,
    da.month AS mes_avaliacao,
    dh.id AS hipotese,
    dh.name AS nome_hipotese,
    MAX(das.comment) AS comentario,
    MAX(da.created_at) AS data_criacao_avaliacao
FROM
    teacher t
INNER JOIN
    diagnostic_assessment da ON t.id = da.teacher_id
INNER JOIN
    class c ON c.id = da.class_id
INNER JOIN
    student s ON s.class_id = c.id
INNER JOIN
    diagnostic_assessment_students das ON das.student_id = s.id
INNER JOIN
    diagnostic_assessment_type_hypothesis dh ON dh.id = das.hypothesis_id
INNER JOIN
    school sc ON sc.cod_inep = c.cod_inep
GROUP BY
    t.id, c.id, c.name, c.year, s.id, s.name, sc.cod_inep, sc.name, sc.municipio, sc.uf, da.id, da.month, dh.id, dh.name
ORDER BY
    data_criacao_avaliacao DESC;"""

evolucao_total = '''SELECT
    das.student_id AS id_aluno,
    s.name AS nome_aluno,
    MIN(dh.ordering) AS ordem_inicial,
    MAX(dh.ordering) AS ordem_final,
    MIN(dh.name) AS estado_inicial,
    MAX(dh.name) AS estado_final,
    MIN(das.created_at) AS data_inicial,
    MAX(das.created_at) AS data_final
FROM
    diagnostic_assessment_students das
INNER JOIN
    student s ON das.student_id = s.id
INNER JOIN
    diagnostic_assessment_type_hypothesis dh ON das.hypothesis_id = dh.id
GROUP BY
    das.student_id, s.name
HAVING
    MIN(dh.ordering) <> MAX(dh.ordering)  -- Verifica se houve evolução
ORDER BY
    nome_aluno;'''

alunos_evolucao = '''SELECT
    COUNT(*) AS total_students_with_evolution
FROM (
    SELECT
        das.student_id
    FROM
        diagnostic_assessment_students das
    INNER JOIN
        diagnostic_assessment_type_hypothesis dh ON das.hypothesis_id = dh.id
    GROUP BY
        das.student_id
    HAVING
        MIN(dh.ordering) <> MAX(dh.ordering)
        AND COUNT(DISTINCT das.created_at) > 1 
) AS evolved_students;'''

alunos_distintos_evolucao = '''SELECT
    COUNT(DISTINCT das.student_id) AS total_alunos_distintos_com_evolucao
FROM
    diagnostic_assessment_students das
INNER JOIN
    student s ON das.student_id = s.id
INNER JOIN
    diagnostic_assessment_type_hypothesis dh ON das.hypothesis_id = dh.id
GROUP BY
    das.student_id
HAVING
    MIN(dh.ordering) <> MAX(dh.ordering);'''

professores_mais_de_uma_turma = '''SELECT
    COUNT(DISTINCT t.id) AS total_teachers_with_multiple_classes
FROM
    teacher t
INNER JOIN
    class c ON t.id = c.teacher_id
GROUP BY
    t.id
HAVING
    COUNT(c.id) > 1;'''

turmas_mais_de_uma_sondagem = '''SELECT
    COUNT(DISTINCT da.class_id) AS total_classes_with_multiple_assessments
FROM
    diagnostic_assessment da
GROUP BY
    da.class_id
HAVING
    COUNT(da.id) > 1;
'''

rank_hipoteses = '''WITH ranked_hypotheses AS (
    SELECT
        das.student_id,
        s.name AS nome_aluno,
        s.class_id,
        c.name AS nome_turma,
        c.year AS ano_turma,
        sc.cod_inep AS cod_inep,
        sc.name AS nome_escola,
        sc.municipio AS cidade_escola,
        sc.uf AS estado_escola,
        dh.name AS nome_hipotese,
        da.created_at,
        ROW_NUMBER() OVER(PARTITION BY das.student_id ORDER BY da.created_at ASC) AS rn
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
        school sc ON c.cod_inep = sc.cod_inep
)
SELECT
    rh.student_id,
    rh.nome_aluno,
    rh.nome_turma,
    rh.ano_turma,
    rh.cod_inep,
    rh.nome_escola,
    rh.cidade_escola,
    rh.estado_escola,
    rh.nome_hipotese,
    rh.created_at,
    rh.rn
FROM
    ranked_hypotheses rh
ORDER BY
    rh.student_id, rh.rn;
'''

alunos_com_evolucao = '''WITH alunos_totais AS (
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
        t.id AS professor_id,  -- Incluir o ID do professor
        MIN(dh.ordering) AS min_ordering,
        MAX(dh.ordering) AS max_ordering
    FROM 
        diagnostic_assessment_students das
    INNER JOIN 
        student s ON das.student_id = s.id
    INNER JOIN 
        class c ON s.class_id = c.id
    INNER JOIN
        teacher t ON t.id = c.teacher_id  -- Associação entre professor e turma
    INNER JOIN 
        diagnostic_assessment_type_hypothesis dh ON das.hypothesis_id = dh.id
    GROUP BY 
        s.id, c.id, t.id
),
alunos_com_melhoria AS (
    SELECT 
        turma_id,
        professor_id,
        COUNT(aluno_id) AS alunos_com_melhoria
    FROM 
        alunos_melhoria
    WHERE 
        min_ordering < max_ordering  -- Filtra alunos que melhoraram de nível
    GROUP BY 
        turma_id, professor_id
)
SELECT 
    t.turma_id,
    t.nome_turma,
    t.professor_id,  -- Incluir o ID do professor
    t.total_alunos,
    COALESCE(m.alunos_com_melhoria, 0) AS alunos_com_melhoria,
    ROUND((COALESCE(m.alunos_com_melhoria, 0) / t.total_alunos) * 100, 2) AS porcentagem_melhoria
FROM 
    alunos_totais t
LEFT JOIN 
    alunos_com_melhoria m ON t.turma_id = m.turma_id
WHERE 
    COALESCE(m.alunos_com_melhoria, 0) > 0;'''


# ------------------------- LEITURA DOS DADOS --------------------------
logins_1 = pd.read_sql(logins_query, engine)
onboardings = pd.read_sql(onboardings_query, engine)
students = pd.read_sql(students_query, engine)
diagnosis = pd.read_sql(diagnostics_query, engine)
classes = pd.read_sql(classes_query, engine)
students_by_class = pd.read_sql(students_by_class_query, engine)
evolucao = pd.read_sql(evolucao_total, engine)
contagem_evolucao = pd.read_sql(alunos_evolucao, engine)
contagem_distinta_evolucao = pd.read_sql(alunos_distintos_evolucao, engine)
contagem_professores_mais_de_uma_turma = pd.read_sql(professores_mais_de_uma_turma, engine)
contagem_turmas_mais_de_uma_sondagem = pd.read_sql(turmas_mais_de_uma_sondagem, engine) 
rank_hipoteses = pd.read_sql(rank_hipoteses, engine)
alunos_evolucao = pd.read_sql(alunos_com_evolucao, engine)
# ------------------------- FILTRAGEM DE DADOS -------------------------
def format_integers(df: pd.DataFrame) -> pd.DataFrame:
    # Itera pelas colunas do DataFrame e converte para int se possível
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            if (df[col] == df[col].astype(int)).all():
                df[col] = df[col].astype(int)
    return df

def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # Cria um checkbox com uma chave única
    modify = st.sidebar.checkbox("Adicionar Filtros", key="filter_checkbox")

    if not modify:
        return df

    df = df.copy()

    # Tratamento especial para colunas numéricas que são inteiras
    for col in df.columns:
        
        if is_object_dtype(df[col]) and df[col].str.contains(r'\d{4}/\d{2}').all():
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

        # Aqui tratamos os inteiros para garantir que não sejam exibidos com vírgulas
        if is_numeric_dtype(df[col]) and (df[col] == df[col].astype(int)).all():
            df[col] = df[col].astype(int)

    modification_container = st.sidebar.container()

    with modification_container:
        # Gera uma chave única para o multiselect usando o nome do DataFrame
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
                    key=f"multiselect_{column}_{i}"  # Chave única para cada coluna
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
                    key=f"slider_{column}_{i}"  # Chave única para cada coluna
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f"Values for {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                    key=f"date_input_{column}_{i}"  # Chave única para cada coluna
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Digite uma substring pelo que quer filtrar de {column}",
                    key=f"text_input_{column}_{i}"  # Chave única para cada coluna
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input)]

    return df
# ------------------------- RELATÓRIO ----------------------------------

# st.markdown("### Login e Onboarding")
logins = filter_dataframe(logins_1)
total_logins = logins['id_professor'].nunique()
df_onboardings = logins[logins['onboarding_completo'] == 1]
total_onboardings = df_onboardings['id_professor'].nunique()

# st.markdown(f"#### Quantidade de Professores Únicos com Onboarding completo na Ferramenta: {total_onboardings}")
# st.markdown(f"#### Quantidade de Professores Únicos que fizeram login na Ferramenta: {total_logins}")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;">Total de Logins<br>Únicos</span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_logins}</span>
        </div>
        """, unsafe_allow_html=True)
    # st.metric("Total de Logins Únicos", total_logins)

with col2:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;">Total de Onboardings<br>Únicos</span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_onboardings}</span>
        </div>
        """, unsafe_allow_html=True)
    # st.metric("Total de Onboardings", total_onboardings)


logins['data_criacao'] = pd.to_datetime(logins['data_criacao'])

df_grouped = logins.groupby(logins['data_criacao'].dt.date)['id_professor'].nunique().reset_index(name='total_professores')

# st.title("Relatório de Professores - Uso e Cadastramento")

fig_1 = px.bar(df_grouped, x='data_criacao', y='total_professores', 
             title='Quantidade de Professores Cadastrados por Dia (Únicos)',
             labels={'data_criacao': 'Data de Cadastro', 'total_professores': 'Total de Professores'},
             text='total_professores',
             color_discrete_sequence=['#63666A'])

fig_1.update_layout(
    xaxis_tickangle=-45,
    height=600,  
    xaxis=dict(
        tickmode='auto',  
        nticks=20 
    ),
    yaxis=dict(
        title="Total de Professores",  
        gridcolor="LightGrey"  
    )
)

fig_1.update_traces(texttemplate='%{text:.2s}', textposition='outside')

st.plotly_chart(fig_1)

with st.expander("Clique aqui para os dados de professores únicos"):
    st.dataframe(logins)

with st.expander("Clique aqui para os dados de contagem de professores únicos por dia"):
    st.dataframe(df_grouped)

df_grouped_2 = df_onboardings.groupby(df_onboardings['data_criacao'].dt.date)['id_professor'].nunique().reset_index(name='total_professores')

# fig_2 = px.bar(df_grouped_2, x='data_criacao', y='total_professores', 
#              title='Quantidade de Professores com Onboarding Completo por Dia (Únicos)',
#              labels={'data_criacao': 'Data de Cadastro', 'total_professores': 'Total de Professores'},
#              text='total_professores')

# st.plotly_chart(fig_2)


fig_2 = px.bar(df_grouped_2, x='data_criacao', y='total_professores', 
             title='Quantidade de Professores com Onboarding Completo por Dia (Únicos)',
             labels={'data_criacao': 'Data de Cadastro', 'total_professores': 'Total de Professores'},
             text='total_professores',
             color_discrete_sequence=['#63666A'])

fig_2.update_layout(
    xaxis_tickangle=-45,
    height=600,  
    xaxis=dict(
        tickmode='auto',  
        nticks=20 
    ),
    yaxis=dict(
        title="Total de Professores",  
        gridcolor="LightGrey"  
    )
)

fig_2.update_traces(texttemplate='%{text:.2s}', textposition='outside')

st.plotly_chart(fig_2)

with st.expander("Clique aqui para acessar os dados de professores com onboarding completo."):
    st.dataframe(df_onboardings)
# st.write("Quantidade de Sondagens totais realizadas:", diagnosis['total_diagnosis'].iloc[0])
# st.write("Quantidade de Alunos Únicos Inscritos na Ferramenta:", students['total_students'].iloc[0])
# st.write("Quantidade de Turmas Únicas cadastradas na Ferramenta:", classes['total_classes'].iloc[0])
# st.write("Quantidade de Turmas com Mais de 1 Sondagem realizada:", contagem_turmas_mais_de_uma_sondagem['total_classes_with_multiple_assessments'].sum())

# st.subheader("Alunos por Turma e Professor")
# filtered = filter_dataframe(students_by_class)


# df = format_integers(filtered)
# df['id_professor'] = df['id_professor'].astype(int)
# df['id_turma'] = df['id_turma'].astype(int)
# df['ano_turma'] = df['ano_turma'].astype(int)
# df['id_aluno'] = df['id_aluno'].astype(int)
# df['cod_inep'] = df['cod_inep'].astype(int)
# df['id_avaliacao'] = df['id_avaliacao'].astype(int)

# df['id_professor'] = df['id_professor'].apply(lambda x: f'{x:,}'.replace(',', ''))
# df['id_turma'] = df['id_turma'].apply(lambda x: f'{x:,}'.replace(',', ''))
# df['ano_turma'] = df['ano_turma'].apply(lambda x: f'{x:,}'.replace(',', ''))
# df['id_aluno'] = df['id_aluno'].apply(lambda x: f'{x:,}'.replace(',', ''))
# df['cod_inep'] = df['cod_inep'].apply(lambda x: f'{x:,}'.replace(',', ''))
# df['id_avaliacao'] = df['id_avaliacao'].apply(lambda x: f'{x:,}'.replace(',', ''))

# with st.expander("Clique aqui para visualizar os microdados"):
#     st.dataframe(df)


# st.write("Resumo dos Dados Filtrados:")


# total_alunos = df['id_aluno'].nunique()
# st.write(f"Total de Alunos: {total_alunos}")


# total_turmas = df['id_turma'].nunique()
# st.write(f"Total de Turmas: {total_turmas}")


# total_escolas = df['cod_inep'].nunique()
# st.write(f"Total de Escolas: {total_escolas}")


# resumo_hipoteses = df.groupby('id_aluno')['nome_hipotese'].first().value_counts()
# st.write("Resumo de Hipóteses (Alunos Únicos):")
# st.dataframe(resumo_hipoteses)

# st.title("Dados por Hipótese Atribuída aos Alunos")
# st.dataframe(rank_hipoteses)

# st.title("Evolução dos Alunos com Datas")
# st.write("Aqui estão os alunos que mostraram evolução ao longo do tempo:")
# evolucao['id_aluno'] = evolucao['id_aluno'].astype(int) 
# evolucao['id_aluno'] = evolucao['id_aluno'].apply(lambda x: f'{x:,}'.replace(',', ''))

# st.dataframe(evolucao)

# st.title("Evolução dos Alunos")
# st.dataframe(contagem_evolucao)

# st.title("Evolução dos Alunos")
# total_students_with_evolution = len(contagem_distinta_evolucao)
# st.write(f"Total de alunos distintos com evolução: {total_students_with_evolution}")

# st.title("Professores com mais de uma turma")
# total_profs_mais = len(contagem_professores_mais_de_uma_turma)
# st.write(f"Total de professores com mais de uma turma: {total_profs_mais}")

# st.title("Total de Trumas com mais de uma sondagem")
# total_turmas_mais = len(contagem_turmas_mais_de_uma_sondagem)
# st.write(f"Total de turmas com mais de uma sondagem: {total_turmas_mais}")

# st.title("Porcentagem da evolução dos alunos por turma")
# st.dataframe(alunos_evolucao)

# df_filtrado = alunos_evolucao[alunos_evolucao['alunos_com_melhoria'] > 0]

# total_alunos = df_filtrado['total_alunos'].sum()
# total_melhorias = df_filtrado['alunos_com_melhoria'].sum()

# if total_alunos > 0:
#     percentual_total_melhoria = (total_melhorias / total_alunos) * 100
# else:
#     percentual_total_melhoria = 0 

# #print(f"Percentual total de alunos que melhoraram (excluindo turmas sem melhoria): {percentual_total_melhoria:.2f}%")

