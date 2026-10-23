"""Funções de apoio: formatação no padrão brasileiro e leitura de valores da planilha."""
import re
import unicodedata
from datetime import date, datetime

import pandas as pd


def formatar_data(valor):
    if not valor:
        return "-"
    if isinstance(valor, str):
        try:
            valor = date.fromisoformat(valor)
        except ValueError:
            return valor
    return valor.strftime("%d/%m/%Y")


def formatar_moeda(valor):
    if valor is None or valor == "":
        return "-"
    texto = f"{float(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def normalizar(texto):
    """'Tipo de Contrato' -> 'tipo de contrato' (sem acento, minúsculo)."""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto).strip().lower()


def ler_data(valor):
    """Aceita datas do Excel, 'dd/mm/aaaa', 'aaaa-mm-dd' ou vazio."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor is pd.NaT:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, pd.Timestamp):
        return valor.date()
    if isinstance(valor, (int, float)):  # número de série do Excel
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(valor))).date()
    texto = str(valor).strip()
    if not texto or texto in {"-", "N/A", "n/a"}:
        return None
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def ler_valor(valor):
    """Aceita 1234.5, '1.234,50', 'R$ 1.234,50' ou vazio."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        return round(float(valor), 2)
    texto = str(valor).replace("R$", "").replace(" ", "").strip()
    if not texto or texto == "-":
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return round(float(texto), 2)
    except ValueError:
        return None


def ler_inteiro(valor):
    numero = ler_valor(valor)
    return int(numero) if numero is not None else None


def ler_sim_nao(valor):
    """'Sim' -> True; 'Não', vazio ou qualquer outra coisa -> False."""
    texto = ler_texto(valor)
    return bool(texto) and normalizar(texto) in {"sim", "s", "x", "true", "1"}


def ler_texto(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    return texto or None
