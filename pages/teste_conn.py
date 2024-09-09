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

user_1 = os.getenv('DB_USER_DASH')
password_1 = os.getenv('DB_PASSWORD_DASH')
host_1 = os.getenv('DB_HOST_DASH')
database_1 = os.getenv('DB_DATABASE_DASH')

connection_string_ne = f'mysql+pymysql://{user_1}:{password_1}@{host_1}/{database_1}'
engine_ne = create_engine(connection_string_ne)

# ------------------------- TESTE DE CONEXÃO ---------------------------
try:
    engine_cdc = create_engine(connection_string_ne)
    connection = engine_ne.connect()
    print("Conexão bem-sucedida!")
    connection.close()
except Exception as e:
    print(f"Erro ao conectar ao banco de dados: {e}")

