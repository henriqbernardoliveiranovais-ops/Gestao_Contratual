import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "chave-dev-troque-no-env")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "contratos.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # upload de planilha até 10 MB

    # Selos de alerta na tabela: quantos dias antes do fim/reajuste o contrato é destacado
    DIAS_ALERTA_VENCIMENTO = int(os.getenv("DIAS_ALERTA_VENCIMENTO", 90))
    DIAS_ALERTA_REAJUSTE = int(os.getenv("DIAS_ALERTA_REAJUSTE", 60))

    # Aviso por e-mail de contratos a vencer (comando: python -m flask --app run.py enviar-alertas)
    EMAIL_DESTINATARIOS = [e.strip() for e in os.getenv("EMAIL_DESTINATARIOS", "").replace(",", ";").split(";")
                           if e.strip()]
    EMAIL_DIAS_ANTECEDENCIA = int(os.getenv("EMAIL_DIAS_ANTECEDENCIA", 90))
    EMAIL_SOMENTE_EM_TRATATIVA = os.getenv("EMAIL_SOMENTE_EM_TRATATIVA", "0") == "1"
    PORTAL_URL = os.getenv("PORTAL_URL", "")

    # Listas usadas nos formulários e filtros (mesmos valores da planilha Base_Contratos)
    STATUS_EM_TRATATIVA = "Em Tratativa"
    STATUS_FINALIZADO = "Finalizado"
    STATUS_OPCOES = [STATUS_EM_TRATATIVA, STATUS_FINALIZADO]
    TIPOS_CONTRATO = ["Fixo", "Spot"]
    AVISO_PREVIO_OPCOES = [0, 30, 60, 90, 120]
    MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
             "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]