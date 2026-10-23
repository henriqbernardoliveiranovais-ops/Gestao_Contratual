from datetime import date, datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for

from app import db
from app.forms import ContratoForm, IndiceForm
from app.models import Contrato, Indice
from app.services import calcular_indicadores, filtrar_contratos, gerar_excel

bp = Blueprint("main", __name__)


def _opcoes(campo):
    valores = db.session.query(campo).distinct().order_by(campo).all()
    return [v[0] for v in valores if v[0]]


def _ajustar_campos(contrato):
    """Normaliza o que veio do formulário antes de salvar."""
    contrato.mes = contrato.mes or None
    contrato.tipo_contrato = contrato.tipo_contrato or None
    if contrato.valor_variavel:
        contrato.valor_mensal = None


def _sugestoes():
    return {"sugestoes_parceiros": _opcoes(Contrato.parceiro), "sugestoes_unidades": _opcoes(Contrato.unidade)}


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------
@bp.route("/")
def dashboard():
    cfg = current_app.config
    contratos = Contrato.query.order_by(Contrato.fim.is_(None), Contrato.fim).all()
    indices = Indice.query.order_by(Indice.ano, Indice.mes).all()[-12:]

    return render_template(
        "dashboard.html",
        kpi=calcular_indicadores(contratos),
        contratos_json=[c.to_dict(cfg["DIAS_ALERTA_VENCIMENTO"], cfg["DIAS_ALERTA_REAJUSTE"]) for c in contratos],
        indices_json=[{"rotulo": f"{i.mes:02d}/{i.ano}", "ipca": i.ipca, "igpm": i.igpm, "ipc_fipe": i.ipc_fipe}
                      for i in indices],
        parceiros=_opcoes(Contrato.parceiro),
        unidades=_opcoes(Contrato.unidade),
        meses_usados=[m for m in cfg["MESES"] if m in _opcoes(Contrato.mes)],
        status_opcoes=cfg["STATUS_OPCOES"],
        dias_venc=cfg["DIAS_ALERTA_VENCIMENTO"],
        dias_reaj=cfg["DIAS_ALERTA_REAJUSTE"],
    )


# ---------------------------------------------------------------------------
# Cadastro direto no portal
# ---------------------------------------------------------------------------
@bp.route("/contratos/novo", methods=["GET", "POST"])
def novo_contrato():
    form = ContratoForm()
    if request.method == "GET":
        form.mes.data = current_app.config["MESES"][date.today().month - 1]
        form.aviso_previo.data = 30
        form.tipo_contrato.data = "Fixo"
    if form.validate_on_submit():
        contrato = Contrato(origem="portal")
        form.populate_obj(contrato)
        _ajustar_campos(contrato)
        db.session.add(contrato)
        db.session.commit()
        flash(f"Contrato com {contrato.parceiro} cadastrado.", "sucesso")
        if request.form.get("acao") == "salvar_e_novo":
            return redirect(url_for("main.novo_contrato"))
        return redirect(url_for("main.dashboard"))
    return render_template("contrato_form.html", form=form, titulo="Novo contrato", contrato=None, **_sugestoes())


@bp.route("/contratos/<int:contrato_id>/editar", methods=["GET", "POST"])
def editar_contrato(contrato_id):
    contrato = db.get_or_404(Contrato, contrato_id)
    form = ContratoForm(obj=contrato)
    # aviso prévio fora da lista padrão (ex.: 45 dias vindo da planilha) continua selecionável
    if contrato.aviso_previo is not None and contrato.aviso_previo not in dict(form.aviso_previo.choices):
        form.aviso_previo.choices = sorted(form.aviso_previo.choices + [(contrato.aviso_previo, f"{contrato.aviso_previo} dias")])
    if form.validate_on_submit():
        form.populate_obj(contrato)
        _ajustar_campos(contrato)
        db.session.commit()
        flash(f"Contrato com {contrato.parceiro} atualizado.", "sucesso")
        return redirect(url_for("main.dashboard"))
    return render_template("contrato_form.html", form=form, titulo="Editar contrato", contrato=contrato,
                           **_sugestoes())


@bp.route("/contratos/<int:contrato_id>/excluir", methods=["POST"])
def excluir_contrato(contrato_id):
    contrato = db.get_or_404(Contrato, contrato_id)
    db.session.delete(contrato)
    db.session.commit()
    flash(f"Contrato com {contrato.parceiro} excluído.", "aviso")
    return redirect(url_for("main.dashboard"))


# ---------------------------------------------------------------------------
# Planilha: exportar
# ---------------------------------------------------------------------------
@bp.route("/exportar")
def exportar():
    arquivo = gerar_excel(filtrar_contratos(request.args))
    nome = f"contratos_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return send_file(arquivo, as_attachment=True, download_name=nome,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------------------
# Índices econômicos (IPCA, IGP-M, IPC/FIPE)
# ---------------------------------------------------------------------------
@bp.route("/indices", methods=["GET", "POST"])
def indices():
    form = IndiceForm()
    if request.method == "GET":
        form.ano.data = date.today().year
        form.mes.data = date.today().month
    if form.validate_on_submit():
        registro = Indice.query.filter_by(ano=form.ano.data, mes=form.mes.data).first() or Indice()
        form.populate_obj(registro)
        db.session.add(registro)
        db.session.commit()
        flash(f"Índices de {form.mes.data:02d}/{form.ano.data} salvos.", "sucesso")
        return redirect(url_for("main.indices"))
    lista = Indice.query.order_by(Indice.ano.desc(), Indice.mes.desc()).all()
    return render_template("indices.html", form=form, lista=lista)


@bp.route("/indices/<int:indice_id>/excluir", methods=["POST"])
def excluir_indice(indice_id):
    registro = db.get_or_404(Indice, indice_id)
    db.session.delete(registro)
    db.session.commit()
    flash("Registro de índice excluído.", "aviso")
    return redirect(url_for("main.indices"))