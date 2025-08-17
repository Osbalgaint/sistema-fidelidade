import os
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sua_chave_secreta_aqui')  # Defina uma chave secreta no Render

# Conexão com banco de dados
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn

# Cria tabelas de clientes, pedidos e usuarios
conn = get_db_connection()
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    card_id TEXT UNIQUE NOT NULL,
    ultimo_pagamento DATE,
    creditos INTEGER NOT NULL,
    data_expiracao DATE,
    celular TEXT NOT NULL
)''')
c.execute('''CREATE TABLE IF NOT EXISTS pedidos (
    id SERIAL PRIMARY KEY,
    card_id TEXT NOT NULL,
    nome_cliente TEXT NOT NULL,
    empresa TEXT NOT NULL,
    quantidade_deduzida INTEGER NOT NULL,
    horario TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)''')
c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    login TEXT UNIQUE NOT NULL,
    senha TEXT
)''')
conn.commit()
conn.close()

# Função para verificar autenticação
def usuario_autenticado():
    return 'login' in session

# Função para validar login
def validar_login(login, senha):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT senha FROM usuarios WHERE login = %s", (login,))
    result = c.fetchone()
    conn.close()
    if result and result['senha'] and result['senha'] == senha:
        return True
    return False

# Função para configurar senha
def configurar_senha(login, senha, confirmar_senha):
    if senha != confirmar_senha:
        return False, "Erro: As senhas não coincidem!"
    if login not in ['JORDANA', 'NETO', 'HUGO', 'SIMONE', 'VITÓRIA', 'MORGANA', 'HENRIQUE', 'JOÃO', 'ÉRIKA', 'VIVIANA']:
        return False, "Erro: Login inválido!"
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT senha FROM usuarios WHERE login = %s", (login,))
    result = c.fetchone()
    if result:
        if result['senha'] is not None:
            conn.close()
            return False, "Erro: Este usuário já possui uma senha configurada!"
        c.execute("UPDATE usuarios SET senha = %s WHERE login = %s", (senha, login))
        conn.commit()
        conn.close()
        return True, "Senha configurada com sucesso!"
    conn.close()
    return False, "Erro: Login não encontrado!"

def validar_id(card_id):
    if not card_id.startswith('CARD'):
        return False, "Erro: O ID do cartão deve começar com 'CARD'."
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT card_id FROM clientes WHERE card_id = %s", (card_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return False, "Erro: Este ID já está cadastrado."
    return True, ""

def buscar_nome_cliente(card_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT nome, celular FROM clientes WHERE card_id = %s", (card_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return True, result['nome'], result['celular']
    return False, "Cliente não encontrado", ""

def listar_clientes():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT card_id, nome FROM clientes ORDER BY id ASC")
    result = c.fetchall()
    conn.close()
    return [(row['card_id'], row['nome']) for row in result]

def excluir_cliente(card_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT nome FROM clientes WHERE card_id = %s", (card_id,))
    result = c.fetchone()
    if result:
        c.execute("DELETE FROM clientes WHERE card_id = %s", (card_id,))
        c.execute("DELETE FROM pedidos WHERE card_id = %s", (card_id,))
        conn.commit()
        conn.close()
        return "Cliente excluído com sucesso!"
    conn.close()
    return "Cliente não encontrado."

def atualizar_nome_cliente(card_id, novo_nome, novo_celular):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT nome FROM clientes WHERE card_id = %s", (card_id,))
    result = c.fetchone()
    if result:
        c.execute("UPDATE clientes SET nome = %s, celular = %s WHERE card_id = %s", (novo_nome, novo_celular, card_id))
        c.execute("UPDATE pedidos SET nome_cliente = %s WHERE card_id = %s", (novo_nome, card_id))
        conn.commit()
        conn.close()
        return "Cliente atualizado com sucesso!"
    conn.close()
    return "Cliente não encontrado."

def cadastrar_cliente(nome, card_id, celular):
    hoje = datetime.now().date()
    expiracao = hoje + timedelta(days=30)
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO clientes (nome, card_id, ultimo_pagamento, creditos, data_expiracao, celular) VALUES (%s, %s, %s, %s, %s, %s)",
                  (nome, card_id, str(hoje), 10, str(expiracao), celular))
        conn.commit()
        conn.close()
        return "Cliente cadastrado com sucesso! Créditos iniciais: 10. Créditos poderão ser utilizados para descontos de 50% em pizzas da STOUT PIZZA ou alimentos no CHAAAMA CHOPP."
    except psycopg.errors.UniqueViolation:
        conn.close()
        return "Erro: ID do cartão já existe."

def recarregar_creditos(card_id):
    hoje = datetime.now().date()
    expiracao = hoje + timedelta(days=30)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT nome FROM clientes WHERE card_id = %s", (card_id,))
    result = c.fetchone()
    if result:
        c.execute("UPDATE clientes SET creditos = %s, ultimo_pagamento = %s, data_expiracao = %s WHERE card_id = %s",
                  (10, str(hoje), str(expiracao), card_id))
        conn.commit()
        conn.close()
        return "Créditos recarregados para 10 (não cumulativos)!"
    conn.close()
    return "Cliente não encontrado."

def adicionar_credito_manual(card_id, quantidade):
    try:
        quantidade = int(quantidade)
        if quantidade <= 0:
            return "Erro: A quantidade deve ser maior que zero."
    except ValueError:
        return "Erro: Insira um número válido."
    
    hoje = datetime.now().date()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT creditos, data_expiracao, nome FROM clientes WHERE card_id = %s", (card_id,))
    result = c.fetchone()
    if result:
        creditos = result['creditos']
        nome_cliente = result['nome']
        expiracao = result['data_expiracao']
        expiracao_date = datetime.strptime(str(expiracao), '%Y-%m-%d').date() if expiracao else hoje
        if hoje > expiracao_date:
            conn.close()
            return "Créditos expirados. Necessário recarregar."
        novo_creditos = creditos + quantidade
        c.execute("UPDATE clientes SET creditos = %s WHERE card_id = %s", (novo_creditos, card_id))
        c.execute("INSERT INTO pedidos (card_id, nome_cliente, empresa, quantidade_deduzida) VALUES (%s, %s, %s, %s)",
                  (card_id, nome_cliente, 'Adição Manual', quantidade))
        conn.commit()
        conn.close()
        return f"{quantidade} crédito(s) adicionado(s) manualmente. Créditos totais: {novo_creditos}"
    conn.close()
    return "Cliente não encontrado."

def registrar_pedido(card_id, nome_cliente, empresa, quantidade_deduzida):
    empresa_historico = 'CHAMA' if empresa == 'CHAAAMA CHOPP' else empresa
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO pedidos (card_id, nome_cliente, empresa, quantidade_deduzida) VALUES (%s, %s, %s, %s)",
              (card_id, nome_cliente, empresa_historico, quantidade_deduzida))
    conn.commit()
    conn.close()

def deduzir_credito(card_id, quantidade, empresa):
    try:
        quantidade = int(quantidade)
        if quantidade <= 0:
            return "Erro: A quantidade deve ser maior que zero."
    except ValueError:
        return "Erro: Insira um número válido."
    
    if empresa not in ['STOUT PIZZA', 'CHAAAMA CHOPP']:
        return "Erro: Empresa inválida."
    
    hoje = datetime.now().date()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT creditos, data_expiracao, nome FROM clientes WHERE card_id = %s", (card_id,))
    result = c.fetchone()
    if result:
        creditos = result['creditos']
        expiracao = result['data_expiracao']
        nome_cliente = result['nome']
        expiracao_date = datetime.strptime(str(expiracao), '%Y-%m-%d').date() if expiracao else hoje
        if hoje > expiracao_date:
            conn.close()
            return "Créditos expirados. Necessário recarregar."
        if creditos >= quantidade:
            novo_creditos = creditos - quantidade
            c.execute("UPDATE clientes SET creditos = %s WHERE card_id = %s", (novo_creditos, card_id))
            c.execute("INSERT INTO pedidos (card_id, nome_cliente, empresa, quantidade_deduzida) VALUES (%s, %s, %s, %s)",
                      (card_id, nome_cliente, 'CHAMA' if empresa == 'CHAAAMA CHOPP' else empresa, -quantidade))
            conn.commit()
            conn.close()
            return f"{quantidade} crédito(s) deduzido(s) para {'CHAMA' if empresa == 'CHAAAMA CHOPP' else empresa}. Créditos restantes: {novo_creditos}"
        conn.close()
        return f"Erro: Créditos insuficientes. Disponível: {creditos}, solicitado: {quantidade}."
    conn.close()
    return "Cliente não encontrado."

def obter_historico(card_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT empresa, quantidade_deduzida, horario FROM pedidos WHERE card_id = %s ORDER BY horario DESC", (card_id,))
    result = c.fetchall()
    conn.close()
    return result

def buscar_info_cliente(card_id):
    hoje = datetime.now().date()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT nome, creditos, data_expiracao FROM clientes WHERE card_id = %s", (card_id,))
    result = c.fetchone()
    conn.close()
    if result:
        nome = result['nome']
        creditos = result['creditos']
        expiracao = result['data_expiracao']
        expiracao_date = datetime.strptime(str(expiracao), '%Y-%m-%d').date() if expiracao else hoje
        if hoje > expiracao_date:
            dias_restantes = "Expirado"
        else:
            dias_restantes = (expiracao_date - hoje).days
        expiracao_formatada = expiracao_date.strftime('%d/%m/%Y')
        return nome, creditos, dias_restantes, expiracao_formatada
    return "Cliente não encontrado", None, None, None

@app.route('/login', methods=['GET', 'POST'])
def login():
    mensagem = ""
    if request.method == 'POST':
        login = request.form.get('login')
        senha = request.form.get('senha')
        if validar_login(login, senha):
            session['login'] = login
            return redirect(url_for('index'))
        mensagem = "Login ou senha inválidos!"
    return render_template('login.html', mensagem=mensagem)

@app.route('/primeiro_acesso', methods=['GET', 'POST'])
def primeiro_acesso():
    mensagem = ""
    if request.method == 'POST':
        login = request.form.get('login')
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        sucesso, mensagem = configurar_senha(login, senha, confirmar_senha)
        if sucesso:
            session['login'] = login
            return redirect(url_for('index'))
    return render_template('primeiro_acesso.html', mensagem=mensagem)

@app.route('/', methods=['GET', 'POST'])
def index():
    if not usuario_autenticado():
        return redirect(url_for('login'))
    mensagem = ""
    card_id_display = ""
    nome = ""
    creditos = ""
    dias = ""
    expiracao = ""
    mostrar_empresas = False
    mostrar_quantidade = False
    empresa_selecionada = ""
    mostrar_adicionar_credito = False
    if request.method == 'POST':
        action = request.form.get('action')
        card_id = request.form.get('card_id')
        if not card_id:
            mensagem = "Erro: ID do cartão é obrigatório!"
        elif action == 'buscar':
            nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
            card_id_display = card_id if nome != "Cliente não encontrado" else ""
            if creditos is None:
                nome = "Cliente não encontrado"
        elif action == 'recarregar':
            senha = request.form.get('senha')
            if senha == "03842789":
                mensagem = recarregar_creditos(card_id)
                nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
                card_id_display = card_id
            else:
                mensagem = "Senha incorreta!"
        elif action == 'adicionar_credito_manual':
            senha = request.form.get('senha')
            if senha == "03842789":
                nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
                card_id_display = card_id if nome != "Cliente não encontrado" else ""
                if creditos is not None:
                    mostrar_adicionar_credito = True
                else:
                    mensagem = "Cliente não encontrado"
            else:
                mensagem = "Senha incorreta!"
        elif action == 'confirmar_adicao':
            quantidade = request.form.get('quantidade')
            mensagem = adicionar_credito_manual(card_id, quantidade)
            nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
            card_id_display = card_id
        elif action == 'mostrar_empresas':
            nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
            card_id_display = card_id if nome != "Cliente não encontrado" else ""
            if creditos is not None:
                mostrar_empresas = True
        elif action == 'selecionar_empresa':
            empresa = request.form.get('empresa')
            if empresa not in ['STOUT PIZZA', 'CHAAAMA CHOPP']:
                mensagem = "Erro: Empresa inválida!"
            else:
                nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
                card_id_display = card_id if nome != "Cliente não encontrado" else ""
                if creditos is not None:
                    mostrar_quantidade = True
                    empresa_selecionada = empresa
        elif action == 'deduzir':
            quantidade = request.form.get('quantidade')
            empresa = request.form.get('empresa')
            if empresa not in ['STOUT PIZZA', 'CHAAAMA CHOPP']:
                mensagem = "Erro: Empresa inválida!"
            else:
                mensagem = deduzir_credito(card_id, quantidade, empresa)
                nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
                card_id_display = card_id
    return render_template('index.html', mensagem=mensagem, card_id_display=card_id_display, nome=nome, creditos=creditos, dias=dias, expiracao=expiracao, mostrar_empresas=mostrar_empresas, mostrar_quantidade=mostrar_quantidade, empresa_selecionada=empresa_selecionada, mostrar_adicionar_credito=mostrar_adicionar_credito)

@app.route('/historico', methods=['GET', 'POST'])
def historico():
    if not usuario_autenticado():
        return redirect(url_for('login'))
    mensagem = ""
    historico = []
    card_id_display = ""
    mostrar_formulario = False
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'verificar_senha':
            senha = request.form.get('senha')
            if senha == "03842789":
                mostrar_formulario = True
            else:
                mensagem = "Senha incorreta!"
        elif action == 'buscar_historico':
            card_id = request.form.get('card_id')
            if not card_id:
                mensagem = "Erro: ID do cartão é obrigatório!"
            else:
                historico = obter_historico(card_id)
                card_id_display = card_id
                if not historico:
                    mensagem = "Nenhum histórico encontrado para este cliente."
    return render_template('historico.html', mensagem=mensagem, historico=historico, card_id_display=card_id_display, mostrar_formulario=mostrar_formulario)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if not usuario_autenticado():
        return redirect(url_for('login'))
    mensagem = ""
    card_id = "CARD"
    if request.method == 'POST':
        nome = request.form.get('nome')
        card_id = request.form.get('card_id')
        celular = request.form.get('celular')
        if not nome or not card_id or not celular:
            mensagem = "Erro: Preencha todos os campos!"
        else:
            valido, erro = validar_id(card_id)
            if not valido:
                mensagem = erro
            else:
                mensagem = cadastrar_cliente(nome, card_id, celular)
                if "sucesso" in mensagem.lower():
                    return redirect(url_for('index'))
    return render_template('cadastro.html', mensagem=mensagem, card_id=card_id)

@app.route('/editar', methods=['GET', 'POST'])
def editar():
    if not usuario_autenticado():
        return redirect(url_for('login'))
    mensagem = ""
    card_id = ""
    nome_atual = ""
    celular_atual = ""
    mostrar_formulario = False
    if request.method == 'POST':
        action = request.form.get('action')
        card_id = request.form.get('card_id')
        if action == 'buscar':
            if not card_id:
                mensagem = "Erro: ID do cartão é obrigatório!"
            else:
                valido, nome_atual, celular_atual = buscar_nome_cliente(card_id)
                if valido:
                    mostrar_formulario = True
                else:
                    mensagem = nome_atual
        elif action == 'editar':
            novo_nome = request.form.get('novo_nome')
            novo_celular = request.form.get('novo_celular')
            if not novo_nome or not novo_celular:
                mensagem = "Erro: Preencha nome e celular!"
            else:
                mensagem = atualizar_nome_cliente(card_id, novo_nome, novo_celular)
                if "sucesso" in mensagem.lower():
                    return redirect(url_for('index'))
                valido, nome_atual, celular_atual = buscar_nome_cliente(card_id)
                mostrar_formulario = True
    return render_template('editar.html', mensagem=mensagem, card_id=card_id, nome_atual=nome_atual, celular_atual=celular_atual, mostrar_formulario=mostrar_formulario)

@app.route('/cliente', methods=['GET', 'POST'])
def cliente():
    if not usuario_autenticado():
        return redirect(url_for('login'))
    mensagem = None
    cliente = None
    if request.method == 'POST':
        celular = request.form['celular'].strip()
        if not celular:
            mensagem = "Celular não pode estar vazio."
        else:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM clientes WHERE celular = %s", (celular,))
            cliente = c.fetchone()
            conn.close()
            if not cliente:
                mensagem = "Nenhum cliente encontrado com esse número de celular."
    return render_template('cliente.html', mensagem=mensagem, cliente=cliente)

@app.route('/consulta')
def consulta():
    if not usuario_autenticado():
        return redirect(url_for('login'))
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT card_id, nome, creditos, data_expiracao FROM clientes ORDER BY id ASC")
    clientes = c.fetchall()
    conn.close()
    return render_template('consulta.html', clientes=clientes)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)