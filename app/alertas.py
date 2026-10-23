"""Aviso por e-mail dos contratos que vão vencer em até 90 dias.

Rodar uma vez por dia (o Agendador de Tarefas do Windows chama o arquivo enviar_alertas.bat):

    python -m flask --app run.py enviar-alertas             -> envia o resumo pelo Outlook
    python -m flask --app run.py enviar-alertas --simular   -> só mostra o que seria enviado

Cada contrato é avisado uma única vez. O resumo do dia só sai se houver contrato novo na janela.
"""
from datetime import date, datetime, timedelta
from html import escape

import click
from flask import current_app

from app import db
from app.models import AlertaEnviado, Contrato
from app.utils import formatar_data, formatar_moeda


# ---------------------------------------------------------------------------
# Quais contratos avisar
# ---------------------------------------------------------------------------
def _chave(c):
    return (c.parceiro, c.unidade, c.objeto or "", c.fim)


def contratos_para_avisar(hoje=None):
    """Contratos com Fim entre hoje e hoje + N dias que ainda não foram avisados."""
    cfg = current_app.config
    hoje = hoje or date.today()
    limite = hoje + timedelta(days=cfg["EMAIL_DIAS_ANTECEDENCIA"])

    consulta = Contrato.query.filter(Contrato.fim.isnot(None), Contrato.fim >= hoje, Contrato.fim <= limite)
    if cfg["EMAIL_SOMENTE_EM_TRATATIVA"]:
        consulta = consulta.filter(Contrato.status == "Em Tratativa")

    ja_avisados = {(a.parceiro, a.unidade, a.objeto, a.fim) for a in AlertaEnviado.query.all()}
    return [c for c in consulta.order_by(Contrato.fim, Contrato.parceiro).all() if _chave(c) not in ja_avisados]


def registrar_avisados(contratos):
    chaves = {_chave(c) for c in contratos}  # sem repetir linhas iguais da planilha
    for parceiro, unidade, objeto, fim in chaves:
        db.session.add(AlertaEnviado(parceiro=parceiro, unidade=unidade, objeto=objeto, fim=fim))
    db.session.commit()


# ---------------------------------------------------------------------------
# Conteúdo do e-mail
# ---------------------------------------------------------------------------
def montar_email(contratos, hoje=None):
    hoje = hoje or date.today()
    cfg = current_app.config
    qtd = len(contratos)
    assunto = (f"[Gestão Contratual] {qtd} contrato{'s' if qtd > 1 else ''} vence{'m' if qtd > 1 else ''} "
               f"em até {cfg['EMAIL_DIAS_ANTECEDENCIA']} dias")

    linhas = []
    for c in contratos:
        dias = (c.fim - hoje).days
        cor = "#b42318" if dias <= 30 else "#a35d00" if dias <= 60 else "#1b2433"
        valor = "Variável" if c.valor_variavel else formatar_moeda(c.valor_mensal)
        linhas.append(f"""
        <tr>
          <td style="{_TD}"><b>{escape(c.parceiro)}</b></td>
          <td style="{_TD}">{escape(c.unidade)}</td>
          <td style="{_TD}">{escape(c.objeto or '-')}</td>
          <td style="{_TD}white-space:nowrap">{formatar_data(c.fim)}</td>
          <td style="{_TD}text-align:center;color:{cor};font-weight:bold">{dias}</td>
          <td style="{_TD}">{c.aviso_previo if c.aviso_previo is not None else '-'} dias</td>
          <td style="{_TD}">{escape(c.status)}</td>
          <td style="{_TD}text-align:right;white-space:nowrap">{valor}</td>
          <td style="{_TD}">{escape(c.observacao or '')}</td>
        </tr>""")

    link = ""
    if cfg["PORTAL_URL"]:
        link = (f'<p style="margin:16px 0 0"><a href="{escape(cfg["PORTAL_URL"])}" '
                f'style="color:#1f4e79;font-weight:bold">Abrir o Painel de Gestão Contratual</a></p>')

    corpo = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1b2433">
      <p>Olá,</p>
      <p>Os contratos abaixo vencem em até <b>{cfg['EMAIL_DIAS_ANTECEDENCIA']} dias</b>
         (referência: {formatar_data(hoje)}). Confira o aviso prévio de cada um para iniciar a tratativa a tempo.</p>
      <table style="border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="background:#1f4e79;color:#fff">
            <th style="{_TH}">Parceiro</th><th style="{_TH}">Unidade</th><th style="{_TH}">Objeto</th>
            <th style="{_TH}">Fim</th><th style="{_TH}">Dias</th><th style="{_TH}">Aviso prévio</th>
            <th style="{_TH}">Status</th><th style="{_TH}">Valor mensal</th><th style="{_TH}">Observação</th>
          </tr>
        </thead>
        <tbody>{''.join(linhas)}</tbody>
      </table>
      {link}
      <p style="color:#5b6576;font-size:12px;margin-top:20px">
        Mensagem automática do Portal de Gestão Contratual. Cada contrato é avisado uma única vez.</p>
    </div>"""
    return assunto, corpo


_TD = "border:1px solid #e2e6ec;padding:6px 8px;vertical-align:top;"
_TH = "border:1px solid #1f4e79;padding:6px 8px;text-align:left;"


# ---------------------------------------------------------------------------
# Envio pelo Outlook instalado no computador
# ---------------------------------------------------------------------------
def enviar_pelo_outlook(destinatarios, assunto, corpo_html):
    try:
        import win32com.client  # pacote pywin32 (só existe no Windows)
    except ImportError as erro:
        raise click.ClickException(
            "Pacote pywin32 não instalado. Rode: python -m pip install pywin32") from erro

    outlook = win32com.client.Dispatch("Outlook.Application")
    email = outlook.CreateItem(0)  # 0 = mensagem de e-mail
    email.To = "; ".join(destinatarios)
    email.Subject = assunto
    email.HTMLBody = corpo_html
    email.Send()


# ---------------------------------------------------------------------------
# Comando de terminal
# ---------------------------------------------------------------------------
def registrar_comando_alertas(app):
    @app.cli.command("enviar-alertas")
    @click.option("--simular", is_flag=True, help="Só mostra o que seria enviado (não envia nem registra).")
    def enviar_alertas(simular):
        """Envia por e-mail o resumo dos contratos que vencem em até N dias."""
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        destinatarios = current_app.config["EMAIL_DESTINATARIOS"]
        if not destinatarios and not simular:
            raise click.ClickException("Nenhum destinatário. Preencha EMAIL_DESTINATARIOS no arquivo .env")

        contratos = contratos_para_avisar()
        if not contratos:
            click.echo(f"{agora} - Nenhum contrato novo para avisar.")
            return

        assunto, corpo = montar_email(contratos)
        if simular:
            click.echo(f"{agora} - SIMULAÇÃO: {assunto}")
            for c in contratos:
                click.echo(f"   {formatar_data(c.fim)}  {c.parceiro} | {c.unidade}")
            click.echo(f"   Destinatários: {', '.join(destinatarios) or '(nenhum configurado)'}")
            return

        enviar_pelo_outlook(destinatarios, assunto, corpo)
        registrar_avisados(contratos)
        click.echo(f"{agora} - E-mail enviado para {', '.join(destinatarios)}: {len(contratos)} contrato(s).")
