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

query = '''SELECT
    t.id AS id_professor,
    t.auth_id AS id_nova_escola,
    t.created_at AS data_cadastro_professor,
    CASE 
        WHEN t.onboarding_completed = 1 THEN 'Onboarding Completo'
        ELSE 'Onboarding Não Completo'
    END AS flag_onboarding,
    CASE 
        WHEN c.id IS NOT NULL THEN 'Tem Turma'
        ELSE 'Sem Turma'
    END AS flag_turma,
    c.id AS id_turma,
    c.name AS nome_turma,
    c.year AS ano_turma,
    c.created_at AS data_cadastro_turma,
    s.id AS id_aluno,
    s.name AS nome_aluno,
    sc.name AS nome_escola,
    sc.municipio AS cidade_escola,
    sc.uf AS estado_escola,
    s.created_at AS data_cadastro_aluno
FROM
    teacher t
LEFT JOIN
    class c ON t.id = c.teacher_id  
LEFT JOIN
    student s ON s.class_id = c.id  
LEFT JOIN 
    school sc ON c.cod_inep = sc.cod_inep
WHERE t.auth_id NOT IN ('3','6','18','64','1466346', '1581795','5844577','5273215','6317922', '5844577','175689','1980922','2051263','2241909','2347872','2607842','2988478','3457137','3693288','3693431','3912304','4681737','4813648','5106338','5326020','5331581','5722986','5726715','5740041','6132779', '6183405', '6361801','6447188','6470829','6491287')
ORDER BY
    t.id, c.id, s.id;'''

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

df = pd.read_sql(query, engine)

st.markdown("## Dados de Professores")
turmas = filter_dataframe(df)
total_professores = turmas[turmas['id_professor'] != 0]['id_professor'].nunique()
total_turmas = turmas[turmas['id_turma'] != 0]['id_turma'].nunique()
total_alunos = turmas[turmas['id_aluno'] != 0]['id_aluno'].nunique()

col1, col2, col3, col4, col5 = st.columns(5)

with col3:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;">Total Geral<br>de Professores</span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_professores}</span>
        </div>
        """, unsafe_allow_html=True)
    # st.metric("Total de Profs com Turma Cadastrada", total_professores)

with col2:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;">Total Geral de Turmas<br>Cadastradas</span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_turmas}</span>
        </div>
        """, unsafe_allow_html=True)
    # st.metric("Total Geral de Turmas", total_turmas)

with col1:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;">Total Geral de Alunos<br>Cadastrados</span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_alunos}</span>
        </div>
        """, unsafe_allow_html=True)
    # st.metric("Total de Alunos Cadastrados", total_alunos)


# st.markdown(f"#### Quantidade de Professores Únicos com Turma cadastrada: {total_professores}")


# st.markdown(f"#### Quantidade de Turmas Únicas cadastradas: {total_turmas}")


# st.markdown(f"#### Quantidade de alunos Únicos cadastrados: {total_alunos}")

turmas['data_cadastro_professor'] = pd.to_datetime(turmas['data_cadastro_professor'])
turmas['data_cadastro_turma'] = pd.to_datetime(turmas['data_cadastro_turma'])
turmas['data_cadastro_aluno'] = pd.to_datetime(turmas['data_cadastro_aluno'])

df_grouped = turmas.groupby(turmas['data_cadastro_professor'].dt.date)['id_professor'].nunique().reset_index(name='total_professores')

with st.expander("Clique aqui para os dados das turmas cadastradas"):
    st.dataframe(turmas)


with st.expander("Clique aqui para os dados de contagem de turmas únicas por dia"):
    st.dataframe(df_grouped)

# Adicionando gráficos de linhas com número de professores cadastrados por dia
df_grouped = turmas.groupby(turmas['data_cadastro_professor'].dt.date)['id_professor'].nunique().reset_index(name='total_professores')

# Criando o gráfico de linhas
fig = go.Figure(data=[go.Scatter(x=df_grouped['data_cadastro_professor'], y=df_grouped['total_professores'])])
fig.update_layout(title='Número de Professores Cadastrados por Dia',
                   xaxis_title='Data',
                   yaxis_title='Número de Professores')

# Exibindo o gráfico
st.plotly_chart(fig, use_container_width=True)