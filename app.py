import json, os, secrets
from datetime import datetime
from functools import wraps
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-troque-em-producao"),
    SQLALCHEMY_DATABASE_URI="sqlite:///altamed.db",
    SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
db = SQLAlchemy(app)

with open(os.path.join(os.path.dirname(__file__), "data", "disc.json"), encoding="utf-8") as _f:
    DISC = json.load(_f)
PERFIS = {"D": "Dominante", "I": "Influente", "S": "Estável", "C": "Condescendente"}

ETAPAS = ["Novo", "Triagem", "Entrevista", "Teste", "Aprovado", "Reprovado"]
PERGUNTAS = [
    {"id": "q1", "tipo": "mc", "texto": "Um colega comete um erro que pode afetar a segurança de um paciente. O que você faz?",
     "opcoes": ["Aviso o colega e a liderança imediatamente", "Espero ver se alguém percebe", "Corrijo sozinho sem avisar ninguém", "Não é minha responsabilidade"]},
    {"id": "q2", "tipo": "mc", "texto": "O que mais pesa na sua rotina de trabalho?",
     "opcoes": ["Cuidado com as pessoas", "Cumprir prazos a qualquer custo", "Autonomia total", "Reconhecimento individual"]},
    {"id": "q3", "tipo": "mc", "texto": "Diante de uma norma de segurança que você considera burocrática:",
     "opcoes": ["Sigo e proponho melhorias pelos canais certos", "Sigo só quando estou sendo observado", "Ignoro se atrapalhar a produtividade", "Sigo sem questionar nada"]},
    {"id": "q4", "tipo": "mc", "texto": "Como você prefere trabalhar?",
     "opcoes": ["Em equipe, dividindo responsabilidades", "Sozinho, sem interferência", "Sob supervisão constante", "Depende do dia"]},
    {"id": "q5", "tipo": "mc", "texto": "Um cliente está insatisfeito com o atendimento. Você:",
     "opcoes": ["Escuto, resolvo ou encaminho com retorno ao cliente", "Explico que seguimos o procedimento", "Passo para outra pessoa", "Evito o contato"]},
    {"id": "q6", "tipo": "texto", "texto": "Por que você quer trabalhar com saúde ocupacional no Grupo Altamed?"},
    {"id": "q7", "tipo": "texto", "texto": "Conte uma situação em que você agiu com responsabilidade e cuidado com outras pessoas."},
]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    perfil = db.Column(db.String(30), default="Responsável")
    ativo = db.Column(db.Boolean, default=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    vagas = db.relationship("Vaga", backref="dono")

class Vaga(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(80))
    local = db.Column(db.String(80))
    descricao = db.Column(db.Text)
    requisitos = db.Column(db.Text)
    atividades = db.Column(db.Text)
    piso = db.Column(db.String(60))
    status = db.Column(db.String(20), default="aberta")  # aberta/pausada/encerrada
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    criada = db.Column(db.DateTime, default=datetime.utcnow)
    candidatos = db.relationship("Candidato", backref="vaga", cascade="all,delete")

class Candidato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vaga_id = db.Column(db.Integer, db.ForeignKey("vaga.id"), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    etapa = db.Column(db.String(20), default="Novo")
    entrevistado = db.Column(db.Boolean, default=False)
    data_entrevista = db.Column(db.String(10))
    parecer = db.Column(db.Text)
    respostas = db.Column(db.Text)  # JSON
    disc_respostas = db.Column(db.Text)  # JSON {"1": {"A": 4, "B": 1, ...}}
    disc_d = db.Column(db.Integer)
    disc_i = db.Column(db.Integer)
    disc_s = db.Column(db.Integer)
    disc_c = db.Column(db.Integer)
    lgpd_em = db.Column(db.DateTime, default=datetime.utcnow)
    criado = db.Column(db.DateTime, default=datetime.utcnow)
    @property
    def disc_totais(self):
        if self.disc_d is None:
            return None
        return {"D": self.disc_d, "I": self.disc_i, "S": self.disc_s, "C": self.disc_c}
    @property
    def disc_dominante(self):
        t = self.disc_totais
        return max(t, key=t.get) if t else None
    @property
    def lista_respostas(self):
        r = json.loads(self.respostas or "{}")
        return [(p["texto"], r.get(p["id"], "—")) for p in PERGUNTAS]

def calcular_disc(form):
    """Lê as notas 1-4 de cada opção (name=disc_<pergunta>_<letra>) e soma por perfil.
    Retorna (respostas, totais) ou (None, mensagem_de_erro)."""
    resp, tot = {}, dict.fromkeys("DISC", 0)
    for p in DISC["perguntas"]:
        notas = {}
        for o in p["opcoes"]:
            v = form.get(f"disc_{p['n']}_{o['letra']}", "")
            if v not in ("1", "2", "3", "4"):
                return None, f"Teste DISC: dê uma nota de 1 a 4 para cada opção da pergunta {p['n']}."
            notas[o["letra"]] = int(v)
            tot[o["perfil"]] += int(v)
        if sorted(notas.values()) != [1, 2, 3, 4]:
            return None, f"Teste DISC, pergunta {p['n']}: use cada número (1, 2, 3 e 4) uma única vez, sem empates."
        resp[str(p["n"])] = notas
    return (resp, tot), None

# ---------- segurança ----------
def usuario():
    return db.session.get(User, session.get("uid")) if session.get("uid") else None

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        u = usuario()
        if not u or not u.ativo:
            return redirect(url_for("login"))
        return f(*a, **k)
    return w

def gerencia_required(f):
    @wraps(f)
    @login_required
    def w(*a, **k):
        if usuario().perfil != "Gerência":
            abort(403)
        return f(*a, **k)
    return w

@app.before_request
def csrf():
    session.setdefault("csrf", secrets.token_hex(16))
    if request.method == "POST":
        tok = request.form.get("csrf") or request.headers.get("X-CSRF")
        if not tok or not secrets.compare_digest(tok, session["csrf"]):
            abort(400)

@app.context_processor
def ctx():
    return dict(me=usuario(), csrf_token=session.get("csrf"), ETAPAS=ETAPAS,
                ano=datetime.now().year, UNIDADES_RODAPE=UNIDADES)

def minha_vaga_or_404(vid):
    v = db.get_or_404(Vaga, vid)
    if v.owner_id != usuario().id:
        abort(403)
    return v

UNIDADES = [("Campinas", "(19) 2515-4878"), ("São Paulo", "(11) 3082-2222"),
            ("Valinhos", "(19) 3517-9797"), ("Barra Bonita", "(14) 98807-4628")]

# ---------- parte pública ----------
@app.route("/")
def index():
    vagas = Vaga.query.filter_by(status="aberta").order_by(Vaga.criada.desc()).all()
    return render_template("index.html", vagas=vagas, UNIDADES=UNIDADES)

@app.route("/vagas/<int:vid>")
def vaga(vid):
    v = db.get_or_404(Vaga, vid)
    if v.status != "aberta":
        abort(404)
    return render_template("vaga.html", v=v)

@app.route("/vagas/<int:vid>/candidatar", methods=["GET", "POST"])
def candidatar(vid):
    v = db.get_or_404(Vaga, vid)
    if v.status != "aberta":
        abort(404)
    if request.method == "POST":
        f = request.form
        if not f.get("lgpd"):
            flash("É necessário aceitar a política de privacidade para enviar.", "erro")
        elif not all(f.get(c, "").strip() for c in ("nome", "telefone", "email")):
            flash("Preencha nome, telefone e e-mail.", "erro")
        elif any(not f.get(p["id"], "").strip() for p in PERGUNTAS):
            flash("Responda todas as perguntas do questionário.", "erro")
        else:
            disc, erro = calcular_disc(f)
            if erro:
                flash(erro, "erro")
            else:
                resp, tot = disc
                db.session.add(Candidato(
                    vaga_id=v.id, nome=f["nome"].strip(), telefone=f["telefone"].strip(),
                    email=f["email"].strip().lower(),
                    respostas=json.dumps({p["id"]: f[p["id"]].strip() for p in PERGUNTAS}),
                    disc_respostas=json.dumps(resp), disc_d=tot["D"], disc_i=tot["I"],
                    disc_s=tot["S"], disc_c=tot["C"]))
                db.session.commit()
                return redirect(url_for("obrigado"))
    return render_template("candidatura.html", v=v, perguntas=PERGUNTAS, disc=DISC["perguntas"], form=request.form)

@app.route("/obrigado")
def obrigado():
    return render_template("obrigado.html")

@app.route("/privacidade")
def privacidade():
    return render_template("privacidade.html")

# ---------- autenticação ----------
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if u and u.ativo and check_password_hash(u.senha_hash, request.form.get("senha", "")):
            session.clear(); session["uid"] = u.id
            return redirect(url_for("dashboard"))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("login.html")

@app.route("/admin/sair", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------- painel ----------
@app.route("/admin")
@login_required
def dashboard():
    u = usuario()
    vagas = Vaga.query.filter_by(owner_id=u.id).all()
    ids = [v.id for v in vagas]
    cands = Candidato.query.filter(Candidato.vaga_id.in_(ids)).all() if ids else []
    por_etapa = {e: sum(c.etapa == e for c in cands) for e in ETAPAS}
    por_vaga = [(v, sum(c.vaga_id == v.id for c in v.candidatos)) for v in vagas]
    total = len(cands)
    conv = round(100 * por_etapa["Aprovado"] / total, 1) if total else 0
    return render_template("dashboard.html", abertas=sum(v.status == "aberta" for v in vagas),
                           total=total, conv=conv, por_etapa=por_etapa, por_vaga=por_vaga)

@app.route("/admin/vagas")
@login_required
def vagas_admin():
    vagas = Vaga.query.filter_by(owner_id=usuario().id).order_by(Vaga.criada.desc()).all()
    return render_template("vagas_admin.html", vagas=vagas)

@app.route("/admin/vagas/nova", methods=["GET", "POST"])
@app.route("/admin/vagas/<int:vid>/editar", methods=["GET", "POST"])
@login_required
def vaga_form(vid=None):
    v = minha_vaga_or_404(vid) if vid else Vaga(owner_id=usuario().id)
    if request.method == "POST":
        for c in ("titulo", "area", "local", "descricao", "requisitos", "atividades", "piso"):
            setattr(v, c, request.form.get(c, "").strip())
        if not v.titulo:
            flash("Informe o título da vaga.", "erro")
        else:
            db.session.add(v); db.session.commit()
            flash("Vaga salva.", "ok")
            return redirect(url_for("vagas_admin"))
    return render_template("vaga_form.html", v=v)

@app.route("/admin/vagas/<int:vid>/status", methods=["POST"])
@login_required
def vaga_status(vid):
    v = minha_vaga_or_404(vid)
    novo = request.form.get("status")
    if novo in ("aberta", "pausada", "encerrada"):
        v.status = novo; db.session.commit()
        flash({"aberta": "Vaga reaberta.", "pausada": "Vaga pausada.", "encerrada": "Vaga encerrada."}[novo], "ok")
    return redirect(url_for("vagas_admin"))

@app.route("/admin/vagas/<int:vid>/kanban")
@login_required
def kanban(vid):
    v = minha_vaga_or_404(vid)
    return render_template("kanban.html", v=v,
                           cols={e: [c for c in v.candidatos if c.etapa == e] for e in ETAPAS})

def meu_candidato(cid):
    c = db.get_or_404(Candidato, cid)
    minha_vaga_or_404(c.vaga_id)
    return c

@app.route("/admin/candidatos/<int:cid>/etapa", methods=["POST"])
@login_required
def mover(cid):
    c = meu_candidato(cid)
    etapa = (request.get_json(silent=True) or {}).get("etapa")
    if etapa not in ETAPAS:
        abort(400)
    c.etapa = etapa; db.session.commit()
    return jsonify(ok=True)

@app.route("/admin/candidatos/<int:cid>", methods=["GET", "POST"])
@login_required
def candidato(cid):
    c = meu_candidato(cid)
    if request.method == "POST":
        c.entrevistado = request.form.get("entrevistado") == "sim"
        c.data_entrevista = request.form.get("data_entrevista") or None
        c.parecer = request.form.get("parecer", "").strip()
        if request.form.get("etapa") in ETAPAS:
            c.etapa = request.form["etapa"]
        db.session.commit(); flash("Perfil atualizado.", "ok")
        return redirect(url_for("candidato", cid=cid))
    return render_template("candidato.html", c=c, PERFIS=PERFIS, DISC=DISC)

# ---------- usuários (somente Gerência) ----------
@app.route("/admin/usuarios")
@gerencia_required
def usuarios():
    return render_template("usuarios.html", users=User.query.order_by(User.nome).all())

@app.route("/admin/usuarios/novo", methods=["GET", "POST"])
@gerencia_required
def usuario_novo():
    if request.method == "POST":
        f = request.form
        email = f.get("email", "").strip().lower()
        if not (f.get("nome", "").strip() and email and len(f.get("senha", "")) >= 8):
            flash("Informe nome, e-mail e uma senha com pelo menos 8 caracteres.", "erro")
        elif not email.endswith("@grupoaltamed.com.br"):
            flash("Use um e-mail @grupoaltamed.com.br.", "erro")
        elif User.query.filter_by(email=email).first():
            flash("Já existe um usuário com este e-mail.", "erro")
        else:
            db.session.add(User(nome=f["nome"].strip(), email=email, perfil=f.get("perfil", "Responsável"),
                                ativo=f.get("ativo") == "on", senha_hash=generate_password_hash(f["senha"])))
            db.session.commit(); flash("Usuário cadastrado.", "ok")
            return redirect(url_for("usuarios"))
    return render_template("usuario_form.html")

# ---------- seed ----------
def seed():
    db.create_all()
    if User.query.first():
        return
    senha = os.environ.get("SENHA_INICIAL", "Altamed@2026")
    base = [("Gerência Altamed", "gerencia@grupoaltamed.com.br", "Gerência"),
            ("Lucas Navarrias", "lucas.navarrias@grupoaltamed.com.br", "Responsável"),
            ("Alberto Tavares", "alberto.tavares@grupoaltamed.com.br", "Responsável")]
    us = [User(nome=n, email=e, perfil=p, senha_hash=generate_password_hash(senha)) for n, e, p in base]
    db.session.add_all(us); db.session.commit()
    db.session.add_all([
        Vaga(titulo="Técnico(a) de Segurança do Trabalho", area="SST", local="Presencial", piso="A combinar",
             descricao="Atuar na gestão de riscos ocupacionais das empresas atendidas pelo Grupo Altamed.",
             requisitos="Curso técnico completo\nRegistro no MTE\nConhecimento das NRs", atividades="Inspeções e laudos\nTreinamentos\nElaboração de PGR", owner_id=us[1].id),
        Vaga(titulo="Atendente de Clínica Ocupacional", area="Atendimento", local="Presencial", piso="A combinar",
             descricao="Recepção e agendamento de exames ocupacionais.",
             requisitos="Ensino médio completo\nBoa comunicação", atividades="Receber pacientes\nAgendar exames\nEmitir documentos", owner_id=us[2].id)])
    db.session.commit()

with app.app_context():
    seed()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
