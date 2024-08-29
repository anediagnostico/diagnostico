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

load_dotenv()
# ------------------------- CONEXÃO COM O BANCO DE DADOS -----------------
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
database = os.getenv('DB_NAME')

connection_string = f'mysql+pymysql://{user}:{password}@{host}/{database}'
engine = create_engine(connection_string)

# ------------------------- TESTE DE CONEXÃO ---------------------------
# try:
#     engine = create_engine(connection_string)
#     connection = engine.connect()
#     print("Conexão bem-sucedida!")
#     connection.close()
# except Exception as e:
#     print(f"Erro ao conectar ao banco de dados: {e}")

# ------------------------- INTERFACE GRÁFICA --------------------------

st.set_page_config(
    page_title="Relatório de Sondagens",  # Título da aba do navegador
    page_icon="📊",  # Ícone da aba do navegador
    layout="wide",  # Layout amplo
    initial_sidebar_state="expanded",  # Estado inicial da barra lateral (expanded/collapsed)
)
st.markdown("## Dashboard da Sondagem Diagnóstica 🎈")
st.sidebar.markdown("# Página Principal do Relatório 🎈")
st.sidebar.markdown('## Seus filtros estão aqui! ✅')
# modify = st.sidebar.checkbox("Adicionar Filtros")


# ------------------------- SQL QUERIES --------------------------------
logins_query = "SELECT COUNT(distinct t.auth_id) AS total_logins FROM teacher t"
onboardings_query = "SELECT COUNT(t.auth_id) AS total_onboardings FROM teacher t WHERE t.onboarding_completed = 1;"
students_query = "SELECT COUNT(distinct s.id) AS total_students FROM student s WHERE s.active = 1;"
diagnostics_query = "SELECT COUNT(distinct da.id) AS total_diagnosis FROM diagnostic_assessment da;"	
classes_query = "SELECT COUNT(*) AS total_classes FROM class;"
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
        AND COUNT(DISTINCT das.created_at) > 1  -- Garantir que as sondagens ocorreram em diferentes datas
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

# ------------------------- LEITURA DOS DADOS --------------------------
logins = pd.read_sql(logins_query, engine)
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

st.subheader("Métricas Gerais")
st.markdown("#### As métricas abaixo apresentam os totais gerais (sem considerar filtragem de dados):")
st.write("Quantidade de Logins:", logins['total_logins'].iloc[0])
st.write("Quantidade de Onboardings:", onboardings['total_onboardings'].iloc[0])
st.write("Quantidade de Sondagens:", diagnosis['total_diagnosis'].iloc[0])
st.write("Quantidade de Alunos Inscritos:", students['total_students'].iloc[0])
st.write("Quantidade de Turmas:", classes['total_classes'].iloc[0])
st.write("Quantidade de Turmas com Mais de 1 Sondagem:", contagem_turmas_mais_de_uma_sondagem['total_classes_with_multiple_assessments'].sum())

st.subheader("Alunos por Turma e Professor")
filtered = filter_dataframe(students_by_class)


df = format_integers(filtered)
df['id_professor'] = df['id_professor'].astype(int)
df['id_turma'] = df['id_turma'].astype(int)
df['ano_turma'] = df['ano_turma'].astype(int)
df['id_aluno'] = df['id_aluno'].astype(int)
df['cod_inep'] = df['cod_inep'].astype(int)
df['id_avaliacao'] = df['id_avaliacao'].astype(int)

df['id_professor'] = df['id_professor'].apply(lambda x: f'{x:,}'.replace(',', ''))
df['id_turma'] = df['id_turma'].apply(lambda x: f'{x:,}'.replace(',', ''))
df['ano_turma'] = df['ano_turma'].apply(lambda x: f'{x:,}'.replace(',', ''))
df['id_aluno'] = df['id_aluno'].apply(lambda x: f'{x:,}'.replace(',', ''))
df['cod_inep'] = df['cod_inep'].apply(lambda x: f'{x:,}'.replace(',', ''))
df['id_avaliacao'] = df['id_avaliacao'].apply(lambda x: f'{x:,}'.replace(',', ''))

with st.expander("Clique aqui para visualizar os microdados"):
    st.dataframe(df)


st.title("Evolução dos Alunos com Datas")
st.write("Aqui estão os alunos que mostraram evolução ao longo do tempo:")
evolucao['id_aluno'] = evolucao['id_aluno'].astype(int) 
evolucao['id_aluno'] = evolucao['id_aluno'].apply(lambda x: f'{x:,}'.replace(',', ''))

st.dataframe(evolucao)


# Contar o número de alunos com evolução
# total_students_with_evolution = len(contagem_evolucao)

# Exibir o número total e a tabela com detalhes
st.title("Evolução dos Alunos")
st.dataframe(contagem_evolucao)

st.title("Evolução dos Alunos")
total_students_with_evolution = len(contagem_distinta_evolucao)
st.write(f"Total de alunos distintos com evolução: {total_students_with_evolution}")

st.title("Professores com mais de uma turma")
total_profs_mais = len(contagem_professores_mais_de_uma_turma)
st.write(f"Total de professores com mais de uma turma: {total_profs_mais}")

st.title("Total de Trumas com mais de uma sondagem")
total_turmas_mais = len(contagem_turmas_mais_de_uma_sondagem)
st.write(f"Total de turmas com mais de uma sondagem: {total_turmas_mais}")
