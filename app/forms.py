from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (BooleanField, DateField, DecimalField, FloatField, IntegerField, MonthField, RadioField,
                     SelectField, StringField, TextAreaField)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError


def _virgula_para_ponto(valores):
    """Permite digitar 4,52 ou 1.234,56 (padrão brasileiro)."""
    if valores and valores[0]:
        texto = str(valores[0]).replace("R$", "").replace(" ", "").strip()
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        return [texto]
    return valores


class DecimalBR(DecimalField):
    def process_formdata(self, valuelist):
        super().process_formdata(_virgula_para_ponto(valuelist))


class FloatBR(FloatField):
    def process_formdata(self, valuelist):
        super().process_formdata(_virgula_para_ponto(valuelist))


def _sim_nao(valor):
    return valor in (True, "True", "true", "1", "sim", "Sim")


class ContratoForm(FlaskForm):
    mes = SelectField("Mês de referência", validators=[Optional()])
    unidade = StringField("Unidade", validators=[DataRequired(message="Informe a unidade."), Length(max=120)])
    parceiro = StringField("Parceiro", validators=[DataRequired(message="Informe o parceiro."), Length(max=200)])
    objeto = TextAreaField("Objeto", validators=[Optional()])
    tipo_contrato = SelectField("Tipo de contrato", validators=[Optional()])

    valor_mensal = DecimalBR("Valor mensal (R$)", places=2, validators=[Optional(), NumberRange(min=0)])
    valor_variavel = BooleanField("Valor variável")
    aviso_previo = SelectField("Aviso prévio", coerce=int, validators=[Optional()])

    inicio = DateField("Início", validators=[Optional()])
    fim = DateField("Fim", validators=[Optional()])
    tratativa_vigencia = SelectField("Tratativa de vigência", coerce=_sim_nao, choices=[(False, "Não"), (True, "Sim")])
    reajuste = MonthField("Mês/ano do reajuste", validators=[Optional()])
    tratativa_reajuste = SelectField("Tratativa de reajuste", coerce=_sim_nao, choices=[(False, "Não"), (True, "Sim")])

    status = SelectField("Status", validators=[DataRequired()])
    inicio_tratativas = DateField("Início das tratativas", validators=[Optional()])
    observacao = TextAreaField("Observação", validators=[Optional()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cfg = current_app.config
        self.mes.choices = [("", "—")] + [(m, m) for m in cfg["MESES"]]
        self.status.choices = [(s, s) for s in cfg["STATUS_OPCOES"]]
        self.tipo_contrato.choices = [("", "—")] + [(t, t) for t in cfg["TIPOS_CONTRATO"]]
        self.aviso_previo.choices = [(d, f"{d} dias") for d in cfg["AVISO_PREVIO_OPCOES"]]

    def validate_fim(self, field):
        if field.data and self.inicio.data and field.data < self.inicio.data:
            raise ValidationError("A data de fim não pode ser anterior ao início.")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        # Optional() interrompe a validação do campo vazio, então a regra fica aqui
        if self.valor_mensal.data is None and not self.valor_variavel.data:
            self.valor_mensal.errors = list(self.valor_mensal.errors) + ['Informe o valor ou marque "Valor variável".']
            ok = False
        return ok


class ImportarForm(FlaskForm):
    arquivo = FileField("Planilha (.xlsx)", validators=[
        FileRequired(message="Escolha um arquivo."),
        FileAllowed(["xlsx", "xls"], "Envie um arquivo Excel (.xlsx)."),
    ])
    modo = RadioField("Como importar", choices=[
        ("adicionar", "Adicionar aos contratos existentes"),
        ("substituir", "Substituir os contratos que vieram de planilha"),
    ], default="adicionar")


class IndiceForm(FlaskForm):
    ano = IntegerField("Ano", validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    mes = SelectField("Mês", coerce=int, choices=list(enumerate( ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"], start=1)))
    ipca = FloatBR("IPCA 12m (%)", validators=[Optional()])
    igpm = FloatBR("IGP-M 12m (%)", validators=[Optional()])
    ipc_fipe = FloatBR("IPC/FIPE 12m (%)", validators=[Optional()])
