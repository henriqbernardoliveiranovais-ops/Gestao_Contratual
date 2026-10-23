from datetime import date, datetime
from app import db

STATUS_EM_TRATATIVA = "Em Tratativa"
STATUS_FINALIZADO = "Finalizado"


class Contrato(db.Model):
    __tablename__ = "contratos"

    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.String(20))                         # mês de referência
    unidade = db.Column(db.String(120), nullable=False, index=True)
    parceiro = db.Column(db.String(200), nullable=False, index=True)
    objeto = db.Column(db.Text)
    valor_mensal = db.Column(db.Numeric(14, 2))            # vazio quando o valor é variável
    valor_variavel = db.Column(db.Boolean, nullable=False, default=False)
    aviso_previo = db.Column(db.Integer)                   # em dias
    inicio = db.Column(db.Date)
    fim = db.Column(db.Date)
    tratativa_vigencia = db.Column(db.Boolean, nullable=False, default=False)
    reajuste = db.Column(db.Date)                           # mês/ano do reajuste
    tratativa_reajuste = db.Column(db.Boolean, nullable=False, default=False)
    inicio_tratativas = db.Column(db.Date)
    status = db.Column(db.String(30), nullable=False, default=STATUS_FINALIZADO, index=True)
    observacao = db.Column(db.Text)
    tipo_contrato = db.Column(db.String(30))

    criado_em = db.Column(db.DateTime, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    origem = db.Column(db.String(20), default="portal")    # "portal", "planilha" ou "exemplo"

    # ---- regras calculadas -------------------------------------------------
    @property
    def em_tratativa(self):
        return self.status == STATUS_EM_TRATATIVA

    def dias_para_fim(self, hoje=None):
        if not self.fim:
            return None
        return (self.fim - (hoje or date.today())).days

    def dias_para_reajuste(self, hoje=None):
        if not self.reajuste:
            return None
        return (self.reajuste - (hoje or date.today())).days

    def categoria(self, hoje=None):
        """Classificação única usada nos cards do painel.

        Finalizado                                   -> em_dia
        Em Tratativa e fim já passou                 -> vencido
        Em Tratativa e Tratativa Vigência = Sim      -> vencimento
        Em Tratativa e Tratativa Reajuste = Sim      -> reajuste
        Em Tratativa sem nenhuma das marcações       -> demais
        """
        if not self.em_tratativa:
            return "em_dia"
        d_fim = self.dias_para_fim(hoje)
        if d_fim is not None and d_fim < 0:
            return "vencido"
        if self.tratativa_vigencia:
            return "vencimento"
        if self.tratativa_reajuste:
            return "reajuste"
        return "demais"

    def alertas(self, dias_venc, dias_reaj, hoje=None):
        """Selos de data mostrados na tabela (só para contratos em tratativa)."""
        lista = []
        if not self.em_tratativa:
            return lista
        d_fim = self.dias_para_fim(hoje)
        d_reaj = self.dias_para_reajuste(hoje)
        if d_fim is not None and d_fim < 0:
            lista.append("vencido")
        elif d_fim is not None and d_fim <= dias_venc:
            lista.append("proximo_vencimento")
        if d_reaj is not None and 0 <= d_reaj <= dias_reaj:
            lista.append("proximo_reajuste")
        return lista

    def to_dict(self, dias_venc=90, dias_reaj=60):
        def iso(d):
            return d.isoformat() if d else None

        return {
            "id": self.id,
            "mes": self.mes or "",
            "unidade": self.unidade,
            "parceiro": self.parceiro,
            "objeto": self.objeto or "",
            "valor_mensal": float(self.valor_mensal) if self.valor_mensal is not None else None,
            "valor_variavel": self.valor_variavel,
            "aviso_previo": self.aviso_previo,
            "inicio": iso(self.inicio),
            "fim": iso(self.fim),
            "tratativa_vigencia": self.tratativa_vigencia,
            "reajuste": iso(self.reajuste),
            "tratativa_reajuste": self.tratativa_reajuste,
            "inicio_tratativas": iso(self.inicio_tratativas),
            "status": self.status,
            "observacao": self.observacao or "",
            "tipo_contrato": self.tipo_contrato or "",
            "dias_para_fim": self.dias_para_fim(),
            "categoria": self.categoria(),
            "alertas": self.alertas(dias_venc, dias_reaj),
        }


class Indice(db.Model):
    """Variação acumulada em 12 meses de IPCA, IGP-M e IPC/FIPE, por mês."""
    __tablename__ = "indices"
    __table_args__ = (db.UniqueConstraint("ano", "mes", name="uq_indice_ano_mes"),)

    id = db.Column(db.Integer, primary_key=True)
    ano = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)  # 1 a 12
    ipca = db.Column(db.Float)
    igpm = db.Column(db.Float)
    ipc_fipe = db.Column(db.Float)
    

class AlertaEnviado(db.Model):
    """Registro dos avisos de vencimento já enviados por e-mail (evita mandar o mesmo aviso duas vezes)."""
    __tablename__ = "alertas_enviados"
    __table_args__ = (db.UniqueConstraint("parceiro", "unidade", "objeto", "fim", name="uq_alerta_contrato_fim"),)

    id = db.Column(db.Integer, primary_key=True)
    parceiro = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(120), nullable=False)
    objeto = db.Column(db.Text, nullable=False, default="")
    fim = db.Column(db.Date, nullable=False)
    enviado_em = db.Column(db.DateTime, default=datetime.now, nullable=False)
