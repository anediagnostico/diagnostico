import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os 
from dotenv import load_dotenv
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
import plotly.graph_objs as go
import plotly.express as px

load_dotenv()
# ------------------------- CONEXÃO COM O BANCO DE DADOS -----------------
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
database = os.getenv('DB_NAME')

connection_string = f'mysql+pymysql://{user}:{password}@{host}/{database}'
engine = create_engine(connection_string)

query = '''WITH respostas_por_professor AS (
    SELECT 
        t.id AS id_professor,
        t.auth_id AS id_nova_escola,
        COUNT(a.id) AS num_respostas
    FROM 
        questionnaire_answer a
    JOIN 
        questionnaire_response qr ON a.response_id = qr.id
    JOIN 
        teacher t ON qr.teacher_id = t.id
    JOIN 
        questionnaire_question q ON a.question_id = q.id  
    JOIN 
        questionnaire qn ON qr.questionnaire_id = qn.id
    JOIN 
        questionnaire_type qt ON qn.type_id = qt.id
    GROUP BY 
        t.id
)
SELECT 
    t.id AS id_professor,
    t.auth_id AS id_nova_escola,
    q.label AS pergunta,
    a.value AS resposta,
    qr.created_at AS data_resposta,
    CASE 
        WHEN rp.num_respostas >= 3 THEN 'Respondeu todas'
        ELSE 'Não respondeu todas'
    END AS status_resposta
FROM 
    questionnaire_answer a
JOIN 
    questionnaire_response qr ON a.response_id = qr.id
JOIN 
    teacher t ON qr.teacher_id = t.id
JOIN 
    questionnaire_question q ON a.question_id = q.id  -- Usar question_id em vez de option_id
JOIN 
    questionnaire qn ON qr.questionnaire_id = qn.id
JOIN 
    questionnaire_type qt ON qn.type_id = qt.id
JOIN 
    respostas_por_professor rp ON t.id = rp.id_professor
WHERE 
    qt.name = 'Onboarding' AND
    t.auth_id NOT IN ('3','6','18','64','1466346', '1581795','5844577','5273215', '6317922', '5844577','175689','1980922','2051263','2241909','2347872','2607842','2988478','3457137','3693288','3693431','3912304','4681737','4813648','5106338','5326020','5331581','5722986','5726715','5740041','6132779', '6183405', '6361801','6447188','6470829','6491287')
ORDER BY 
    t.id, qr.created_at;'''

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

onboardings = filter_dataframe(df)
respondeu_todas = onboardings[onboardings['status_resposta'] == 'Respondeu todas']
nao_respondeu_todas = onboardings[onboardings['status_resposta'] == 'Não respondeu todas']


st.markdown("## Dados do Onboarding dos Professores 🎓")

col1, col2, col3, col4, col5 = st.columns(5)

total_professores = respondeu_todas['id_professor'].nunique()
total_professores_n = nao_respondeu_todas['id_professor'].nunique()

with col1:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;"> Total de Professores <br> Embarcando</span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_professores}</span>
        </div>
        """, unsafe_allow_html=True)
    
with col2:
    st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 14px;"> Total de Professores <br> que não Embarcaram </span><br>
            <span style="font-size: 36px; font-weight: bold;">{total_professores_n}</span>
        </div>
        """, unsafe_allow_html=True)
    
with st.expander("Clique aqui para os dados dos Professores com Onboarding completo"):
    st.dataframe(respondeu_todas)


resumo_respostas = respondeu_todas.groupby(['pergunta', 'resposta']).size().reset_index(name='count')
resumo_respostas['resposta_ajustada'] = resumo_respostas['resposta'].replace({
    'Falta de conhecimento do que fazer após a sondagem': 'Falta de conhecimento<br>do que fazer<br>após a sondagem',
    'Falta de conhecimento sobre sondagem': 'Falta de conhecimento<br>sobre sondagem',
    'Falta de materiais práticos para realizar a sondagem': 'Falta de materiais<br>práticos para<br>realizar a sondagem',
    'Falta de visibilidade do nível da turma': 'Falta de visibilidade<br>do nível da turma',
    'Não tenho dificuldade com sondagem': 'Não tenho dificuldade<br>com sondagem'
})


fig1 = px.bar(
    resumo_respostas[resumo_respostas['pergunta'] == '1) Nos últimos 6 meses, com que frequência você realizou uma sondagem com sua turma?'], 
    x='resposta', 
    y='count', 
    title='1) Nos últimos 6 meses, com que frequência você realizou uma sondagem com sua turma?', 
    height=400
)


fig1.update_traces(
    texttemplate='%{y}',  
    textposition='inside'  
)

fig1.update_layout(
    xaxis_tickangle=0,  
    height=600,  
    xaxis=dict(
        tickmode='auto',  
        nticks=20 
    ),
    yaxis=dict(
        title="Contagem de Respostas",  
        gridcolor="LightGrey"  
    ), 
    bargap=0.3
)



fig2 = px.bar(
    resumo_respostas[resumo_respostas['pergunta'] == '2) Você se sente confiante para realizar uma sondagem com a sua turma?'], 
    x='resposta', 
    y='count', 
    title='2) Você se sente confiante para realizar uma sondagem com a sua turma?', 
    labels={'resposta': 'Respostas', 'count': 'Contagem'},
    height=400
)


fig2.update_traces(
    texttemplate='%{y}',  
    textposition='inside'  
)

fig2.update_layout(
    xaxis_tickangle=0,  
    height=600,  
    xaxis=dict(
        tickmode='auto',  
        nticks=20 
    ),
    yaxis=dict(
        title="Contagem de Respostas",  
        gridcolor="LightGrey"  
    ),
    bargap=0.3
)

fig3 = px.bar(
    resumo_respostas[resumo_respostas['pergunta'] == '3) Para você, quais os principais desafios para realizar uma sondagem?'], 
    x='resposta_ajustada', 
    y='count', 
    title='3) Para você, quais os principais desafios para realizar uma sondagem?', 
    labels={'resposta_ajustada': 'Respostas', 'count': 'Contagem'},
    height=400
)


fig3.update_traces(
    texttemplate='%{y}',  
    textposition='inside'  
)

fig3.update_layout(
    xaxis_tickangle=0,  
    height=600,  
    xaxis=dict(
        tickmode='auto',  
        nticks=20 
    ),
    yaxis=dict(
        title="Contagem de Respostas",  
        gridcolor="LightGrey"  
    ),
    bargap=0.3
)

st.plotly_chart(fig1)
st.plotly_chart(fig2)
st.plotly_chart(fig3)

with st.expander("Clique aqui para os dados dos Professores com Onboarding incompleto"):
    st.dataframe(nao_respondeu_todas)


resumo_respostas_1 = nao_respondeu_todas.groupby(['pergunta', 'resposta']).size().reset_index(name='count')
resumo_respostas_1['resposta_ajustada'] = resumo_respostas_1['resposta'].replace({
    'Falta de conhecimento do que fazer após a sondagem': 'Falta de conhecimento<br>do que fazer<br>após a sondagem',
    'Falta de conhecimento sobre sondagem': 'Falta de conhecimento<br>sobre sondagem',
    'Falta de materiais práticos para realizar a sondagem': 'Falta de materiais<br>práticos para<br>realizar a sondagem',
    'Falta de visibilidade do nível da turma': 'Falta de visibilidade<br>do nível da turma',
    'Não tenho dificuldade com sondagem': 'Não tenho dificuldade<br>com sondagem'
})


fig4 = px.bar(
    resumo_respostas_1[resumo_respostas_1['pergunta'] == '1) Nos últimos 6 meses, com que frequência você realizou uma sondagem com sua turma?'], 
    x='resposta', 
    y='count', 
    title='1) Nos últimos 6 meses, com que frequência você realizou uma sondagem com sua turma?', 
    height=400
)


fig4.update_traces(
    texttemplate='%{y}',  
    textposition='inside'  
)

fig4.update_layout(
    xaxis_tickangle=0,  
    height=600,  
    xaxis=dict(
        tickmode='auto',  
        nticks=20 
    ),
    yaxis=dict(
        title="Contagem de Respostas",  
        gridcolor="LightGrey"  
    ), 
    bargap=0.3
)



fig5 = px.bar(
    resumo_respostas_1[resumo_respostas_1['pergunta'] == '2) Você se sente confiante para realizar uma sondagem com a sua turma?'], 
    x='resposta', 
    y='count', 
    title='2) Você se sente confiante para realizar uma sondagem com a sua turma?', 
    labels={'resposta': 'Respostas', 'count': 'Contagem'},
    height=400
)


fig5.update_traces(
    texttemplate='%{y}',  
    textposition='inside'  
)

fig5.update_layout(
    xaxis_tickangle=0,  
    height=600,  
    xaxis=dict(
        tickmode='auto',  
        nticks=20 
    ),
    yaxis=dict(
        title="Contagem de Respostas",  
        gridcolor="LightGrey"  
    ),
    bargap=0.3
)

fig6 = px.bar(
    resumo_respostas_1[resumo_respostas_1['pergunta'] == '3) Para você, quais os principais desafios para realizar uma sondagem?'], 
    x='resposta_ajustada', 
    y='count', 
    title='3) Para você, quais os principais desafios para realizar uma sondagem?', 
    labels={'resposta_ajustada': 'Respostas', 'count': 'Contagem'},
    height=400
)


fig6.update_traces(
    texttemplate='%{y}',  
    textposition='inside'  
)

fig6.update_layout(
    xaxis_tickangle=0,  
    height=600,  
    xaxis=dict(
        tickmode='auto',  
        nticks=20 
    ),
    yaxis=dict(
        title="Contagem de Respostas",  
        gridcolor="LightGrey"  
    ),
    bargap=0.3
)

st.plotly_chart(fig4)
st.plotly_chart(fig5)
st.plotly_chart(fig6)

