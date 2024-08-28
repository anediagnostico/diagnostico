import os
from dotenv import load_dotenv
import sqlalchemy
import streamlit as st
import pandas as pd

# Carregar as variáveis de ambiente do arquivo .env
load_dotenv()

# Recuperar as variáveis de ambiente
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
database = os.getenv('DB_NAME')

# Construir a string de conexão
connection_string = f'mysql+pymysql://{user}:{password}@{host}/{database}'

# Conectar ao banco de dados
engine = sqlalchemy.create_engine(connection_string)

# Conexão com o banco de dados
engine = sqlalchemy.create_engine('mysql+pymysql://user:password@host/database')

# Recuperar dados usando SQL
logins_query = "SELECT COUNT(*) AS total_logins FROM teacher WHERE confirmed = 1;"
onboardings_query = "SELECT COUNT(*) AS total_onboardings FROM teacher WHERE confirmed = 1;"
students_query = "SELECT COUNT(*) AS total_students FROM student;"
classes_query = "SELECT COUNT(*) AS total_classes FROM class;"
students_by_class_query = """... (sua query acima) ..."""

# Executar as queries
logins = pd.read_sql(logins_query, engine)
onboardings = pd.read_sql(onboardings_query, engine)
students = pd.read_sql(students_query, engine)
classes = pd.read_sql(classes_query, engine)
students_by_class = pd.read_sql(students_by_class_query, engine)

# Visualização no Streamlit
st.title("Relatório Diagnóstico")

st.subheader("Métricas Gerais")
st.write("Quantidade de Logins:", logins['total_logins'].iloc[0])
st.write("Quantidade de Onboardings:", onboardings['total_onboardings'].iloc[0])
st.write("Quantidade de Alunos Inscritos:", students['total_students'].iloc[0])
st.write("Quantidade de Turmas:", classes['total_classes'].iloc[0])

st.subheader("Alunos por Turma e Professor")
st.dataframe(students_by_class)

