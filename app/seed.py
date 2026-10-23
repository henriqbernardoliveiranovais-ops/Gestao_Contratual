"""Comandos de terminal para popular/limpar dados FICTÍCIOS de teste.

    python -m flask dados-exemplo      -> cria 40 contratos e 12 meses de índices de exemplo
    python -m flask limpar-exemplo     -> apaga somente o que foi criado pelo comando acima
    python -m flask importar-base      -> carrega dados\Base_Dashboard_1.xlsx no banco (substitui o que veio de planilha)
"""
import os
import random
from datetime import date, timedelta

import click

from app import db
from app.models import Contrato, Indice

UNIDADES = ["Matriz", "Unidade Norte", "Unidade Sul", "Unidade Leste", "Centro de Distribuição"]
PARCEIROS = ["Parceiro Exemplo " + letra for letra in "ABCDEFGHIJKL"]
OBJETOS = ["Limpeza e conservação", "Vigilância patrimonial", "Manutenção predial", "Locação de impressoras",
           "Fornecimento de água mineral", "Manutenção de ar-condicionado", "Jardinagem", "Controle de pragas"]
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def registrar_comandos(app):
    @app.cli.command("dados-exemplo")
    def dados_exemplo():
        """Cria contratos e índices fictícios para testar o painel."""
        random.seed(42)
        hoje = date.today()
        for _ in range(40):
            inicio = hoje - timedelta(days=random.randint(200, 900))
            fim = hoje + timedelta(days=random.randint(-40, 500))
            reajuste = hoje + timedelta(days=random.randint(-10, 300))
            em_tratativa = random.random() < 0.33
            vigencia = em_tratativa and random.random() < 0.45
            reaj = em_tratativa and (not vigencia or random.random() < 0.5)
            variavel = random.random() < 0.3
            db.session.add(Contrato(
                mes=MESES[hoje.month - 1], unidade=random.choice(UNIDADES), parceiro=random.choice(PARCEIROS),
                objeto=random.choice(OBJETOS), tipo_contrato="Fixo",
                valor_mensal=None if variavel else round(random.uniform(1500, 48000), 2), valor_variavel=variavel,
                aviso_previo=random.choice([30, 30, 30, 60, 90]),
                inicio=inicio, fim=fim, reajuste=reajuste.replace(day=1),
                tratativa_vigencia=vigencia, tratativa_reajuste=reaj,
                inicio_tratativas=hoje - timedelta(days=random.randint(5, 120)) if em_tratativa else None,
                status="Em Tratativa" if em_tratativa else "Finalizado",
                observacao="Suprimentos - Em negociação." if em_tratativa else "Concluído",
                origem="exemplo",
            ))

        base = {"ipca": 4.2, "igpm": 3.1, "ipc_fipe": 3.8}
        ano, mes = hoje.year - 1, hoje.month
        for _ in range(12):
            mes += 1
            if mes > 12:
                mes, ano = 1, ano + 1
            for chave in base:
                base[chave] = round(base[chave] + random.uniform(-0.35, 0.3), 2)
            if not Indice.query.filter_by(ano=ano, mes=mes).first():
                db.session.add(Indice(ano=ano, mes=mes, **base))
        db.session.commit()
        click.echo("Dados de exemplo criados.")

    @app.cli.command("importar-base")
    @click.argument("arquivo", default=os.path.join("dados", "Base_Dashboard_1.xlsx"))
    @click.option("--adicionar", is_flag=True, help="Soma aos contratos atuais em vez de substituir.")
    def importar_base(arquivo, adicionar):
        """Carrega a planilha Base_Dashboard direto no banco (abas Base_Contratos e Base_Indices)."""
        from app.services import importar_planilha

        if not os.path.exists(arquivo):
            raise click.ClickException(f"Arquivo não encontrado: {arquivo}")
        resumo = importar_planilha(arquivo, "adicionar" if adicionar else "substituir")
        click.echo(f"{resumo['importados']} contratos importados da aba {resumo['aba']}.")
        click.echo(f"{resumo['indices']} meses de índices atualizados.")
        for aviso in resumo["avisos"]:
            click.echo(f"  aviso: {aviso}")
        if resumo["ignoradas"]:
            click.echo("  colunas ignoradas: " + ", ".join(resumo["ignoradas"]))

    @app.cli.command("limpar-exemplo")
    @click.option("--indices", is_flag=True, help="Apaga também TODOS os índices cadastrados.")
    def limpar_exemplo(indices):
        """Apaga os contratos fictícios (e, com --indices, a tabela de índices)."""
        apagados = Contrato.query.filter_by(origem="exemplo").delete()
        if indices:
            Indice.query.delete()
        db.session.commit()
        click.echo(f"{apagados} contratos de exemplo apagados." + (" Índices apagados." if indices else ""))