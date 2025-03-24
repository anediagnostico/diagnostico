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

##################################################################
## Adicionando filtro por estado

# Aplica filtros iniciais
turmas = df.copy()
turmas['data_cadastro_professor'] = pd.to_datetime(turmas['data_cadastro_professor'])
turmas['data_cadastro_turma'] = pd.to_datetime(turmas['data_cadastro_turma'])
turmas['data_cadastro_aluno'] = pd.to_datetime(turmas['data_cadastro_aluno'])

# Primeiro aplica o filtro interativo da sidebar
turmas = filter_dataframe(turmas)  # Aqui aplicamos os filtros da sidebar

# Depois aplica o filtro por estado
estado_escolha = st.multiselect(
    "Selecione o estado:",
    ["Todos"] + turmas["estado_escola"].unique().tolist()
)

if "Todos" in estado_escolha:
    turmas_filtradas = turmas
else:
    turmas_filtradas = turmas[turmas["estado_escola"].isin(estado_escolha)]


##################################################################

st.markdown("## Dados de Professores")
total_professores = turmas_filtradas[turmas_filtradas['id_professor'] != 0]['id_professor'].nunique()
total_turmas = turmas_filtradas[turmas_filtradas['id_turma'] != 0]['id_turma'].nunique()
total_alunos = turmas_filtradas[turmas_filtradas['id_aluno'] != 0]['id_aluno'].nunique()


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

# Aplica as conversões de data no dataframe já filtrado
turmas_filtradas['data_cadastro_professor'] = pd.to_datetime(turmas_filtradas['data_cadastro_professor'])
turmas_filtradas['data_cadastro_turma'] = pd.to_datetime(turmas_filtradas['data_cadastro_turma'])
turmas_filtradas['data_cadastro_aluno'] = pd.to_datetime(turmas_filtradas['data_cadastro_aluno'])

# Agrupa os dados filtrados
df_grouped = turmas_filtradas.groupby(turmas_filtradas['data_cadastro_professor'].dt.date)['id_professor'].nunique().reset_index(name='total_professores')

# Mostra os dataframes filtrados
with st.expander("Clique aqui para os dados das turmas cadastradas"):
    st.dataframe(turmas_filtradas)

with st.expander("Clique aqui para os dados de contagem de turmas únicas por dia"):
    st.dataframe(df_grouped)


# Número de Professores cadastrados por dia
df_professores_ativos = turmas_filtradas.groupby(
    turmas_filtradas['data_cadastro_professor'].dt.date
)['id_professor'].nunique().reset_index(name='total_professores_ativos')

fig_professores_ativos = go.Figure(
    data=[go.Bar(
        x=df_professores_ativos['data_cadastro_professor'],
        y=df_professores_ativos['total_professores_ativos']
    )]
)

fig_professores_ativos.update_layout(
    title='Número de Professores cadastrados por dia',
    xaxis_title='Data',
    yaxis_title='Número de Professores Ativos'
)

st.plotly_chart(fig_professores_ativos, use_container_width=True)

# Tempo médio de cadastro de professores
df_tempo_cadastro = turmas_filtradas.groupby(
    turmas_filtradas['data_cadastro_professor'].dt.date
)['data_cadastro_professor'].apply(
    lambda x: (x.max() - x.min()).total_seconds() / 60
).reset_index(name='tempo_medio_cadastro')

fig_tempo_cadastro = go.Figure(
    data=[go.Bar(
        x=df_tempo_cadastro['data_cadastro_professor'],
        y=df_tempo_cadastro['tempo_medio_cadastro']
    )]
)

fig_tempo_cadastro.update_layout(
    title='Tempo Médio de Cadastro de Professores',
    xaxis_title='Data',
    yaxis_title='Tempo Médio de Cadastro (minutos)'
)

st.plotly_chart(fig_tempo_cadastro, use_container_width=True)

##################################################################

# Professores cadastrados por estado
df_professores_por_estado = turmas_filtradas.groupby('estado_escola')['id_professor'].nunique().reset_index(name='total_professores')

# Ordena pelos estados originais para manter consistência
estados_ordenados = turmas['estado_escola'].unique()
df_professores_por_estado['estado_escola'] = pd.Categorical(
    df_professores_por_estado['estado_escola'],
    categories=estados_ordenados,
    ordered=True
)
df_professores_por_estado = df_professores_por_estado.sort_values('estado_escola')

fig_professores_por_estado = go.Figure(
    data=[go.Bar(
        x=df_professores_por_estado['estado_escola'],
        y=df_professores_por_estado['total_professores'],
        text=df_professores_por_estado['total_professores'],
        textposition='auto'
    )]
)

fig_professores_por_estado.update_layout(
    title='Professores Cadastrados por Estado',
    xaxis_title='Estado',
    yaxis_title='Número de Professores',
    hovermode='x'
)

st.plotly_chart(fig_professores_por_estado, use_container_width=True)

##################################################################

# Taxa de onboarding completo (com filtros aplicados)
total_professores = turmas_filtradas['id_professor'].nunique()
professores_onboarding_completo = turmas_filtradas[turmas_filtradas['flag_onboarding'] == 'Onboarding Completo']['id_professor'].nunique()

# Cálculo seguro da taxa (evita divisão por zero)
taxa_onboarding_completo = (professores_onboarding_completo / total_professores * 100) if total_professores > 0 else 0

# Criação do gráfico de pizza
fig = go.Figure(data=[
    go.Pie(
        labels=['Onboarding Completo', 'Onboarding Não Completo'],
        values=[
            professores_onboarding_completo, 
            max(total_professores - professores_onboarding_completo, 0)  # Garante valor não negativo
        ],
        marker_colors=['#DB7093', '#FFC5C5'],
        hole=0.3,  # Opcional: transforma em gráfico de rosca
        textinfo='percent+value',
        hoverinfo='label+percent+value'
    )
])

fig.update_layout(
    title=f'Taxa de Onboarding Completo: {taxa_onboarding_completo:.2f}% (Base: {total_professores} professores)',
    font=dict(size=14),
    showlegend=True,
    annotations=[dict(
        text=f"Total: {total_professores}",
        showarrow=False,
        font_size=12
    )] if total_professores > 0 else None
)

st.plotly_chart(fig, use_container_width=True)

# Adiciona mensagem se não houver dados
if total_professores == 0:
    st.warning("Nenhum professor encontrado com os filtros selecionados.")

##################################################################


# Turmas por estado (com filtros aplicados)
df_turmas_por_estado = turmas_filtradas.groupby('estado_escola')['id_turma'].nunique().reset_index(name='total_turmas')

# Mantém a ordenação original dos estados
estados_ordenados = [estado for estado in turmas['estado_escola'].unique() if estado in df_turmas_por_estado['estado_escola'].values]
df_turmas_por_estado['estado_escola'] = pd.Categorical(
    df_turmas_por_estado['estado_escola'],
    categories=estados_ordenados,
    ordered=True
)
df_turmas_por_estado = df_turmas_por_estado.sort_values('estado_escola')

# Criação do gráfico de barras
fig = go.Figure(data=[
    go.Bar(
        x=df_turmas_por_estado['estado_escola'],
        y=df_turmas_por_estado['total_turmas'],
        text=df_turmas_por_estado['total_turmas'],
        textposition='auto',
        marker_color='#1f77b4',
        hovertemplate='<b>%{x}</b><br>Turmas: %{y}<extra></extra>'
    )
])

fig.update_layout(
    title=f'Turmas Cadastradas por Estado (Total: {df_turmas_por_estado["total_turmas"].sum()})',
    xaxis_title='Estado',
    yaxis_title='Total de Turmas',
    font=dict(size=12),
    hoverlabel=dict(
        bgcolor="white",
        font_size=12,
        font_family="Arial"
    ),
    plot_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(tickangle=45),
    margin=dict(l=20, r=20, t=60, b=100)
)

# Adiciona rótulos de dados
fig.update_traces(texttemplate='%{text}', textposition='outside')

# Mostra mensagem se não houver dados
if df_turmas_por_estado.empty:
    st.warning("Nenhuma turma encontrada com os filtros selecionados.")
else:
    st.plotly_chart(fig, use_container_width=True)

##################################################################



