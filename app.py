import os
import re
import sqlite3
from datetime import date, datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for
from jinja2 import DictLoader
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "scql.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "scql-prototipo-ads-2026")

STATUS = ["Novo", "Contatado", "Qualificado", "Proposta", "Ganho", "Perdido"]
ORIGENS = ["LinkedIn", "Indicação", "E-mail", "Telefone"]
TIPOS_INTERACAO = ["Ligação", "E-mail", "WhatsApp", "LinkedIn", "Reunião"]

TABELA_PORTE = {"Micro": 10, "Pequena": 20, "Média": 30, "Grande": 40}
TABELA_ORIGEM = {"LinkedIn": 25, "Indicação": 20, "E-mail": 5, "Telefone": 5}


def conectar():
    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def calcular_score(porte, cargo, origem):
    score = TABELA_PORTE.get((porte or "").strip(), 5)
    score += TABELA_ORIGEM.get((origem or "").strip(), 5)
    cargo = (cargo or "").lower()
    if any(p in cargo for p in ("diretor", "sócio", "socio", "ceo", "presidente", "proprietário", "proprietario", "head")):
        score += 35
    elif "gerente" in cargo:
        score += 25
    elif any(p in cargo for p in ("coordenador", "supervisor", "analista")):
        score += 15
    elif cargo:
        score += 5
    return min(score, 100)


def inicializar_banco():
    conexao = conectar()
    caminho_schema = os.path.join(BASE_DIR, "schema.sql")
    with open(caminho_schema, encoding="utf-8") as arquivo:
        conexao.executescript(arquivo.read())
    popular_dados_iniciais(conexao)
    conexao.commit()
    conexao.close()


def popular_dados_iniciais(conexao):
    if conexao.execute("SELECT COUNT(*) FROM usuario").fetchone()[0]:
        return

    senha = generate_password_hash("123456")
    conexao.executemany(
        "INSERT INTO usuario (nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?)",
        [
            ("Kariny Kitazawa", "kariny@empresa.com.br", senha, "consultor"),
            ("Gestor Comercial", "gestor@empresa.com.br", senha, "gestor"),
        ],
    )

    conexao.executemany(
        "INSERT INTO empresa (razao_social, cnpj, segmento, porte, cidade, uf) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("Alfa Contact Center", "12.345.678/0001-90", "Contact center", "Grande", "São Paulo", "SP"),
            ("Norte Serviços", "23.456.789/0001-01", "Serviços", "Média", "Guarulhos", "SP"),
            ("Vega Cobranças", "34.567.890/0001-12", "Cobrança", "Média", "Osasco", "SP"),
            ("Prisma Atendimento", "45.678.901/0001-23", "Atendimento", "Grande", "Barueri", "SP"),
            ("Delta Telecom", "56.789.012/0001-34", "Telecom", "Média", "São Paulo", "SP"),
            ("Orion Contact Center", "67.890.123/0001-45", "Contact center", "Pequena", "Santo André", "SP"),
        ],
    )

    # Scores fixos para que a tela coincida com os protótipos do relatório
    conexao.executemany(
        """INSERT INTO lead (id_empresa, id_usuario, nome_contato, cargo, email, telefone,
                             origem, status, score, data_captura)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, 1, "Marina Prado", "Diretora de Operações", "marina.prado@alfacontact.com.br",
             "(11) 98888-1010", "LinkedIn", "Qualificado", 82, "2026-10-12"),
            (2, 1, "Rafael Lima", "Gerente de TI", "rafael.lima@norteservicos.com.br",
             "(11) 97777-2020", "LinkedIn", "Contatado", 54, "2026-10-12"),
            (3, 1, "Camila Souza", "Head Comercial", "camila.souza@vegacobrancas.com.br",
             "(11) 96666-3030", "Indicação", "Novo", 61, "2026-10-11"),
            (4, 1, "Diego Matos", "Sócio", "diego.matos@prismaatendimento.com.br",
             "(11) 95555-4040", "LinkedIn", "Proposta", 90, "2026-10-10"),
            (5, 1, "Bruno Alves", "Head de Operações", "bruno.alves@deltatelecom.com.br",
             "(11) 94444-5050", "LinkedIn", "Qualificado", 78, "2026-10-09"),
            (6, 1, "Patrícia Nunes", "Coordenadora de Atendimento", "patricia.nunes@orioncc.com.br",
             "(11) 93333-6060", "Telefone", "Contatado", 40, "2026-10-09"),
        ],
    )

    conexao.executemany(
        """INSERT INTO interacao (id_lead, id_usuario, tipo, data_hora, resumo, proximo_passo)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (1, 1, "LinkedIn", "2026-10-08 09:20:00", "Primeiro contato, conexão aceita.",
             "Localizar e-mail e telefone"),
            (1, 1, "E-mail", "2026-10-10 14:05:00", "Envio de apresentação institucional.",
             "Aguardar retorno"),
            (1, 1, "Ligação", "2026-10-12 10:30:00", "Interesse em rota SIP, pediu proposta.",
             "Enviar proposta comercial"),
            (4, 1, "Ligação", "2026-10-11 16:00:00", "Operação com três operadoras, aberta a teste.",
             "Agendar teste de rota SIP"),
        ],
    )


def validar_lead(dados):
    obrigatorios = {
        "razao_social": "Razão social",
        "cnpj": "CNPJ",
        "nome_contato": "Nome do contato",
        "origem": "Origem da captura",
    }
    for campo, rotulo in obrigatorios.items():
        if not (dados.get(campo) or "").strip():
            raise ValueError(f"O campo {rotulo} é obrigatório.")

    digitos_cnpj = re.sub(r"\D", "", dados["cnpj"])
    if len(digitos_cnpj) != 14:
        raise ValueError("CNPJ inválido. Informe os 14 dígitos no formato 00.000.000/0000-00.")

    email = (dados.get("email") or "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", email):
        raise ValueError("E-mail inválido. Verifique o formato nome@empresa.com.br.")


def cadastrar_lead(conexao, dados):
    validar_lead(dados)
    cursor = conexao.cursor()
    try:
        registro = cursor.execute(
            "SELECT id_empresa FROM empresa WHERE cnpj = ?", (dados["cnpj"].strip(),)
        ).fetchone()

        if registro:
            id_empresa = registro["id_empresa"]
        else:
            cursor.execute(
                """INSERT INTO empresa (razao_social, cnpj, segmento, porte, cidade, uf)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    dados["razao_social"].strip(),
                    dados["cnpj"].strip(),
                    dados.get("segmento"),
                    dados.get("porte"),
                    dados.get("cidade"),
                    dados.get("uf"),
                ),
            )
            id_empresa = cursor.lastrowid

        score = calcular_score(dados.get("porte"), dados.get("cargo"), dados["origem"])
        cursor.execute(
            """INSERT INTO lead (id_empresa, id_usuario, nome_contato, cargo, email,
                                 telefone, origem, status, score, data_captura)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                id_empresa,
                session["usuario_id"],
                dados["nome_contato"].strip(),
                dados.get("cargo"),
                dados.get("email"),
                dados.get("telefone"),
                dados["origem"],
                "Novo",
                score,
                dados.get("data_captura") or date.today().isoformat(),
            ),
        )
        conexao.commit()
        return cursor.lastrowid
    except sqlite3.Error as erro:
        conexao.rollback()
        raise RuntimeError(f"Falha ao gravar o lead: {erro}")


def consultar_leads(conexao, status=None, origem=None, id_usuario=None, inicio=None, fim=None):
    sql = [
        "SELECT l.id_lead, e.razao_social, l.nome_contato, l.cargo, l.origem,",
        "       l.status, l.score, l.data_captura, u.nome AS consultor",
        "FROM lead l",
        "INNER JOIN empresa e ON e.id_empresa = l.id_empresa",
        "INNER JOIN usuario u ON u.id_usuario = l.id_usuario",
        "WHERE 1 = 1",
    ]
    parametros = []

    if status:
        sql.append("AND l.status = ?")
        parametros.append(status)
    if origem:
        sql.append("AND l.origem = ?")
        parametros.append(origem)
    if id_usuario:
        sql.append("AND l.id_usuario = ?")
        parametros.append(id_usuario)
    if inicio and fim:
        sql.append("AND l.data_captura BETWEEN ? AND ?")
        parametros.extend([inicio, fim])

    sql.append("ORDER BY l.score DESC, l.data_captura DESC")
    return conexao.execute(" ".join(sql), parametros).fetchall()


def gerar_relatorio(conexao):
    return conexao.execute(
        """SELECT origem,
                  COUNT(*) AS captados,
                  SUM(CASE WHEN status IN ('Qualificado', 'Proposta', 'Ganho') THEN 1 ELSE 0 END) AS qualificados,
                  SUM(CASE WHEN status = 'Ganho' THEN 1 ELSE 0 END) AS ganhos
           FROM lead
           GROUP BY origem
           ORDER BY captados DESC"""
    ).fetchall()


@app.template_filter("data_br")
def data_br(valor):
    if not valor:
        return ""
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return valor


@app.template_filter("data_hora_br")
def data_hora_br(valor):
    if not valor:
        return ""
    try:
        return datetime.strptime(str(valor)[:16], "%Y-%m-%d %H:%M").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return valor


@app.context_processor
def injetar_globais():
    return {"status_opcoes": STATUS, "origem_opcoes": ORIGENS, "tipos_interacao": TIPOS_INTERACAO}


def exigir_login():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        conexao = conectar()
        usuario = conexao.execute(
            "SELECT * FROM usuario WHERE email = ? AND ativo = 1", (email,)
        ).fetchone()
        conexao.close()

        if usuario and check_password_hash(usuario["senha_hash"], senha):
            session["usuario_id"] = usuario["id_usuario"]
            session["usuario_nome"] = usuario["nome"]
            session["perfil"] = usuario["perfil"]
            return redirect(url_for("painel"))

        flash("E-mail ou senha incorretos.", "erro")

    return render_template("login.html", titulo="Acesso")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def painel():
    redirecionamento = exigir_login()
    if redirecionamento:
        return redirecionamento

    filtros = {
        "status": request.args.get("status", ""),
        "origem": request.args.get("origem", ""),
        "id_usuario": request.args.get("id_usuario", ""),
        "inicio": request.args.get("inicio", ""),
        "fim": request.args.get("fim", ""),
    }

    conexao = conectar()
    leads = consultar_leads(
        conexao,
        status=filtros["status"] or None,
        origem=filtros["origem"] or None,
        id_usuario=filtros["id_usuario"] or None,
        inicio=filtros["inicio"] or None,
        fim=filtros["fim"] or None,
    )
    usuarios = conexao.execute("SELECT id_usuario, nome FROM usuario ORDER BY nome").fetchall()
    conexao.close()

    return render_template("painel.html", titulo="Leads", leads=leads, usuarios=usuarios, filtros=filtros)


@app.route("/lead/novo", methods=["GET", "POST"])
def novo_lead():
    redirecionamento = exigir_login()
    if redirecionamento:
        return redirecionamento

    dados = request.form.to_dict()

    if request.method == "POST":
        conexao = conectar()
        try:
            id_lead = cadastrar_lead(conexao, dados)
            conexao.close()
            flash("Lead cadastrado com sucesso.", "sucesso")
            return redirect(url_for("detalhe_lead", id_lead=id_lead))
        except ValueError as erro:
            conexao.close()
            flash(str(erro), "erro")
        except RuntimeError as erro:
            conexao.close()
            flash(str(erro), "erro")

    if not dados:
        dados = {"data_captura": date.today().isoformat(), "origem": "LinkedIn"}

    return render_template("cadastro.html", titulo="Novo lead", dados=dados)


@app.route("/lead/<int:id_lead>")
def detalhe_lead(id_lead):
    redirecionamento = exigir_login()
    if redirecionamento:
        return redirecionamento

    conexao = conectar()
    lead = conexao.execute(
        """SELECT l.*, e.razao_social, e.cnpj, e.segmento, e.porte, e.cidade, e.uf
           FROM lead l
           INNER JOIN empresa e ON e.id_empresa = l.id_empresa
           WHERE l.id_lead = ?""",
        (id_lead,),
    ).fetchone()
    interacoes = conexao.execute(
        """SELECT i.*, u.nome AS autor
           FROM interacao i
           INNER JOIN usuario u ON u.id_usuario = i.id_usuario
           WHERE i.id_lead = ?
           ORDER BY i.data_hora DESC""",
        (id_lead,),
    ).fetchall()
    conexao.close()

    if not lead:
        flash("Lead não encontrado.", "erro")
        return redirect(url_for("painel"))

    return render_template("detalhe.html", titulo=lead["razao_social"], lead=lead, interacoes=interacoes)


@app.route("/lead/<int:id_lead>/interacao", methods=["POST"])
def registrar_interacao(id_lead):
    redirecionamento = exigir_login()
    if redirecionamento:
        return redirecionamento

    tipo = request.form.get("tipo", "").strip()
    resumo = request.form.get("resumo", "").strip()
    proximo_passo = request.form.get("proximo_passo", "").strip()

    if not tipo or not resumo:
        flash("Informe o tipo de contato e o resumo da interação.", "erro")
        return redirect(url_for("detalhe_lead", id_lead=id_lead))

    conexao = conectar()
    conexao.execute(
        """INSERT INTO interacao (id_lead, id_usuario, tipo, data_hora, resumo, proximo_passo)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (id_lead, session["usuario_id"], tipo, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         resumo, proximo_passo),
    )
    conexao.commit()
    conexao.close()

    flash("Interação registrada com sucesso.", "sucesso")
    return redirect(url_for("detalhe_lead", id_lead=id_lead))


@app.route("/lead/<int:id_lead>/status", methods=["POST"])
def alterar_status(id_lead):
    redirecionamento = exigir_login()
    if redirecionamento:
        return redirecionamento

    novo_status = request.form.get("status", "").strip()
    if novo_status not in STATUS:
        flash("Status inválido.", "erro")
        return redirect(url_for("detalhe_lead", id_lead=id_lead))

    conexao = conectar()
    conexao.execute("UPDATE lead SET status = ? WHERE id_lead = ?", (novo_status, id_lead))
    conexao.commit()
    conexao.close()

    flash(f"Status alterado para {novo_status}.", "sucesso")
    return redirect(url_for("detalhe_lead", id_lead=id_lead))


@app.route("/relatorio")
def relatorio():
    redirecionamento = exigir_login()
    if redirecionamento:
        return redirecionamento

    conexao = conectar()
    linhas = gerar_relatorio(conexao)
    conexao.close()

    captados = sum(linha["captados"] for linha in linhas)
    qualificados = sum(linha["qualificados"] for linha in linhas)
    ganhos = sum(linha["ganhos"] for linha in linhas)
    taxa = round((qualificados / captados) * 100, 1) if captados else 0.0

    return render_template(
        "relatorio.html",
        titulo="Relatório de conversão",
        linhas=linhas,
        captados=captados,
        qualificados=qualificados,
        ganhos=ganhos,
        taxa=taxa,
    )


TEMPLATES = {
    "base.html": """
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ titulo }} · SCQL</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: Arial, Helvetica, sans-serif; font-size: 14px;
         color: #1a1a1a; background: #f4f4f4; }
  header.topo { display: flex; align-items: center; gap: 24px; padding: 12px 24px;
                background: #1f2a37; color: #fff; }
  header.topo .marca { font-weight: bold; letter-spacing: 1px; }
  header.topo nav { display: flex; gap: 16px; flex: 1; }
  header.topo nav a { color: #d6dde6; text-decoration: none; }
  header.topo nav a:hover { color: #fff; }
  header.topo .usuario { font-size: 12px; color: #c3ccd6; }
  header.topo .usuario a { color: #d6dde6; }
  main { max-width: 1120px; margin: 24px auto; padding: 0 16px; }
  h1 { font-size: 20px; margin: 0 0 16px; }
  .aviso { padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; border: 1px solid; }
  .aviso.sucesso { background: #eef8ef; border-color: #b7dfb9; color: #1e5b25; }
  .aviso.erro { background: #fdf0ef; border-color: #f0bdb8; color: #7d1a12; }
  .filtros { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end;
             background: #fff; padding: 16px; border: 1px solid #d9d9d9; margin-bottom: 16px; }
  label { display: flex; flex-direction: column; font-size: 12px; color: #444; gap: 4px; }
  input, select { padding: 7px 8px; border: 1px solid #c4c4c4; border-radius: 3px;
                  font-size: 13px; background: #fff; }
  .btn { display: inline-block; padding: 8px 14px; border: 1px solid #1f2a37;
         background: #fff; color: #1f2a37; border-radius: 3px; font-size: 13px;
         text-decoration: none; cursor: pointer; }
  .btn.primario { background: #1f2a37; color: #fff; }
  table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9d9d9; }
  th, td { padding: 9px 10px; border-bottom: 1px solid #e6e6e6; text-align: left; font-size: 13px; }
  th { background: #f0f0f0; font-weight: bold; }
  .vazio { text-align: center; color: #777; padding: 24px; }
  .etiqueta { display: inline-block; padding: 2px 8px; border-radius: 10px;
              background: #eef1f5; border: 1px solid #ccd4de; font-size: 12px; }
  .cartao { background: #fff; border: 1px solid #d9d9d9; padding: 20px; margin-bottom: 16px; }
  .cartao h2 { font-size: 15px; margin: 0 0 12px; }
  .grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
  .indicadores { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                 gap: 16px; margin-bottom: 20px; }
  .indicador { background: #fff; border: 1px solid #d9d9d9; padding: 16px; }
  .indicador span { display: block; font-size: 12px; color: #666; margin-bottom: 6px; }
  .indicador strong { font-size: 22px; }
  .colunas { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 760px) { .colunas { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header class="topo">
  <span class="marca">SCQL</span>
  {% if session.get('usuario_nome') %}
  <nav>
    <a href="{{ url_for('painel') }}">Painel de leads</a>
    <a href="{{ url_for('novo_lead') }}">Novo lead</a>
    <a href="{{ url_for('relatorio') }}">Relatório</a>
  </nav>
  <span class="usuario">{{ session.usuario_nome }} · {{ session.perfil }} · <a href="{{ url_for('logout') }}">Sair</a></span>
  {% endif %}
</header>
<main>
  {% with mensagens = get_flashed_messages(with_categories=true) %}
    {% for categoria, texto in mensagens %}
      <div class="aviso {{ categoria }}">{{ texto }}</div>
    {% endfor %}
  {% endwith %}
  {% block corpo %}{% endblock %}
</main>
</body>
</html>
""",
    "login.html": """
{% extends "base.html" %}
{% block corpo %}
<div class="cartao" style="max-width: 380px; margin: 60px auto;">
  <h1>SCQL · Acesso ao sistema</h1>
  <form method="post">
    <label>E-mail<input type="email" name="email" required autofocus></label>
    <label style="margin-top: 12px;">Senha<input type="password" name="senha" required></label>
    <button class="btn primario" type="submit" style="margin-top: 16px; width: 100%;">Entrar</button>
  </form>
  <p style="font-size: 12px; color: #666; margin-top: 16px;">
    Usuários de teste: kariny@empresa.com.br (consultor) e gestor@empresa.com.br (gestor). Senha 123456.
  </p>
</div>
{% endblock %}
""",
    "painel.html": """
{% extends "base.html" %}
{% block corpo %}
<h1>Leads</h1>
<p><a class="btn primario" href="{{ url_for('novo_lead') }}">+ Novo lead</a></p>

<form class="filtros" method="get">
  <label>Status
    <select name="status">
      <option value="">Todos</option>
      {% for valor in status_opcoes %}
      <option value="{{ valor }}" {% if valor == filtros.status %}selected{% endif %}>{{ valor }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Origem
    <select name="origem">
      <option value="">Todas</option>
      {% for valor in origem_opcoes %}
      <option value="{{ valor }}" {% if valor == filtros.origem %}selected{% endif %}>{{ valor }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Consultor
    <select name="id_usuario">
      <option value="">Todos</option>
      {% for item in usuarios %}
      <option value="{{ item.id_usuario }}" {% if filtros.id_usuario|string == item.id_usuario|string %}selected{% endif %}>{{ item.nome }}</option>
      {% endfor %}
    </select>
  </label>
  <label>De <input type="date" name="inicio" value="{{ filtros.inicio }}"></label>
  <label>Até <input type="date" name="fim" value="{{ filtros.fim }}"></label>
  <button class="btn primario" type="submit">Filtrar</button>
  <a class="btn" href="{{ url_for('painel') }}">Limpar</a>
</form>

<table>
  <thead>
    <tr>
      <th>Empresa</th><th>Contato</th><th>Cargo</th><th>Origem</th>
      <th>Status</th><th>Score</th><th>Data</th><th>Ações</th>
    </tr>
  </thead>
  <tbody>
    {% for lead in leads %}
    <tr>
      <td>{{ lead.razao_social }}</td>
      <td>{{ lead.nome_contato }}</td>
      <td>{{ lead.cargo }}</td>
      <td>{{ lead.origem }}</td>
      <td><span class="etiqueta">{{ lead.status }}</span></td>
      <td>{{ lead.score }}</td>
      <td>{{ lead.data_captura|data_br }}</td>
      <td><a href="{{ url_for('detalhe_lead', id_lead=lead.id_lead) }}">Abrir</a></td>
    </tr>
    {% else %}
    <tr><td colspan="8" class="vazio">Nenhum lead encontrado com os filtros aplicados.</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
""",
    "cadastro.html": """
{% extends "base.html" %}
{% block corpo %}
<h1>Novo lead</h1>
<form method="post">
  <div class="cartao">
    <h2>Dados da empresa</h2>
    <div class="grade">
      <label>CNPJ<input name="cnpj" value="{{ dados.cnpj or '' }}" placeholder="00.000.000/0000-00" required></label>
      <label>Razão social<input name="razao_social" value="{{ dados.razao_social or '' }}" required></label>
      <label>Segmento<input name="segmento" value="{{ dados.segmento or '' }}"></label>
      <label>Porte
        <select name="porte">
          <option value="">Selecione</option>
          {% for porte in ['Micro', 'Pequena', 'Média', 'Grande'] %}
          <option value="{{ porte }}" {% if dados.porte == porte %}selected{% endif %}>{{ porte }}</option>
          {% endfor %}
        </select>
      </label>
      <label>Cidade<input name="cidade" value="{{ dados.cidade or '' }}"></label>
      <label>UF<input name="uf" value="{{ dados.uf or '' }}" maxlength="2"></label>
    </div>
  </div>

  <div class="cartao">
    <h2>Dados do contato</h2>
    <div class="grade">
      <label>Nome do contato<input name="nome_contato" value="{{ dados.nome_contato or '' }}" required></label>
      <label>Cargo<input name="cargo" value="{{ dados.cargo or '' }}"></label>
      <label>E-mail<input name="email" value="{{ dados.email or '' }}"></label>
      <label>Telefone<input name="telefone" value="{{ dados.telefone or '' }}"></label>
    </div>
  </div>

  <div class="cartao">
    <h2>Origem da captura</h2>
    <div class="grade">
      <label>Origem
        <select name="origem" required>
          {% for origem in origem_opcoes %}
          <option value="{{ origem }}" {% if dados.origem == origem %}selected{% endif %}>{{ origem }}</option>
          {% endfor %}
        </select>
      </label>
      <label>Ferramenta de enriquecimento
        <select name="ferramenta">
          <option value="">Não utilizada</option>
          {% for ferramenta in ['Localizador de e-mail', 'Localizador de telefone', 'Ambos'] %}
          <option value="{{ ferramenta }}" {% if dados.ferramenta == ferramenta %}selected{% endif %}>{{ ferramenta }}</option>
          {% endfor %}
        </select>
      </label>
      <label>Data da captura<input type="date" name="data_captura" value="{{ dados.data_captura or '' }}"></label>
    </div>
  </div>

  <button class="btn primario" type="submit">Salvar</button>
  <a class="btn" href="{{ url_for('painel') }}">Cancelar</a>
</form>
{% endblock %}
""",
    "detalhe.html": """
{% extends "base.html" %}
{% block corpo %}
<h1>{{ lead.razao_social }}</h1>
<p style="color: #555; margin-top: -8px;">
  CNPJ {{ lead.cnpj }} · {{ lead.segmento }} · {{ lead.porte }} · {{ lead.cidade }}/{{ lead.uf }}
</p>

<div class="colunas">
  <div class="cartao">
    <h2>Dados do contato</h2>
    <table>
      <tr><th>Nome</th><td>{{ lead.nome_contato }}</td></tr>
      <tr><th>Cargo</th><td>{{ lead.cargo }}</td></tr>
      <tr><th>E-mail</th><td>{{ lead.email }}</td></tr>
      <tr><th>Telefone</th><td>{{ lead.telefone }}</td></tr>
      <tr><th>Origem</th><td>{{ lead.origem }}</td></tr>
      <tr><th>Data da captura</th><td>{{ lead.data_captura|data_br }}</td></tr>
    </table>
    <form method="post" action="{{ url_for('alterar_status', id_lead=lead.id_lead) }}"
          style="display: flex; gap: 8px; align-items: flex-end; margin-top: 16px;">
      <label>Status
        <select name="status">
          {% for valor in status_opcoes %}
          <option value="{{ valor }}" {% if valor == lead.status %}selected{% endif %}>{{ valor }}</option>
          {% endfor %}
        </select>
      </label>
      <button class="btn" type="submit">Alterar status</button>
    </form>
  </div>

  <div class="cartao">
    <h2>Registrar interação</h2>
    <form method="post" action="{{ url_for('registrar_interacao', id_lead=lead.id_lead) }}">
      <label>Tipo
        <select name="tipo">
          {% for tipo in tipos_interacao %}
          <option value="{{ tipo }}">{{ tipo }}</option>
          {% endfor %}
        </select>
      </label>
      <label style="margin-top: 10px;">Resumo
        <input name="resumo" placeholder="O que foi tratado no contato" required>
      </label>
      <label style="margin-top: 10px;">Próximo passo
        <input name="proximo_passo" placeholder="Ação combinada">
      </label>
      <button class="btn primario" type="submit" style="margin-top: 14px;">Registrar interação</button>
    </form>
  </div>
</div>

<div class="cartao">
  <h2>Histórico de interações</h2>
  <table>
    <thead><tr><th>Data</th><th>Tipo</th><th>Resumo</th><th>Próximo passo</th><th>Autor</th></tr></thead>
    <tbody>
      {% for item in interacoes %}
      <tr>
        <td>{{ item.data_hora|data_hora_br }}</td>
        <td>{{ item.tipo }}</td>
        <td>{{ item.resumo }}</td>
        <td>{{ item.proximo_passo }}</td>
        <td>{{ item.autor }}</td>
      </tr>
      {% else %}
      <tr><td colspan="5" class="vazio">Nenhuma interação registrada.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
""",
    "relatorio.html": """
{% extends "base.html" %}
{% block corpo %}
<h1>Relatório de conversão</h1>

<div class="indicadores">
  <div class="indicador"><span>Leads captados</span><strong>{{ captados }}</strong></div>
  <div class="indicador"><span>Leads qualificados</span><strong>{{ qualificados }}</strong></div>
  <div class="indicador"><span>Negócios ganhos</span><strong>{{ ganhos }}</strong></div>
  <div class="indicador"><span>Taxa de conversão</span><strong>{{ taxa }}%</strong></div>
</div>

<table>
  <thead><tr><th>Origem</th><th>Captados</th><th>Qualificados</th><th>Ganhos</th><th>Taxa</th></tr></thead>
  <tbody>
    {% for linha in linhas %}
    <tr>
      <td>{{ linha.origem }}</td>
      <td>{{ linha.captados }}</td>
      <td>{{ linha.qualificados }}</td>
      <td>{{ linha.ganhos }}</td>
      <td>{{ ((linha.qualificados / linha.captados) * 100)|round(1) }}%</td>
    </tr>
    {% else %}
    <tr><td colspan="5" class="vazio">Nenhum lead cadastrado.</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
""",
}

app.jinja_loader = DictLoader(TEMPLATES)

inicializar_banco()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
