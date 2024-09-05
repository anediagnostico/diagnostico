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

query = '''WITH alunos_totais AS (
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
    GROUP BY 
        s.id, c.id, t.id
),
alunos_com_melhoria AS (
    SELECT 
        turma_id,
        ano_turma,
        cod_inep_turma,
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
    ROUND((COALESCE(m.alunos_com_melhoria, 0) / t.total_alunos) * 100, 2) AS porcentagem_melhoria
FROM 
    alunos_totais t
LEFT JOIN 
    alunos_com_melhoria m ON t.turma_id = m.turma_id
INNER JOIN
    school sc ON m.cod_inep_turma = sc.cod_inep

WHERE 
    COALESCE(m.alunos_com_melhoria, 0) > 0;'''

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