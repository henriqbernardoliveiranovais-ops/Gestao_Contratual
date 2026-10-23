"""Regras de negócio: indicadores, filtros, importação e exportação da planilha."""
from io import BytesIO

import pandas as pd
from flask import current_app
from sqlalchemy import or_

from app import db
from app.models import Contrato, Indice
from app.utils import ler_data, ler_inteiro, ler_sim_nao, ler_texto, ler_valor, normalizar

# Abas da planilha Base_Dashboard
ABA_CONTRATOS = "base_contratos"
ABA_INDICES = "base_indices"

# Cabeçalhos aceitos na aba de contratos -> campo do banco (comparação sem acento/maiúscula)
MAPA_COLUNAS = {
    "mes": "mes", "mes de referencia": "mes",
    "unidade": "unidade",
    "parceiro": "parceiro", "fornecedor": "parceiro",
    "objeto": "objeto",
    "valor mensal": "valor_mensal", "valor": "valor_mensal",
    "aviso previo": "aviso_previo",
    "inicio": "inicio", "data inicio": "inicio", "data de inicio": "inicio",
    "fim": "fim", "data fim": "fim", "termino": "fim",
    "tratativa vigencia": "tratativa_vigencia",
    "mes/ano - reajuste": "reajuste", "mes/ano reajuste": "reajuste", "reajuste": "reajuste",
    "tratativa reajuste": "tratativa_reajuste",
    "inicio das tratativas": "inicio_tratativas",
    "status": "status",
    "observacao": "observacao", "obs": "observacao",
    "tipo de contrato": "tipo_contrato", "tipo": "tipo_contrato",
}
CAMPOS_DATA = {"inicio", "fim", "reajuste", "inicio_tratativas"}
CAMPOS_SIM_NAO = {"tratativa_vigencia", "tratativa_reajuste"}
CAMPOS_OBRIGATORIOS = {"unidade", "parceiro"}

# Colunas da exportação = mesmo layout da aba Base_Contratos (dá para reimportar)
COLUNAS_EXPORTACAO = ["Mês", "Unidade", "Parceiro", "Objeto", "Valor Mensal", "Aviso Prévio", "Início", "Fim",
                      "Tratativa Vigencia", "Mês/Ano - Reajuste", "Tratativa Reajuste", "Inicio das Tratativas",
                      "Status", "Observação", "Tipo de Contrato"]


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------
def calcular_indicadores(contratos):
    cfg = current_app.config
    dv, dr = cfg["DIAS_ALERTA_VENCIMENTO"], cfg["DIAS_ALERTA_REAJUSTE"]
    categorias = [c.categoria() for c in contratos]

    def contar(nome):
        return categorias.count(nome)

    return {
        "total": len(contratos),
        "em_dia": contar("em_dia"),
        "em_tratativas": len(contratos) - contar("em_dia"),
        "vencidos": contar("vencido"),
        "tratativa_vencimento": contar("vencimento"),
        "tratativa_reajuste": contar("reajuste"),
        "tratativa_outros": contar("demais"),
        "alerta_vencimento": sum(1 for c in contratos if "proximo_vencimento" in c.alertas(dv, dr)),
        "alerta_reajuste": sum(1 for c in contratos if "proximo_reajuste" in c.alertas(dv, dr)),
        "valor_total": float(sum(c.valor_mensal or 0 for c in contratos)),
        "qtd_variavel": sum(1 for c in contratos if c.valor_variavel),
    }


# ---------------------------------------------------------------------------
# Filtros (usados na exportação; o painel filtra no navegador)
# ---------------------------------------------------------------------------
def filtrar_contratos(args):
    q = Contrato.query
    if args.get("parceiro"):
        q = q.filter(Contrato.parceiro == args["parceiro"])
    if args.get("unidade"):
        q = q.filter(Contrato.unidade == args["unidade"])
    if args.get("status"):
        q = q.filter(Contrato.status == args["status"])
    if args.get("mes"):
        q = q.filter(Contrato.mes == args["mes"])
    if args.get("busca"):
        termo = f"%{args['busca'].strip()}%"
        q = q.filter(or_(Contrato.parceiro.ilike(termo), Contrato.unidade.ilike(termo),
                         Contrato.status.ilike(termo), Contrato.observacao.ilike(termo),
                         Contrato.objeto.ilike(termo)))
    return q.order_by(Contrato.fim.is_(None), Contrato.fim, Contrato.parceiro).all()


# ---------------------------------------------------------------------------
# Importação da planilha
# ---------------------------------------------------------------------------
def _escolher_aba(abas, nome_desejado, padrao_primeira=False):
    for nome in abas:
        if normalizar(nome).replace(" ", "_") == nome_desejado:
            return nome
    return abas[0] if padrao_primeira else None


def importar_planilha(arquivo, modo="adicionar"):
    """Lê a aba de contratos (e a de índices, se existir). Devolve um resumo para a tela."""
    planilha = pd.ExcelFile(arquivo)
    aba_contratos = _escolher_aba(planilha.sheet_names, ABA_CONTRATOS, padrao_primeira=True)
    df = planilha.parse(aba_contratos, dtype=object).dropna(how="all")

    colunas, ignoradas = {}, []
    for col in df.columns:
        campo = MAPA_COLUNAS.get(normalizar(col))
        if campo and campo not in colunas.values():
            colunas[col] = campo
        elif not str(col).startswith("Unnamed"):
            ignoradas.append(str(col).strip())

    faltando = CAMPOS_OBRIGATORIOS - set(colunas.values())
    if faltando:
        raise ValueError(f"A aba '{aba_contratos}' não tem as colunas obrigatórias: " + ", ".join(sorted(faltando)))

    status_validos = {normalizar(s): s for s in current_app.config["STATUS_OPCOES"]}
    tipos_validos = {normalizar(t): t for t in current_app.config["TIPOS_CONTRATO"]}
    novos, avisos = [], []

    for numero, (_, linha) in enumerate(df.iterrows(), start=2):  # linha 1 = cabeçalho
        dados = {}
        for col, campo in colunas.items():
            valor = linha[col]
            if campo in CAMPOS_DATA:
                dados[campo] = ler_data(valor)
            elif campo in CAMPOS_SIM_NAO:
                dados[campo] = ler_sim_nao(valor)
            elif campo == "aviso_previo":
                dados[campo] = ler_inteiro(valor)
            elif campo == "valor_mensal":
                texto = ler_texto(valor)
                if texto and normalizar(texto) == "variavel":
                    dados["valor_variavel"] = True
                    dados[campo] = None
                else:
                    dados[campo] = ler_valor(valor)
            else:
                dados[campo] = ler_texto(valor)

        if not dados.get("unidade") or not dados.get("parceiro"):
            avisos.append(f"Linha {numero}: sem unidade ou parceiro — ignorada.")
            continue

        status = dados.get("status")
        dados["status"] = status_validos.get(normalizar(status), status) if status else "Finalizado"
        if dados.get("tipo_contrato"):
            dados["tipo_contrato"] = tipos_validos.get(normalizar(dados["tipo_contrato"]), dados["tipo_contrato"])
        if "reajuste" in colunas.values() and dados.get("reajuste") is None:
            avisos.append(f"Linha {numero} ({dados['parceiro']}): sem mês/ano de reajuste.")

        novos.append(Contrato(origem="planilha", **dados))

    if modo == "substituir":
        Contrato.query.filter(Contrato.origem.in_(["planilha", "exemplo"])).delete(synchronize_session=False)
    db.session.add_all(novos)

    indices = 0
    aba_indices = _escolher_aba(planilha.sheet_names, ABA_INDICES)
    if aba_indices:
        indices = _importar_indices(planilha.parse(aba_indices))

    db.session.commit()
    return {"importados": len(novos), "indices": indices, "avisos": avisos, "ignoradas": ignoradas,
            "aba": aba_contratos, "mapeadas": {str(k).strip(): v for k, v in colunas.items()}}


def _importar_indices(df):
    """Aba Base_Indices: Ano | Mês | ... | IPCA (%) | IGP-M (%) | IPC/FIPE ... (cria ou atualiza o mês)."""
    meses = {normalizar(m): i for i, m in enumerate(current_app.config["MESES"], start=1)}
    col = {}
    for c in df.columns:
        n = normalizar(c)
        if n == "ano":
            col["ano"] = c
        elif n == "mes":
            col["mes"] = c
        elif n.startswith("ipca"):
            col["ipca"] = c
        elif n.startswith("igp-m") or n.startswith("igpm"):
            col["igpm"] = c
        elif n.startswith("ipc/fipe") or n.startswith("ipc fipe"):
            col["ipc_fipe"] = c
    if "ano" not in col or "mes" not in col:
        return 0

    total = 0
    for _, linha in df.iterrows():
        ano = ler_inteiro(linha[col["ano"]])
        mes_valor = linha[col["mes"]]
        mes = ler_inteiro(mes_valor) or meses.get(normalizar(mes_valor or ""))
        if not ano or not mes:
            continue
        registro = Indice.query.filter_by(ano=ano, mes=mes).first() or Indice(ano=ano, mes=mes)
        for campo in ("ipca", "igpm", "ipc_fipe"):
            if campo in col:
                setattr(registro, campo, ler_valor(linha[col[campo]]))
        db.session.add(registro)
        total += 1
    return total


# ---------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------
def gerar_excel(contratos):
    def sim_nao(v):
        return "Sim" if v else "Não"

    linhas = [{
        "Mês": c.mes, "Unidade": c.unidade, "Parceiro": c.parceiro, "Objeto": c.objeto,
        "Valor Mensal": "Variável" if c.valor_variavel else (float(c.valor_mensal) if c.valor_mensal is not None else None),
        "Aviso Prévio": c.aviso_previo, "Início": c.inicio, "Fim": c.fim,
        "Tratativa Vigencia": sim_nao(c.tratativa_vigencia), "Mês/Ano - Reajuste": c.reajuste,
        "Tratativa Reajuste": sim_nao(c.tratativa_reajuste),
        "Inicio das Tratativas": c.inicio_tratativas or "-",
        "Status": c.status, "Observação": c.observacao, "Tipo de Contrato": c.tipo_contrato,
    } for c in contratos]
    df = pd.DataFrame(linhas, columns=COLUNAS_EXPORTACAO)

    saida = BytesIO()
    with pd.ExcelWriter(saida, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Base_Contratos")
        ws = writer.sheets["Base_Contratos"]
        larguras = [11, 34, 40, 40, 14, 12, 12, 12, 10, 14, 10, 14, 14, 45, 10]
        for i, largura in enumerate(larguras, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = largura
        for row in ws.iter_rows(min_row=2):
            for idx in (6, 7, 11):  # Início, Fim, Início das tratativas
                row[idx].number_format = "DD/MM/YYYY"
            row[9].number_format = "MM/YYYY"
            row[4].number_format = '"R$" #,##0.00'
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    saida.seek(0)
    return saida
