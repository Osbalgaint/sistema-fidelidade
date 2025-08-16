import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)

# Conexão com banco de dados
def get_db_connection():
    conn = sqlite3.connect('fidelidade.db')
    conn.row_factory = sqlite3.Row
    return conn

# Cria tabela de clientes
conn = get_db_connection()
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    card_id TEXT UNIQUE NOT NULL,
    ultimo_pagamento DATE,
    creditos INTEGER NOT NULL,
    data_expiracao DATE,
    celular TEXT NOT NULL
)''')
conn.commit()
conn.close()

def validar_id(card_id):
    if not card_id.startswith('CARD'):
        return False, "Erro: O ID do cartão deve começar com 'CARD'."
    conn = get_db_connection()
    result = conn.execute("SELECT card_id FROM clientes WHERE card_id = ?", (card_id,)).fetchone()
    conn.close()
    if result:
        return False, "Erro: Este ID já está cadastrado."
    return True, ""

def buscar_nome_cliente(card_id):
    conn = get_db_connection()
    result = conn.execute("SELECT nome, celular FROM clientes WHERE card_id = ?", (card_id,)).fetchone()
    conn.close()
    if result:
        return True, result['nome'], result['celular']
    return False, "Cliente não encontrado", ""

def listar_clientes():
    conn = get_db_connection()
    result = conn.execute("SELECT card_id, nome FROM clientes").fetchall()
    conn.close()
    return [(row['card_id'], row['nome']) for row in result]

def excluir_cliente(card_id):
    conn = get_db_connection()
    result = conn.execute("SELECT nome FROM clientes WHERE card_id = ?", (card_id,)).fetchone()
    if result:
        conn.execute("DELETE FROM clientes WHERE card_id = ?", (card_id,))
        conn.commit()
        conn.close()
        return "Cliente excluído com sucesso!"
    conn.close()
    return "Cliente não encontrado."

def atualizar_nome_cliente(card_id, novo_nome, novo_celular):
    conn = get_db_connection()
    result = conn.execute("SELECT nome FROM clientes WHERE card_id = ?", (card_id,)).fetchone()
    if result:
        conn.execute("UPDATE clientes SET nome = ?, celular = ? WHERE card_id = ?", (novo_nome, novo_celular, card_id))
        conn.commit()
        conn.close()
        return "Cliente atualizado com sucesso!"
    conn.close()
    return "Cliente não encontrado."

def cadastrar_cliente(nome, card_id, celular):
    hoje = datetime.now().date()
    expiracao = hoje + timedelta(days=30)
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO clientes (nome, card_id, ultimo_pagamento, creditos, data_expiracao, celular) VALUES (?, ?, ?, ?, ?, ?)",
                     (nome, card_id, str(hoje), 10, str(expiracao), celular))
        conn.commit()
        conn.close()
        return "Cliente cadastrado com sucesso! Créditos iniciais: 10"
    except sqlite3.IntegrityError:
        conn.close()
        return "Erro: ID do cartão já existe."

def recarregar_creditos(card_id):
    hoje = datetime.now().date()
    expiracao = hoje + timedelta(days=30)
    conn = get_db_connection()
    result = conn.execute("SELECT nome FROM clientes WHERE card_id = ?", (card_id,)).fetchone()
    if result:
        conn.execute("UPDATE clientes SET creditos = 10, ultimo_pagamento = ?, data_expiracao = ? WHERE card_id = ?",
                     (str(hoje), str(expiracao), card_id))
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
    result = conn.execute("SELECT creditos, data_expiracao FROM clientes WHERE card_id = ?", (card_id,)).fetchone()
    if result:
        creditos = result['creditos']
        expiracao = datetime.strptime(result['data_expiracao'], '%Y-%m-%d').date()
        if hoje > expiracao:
            conn.close()
            return "Créditos expirados. Necessário recarregar."
        novo_creditos = creditos + quantidade
        conn.execute("UPDATE clientes SET creditos = ? WHERE card_id = ?", (novo_creditos, card_id))
        conn.commit()
        conn.close()
        return f"{quantidade} crédito(s) adicionado(s) manualmente. Créditos totais: {novo_creditos}"
    conn.close()
    return "Cliente não encontrado."

def deduzir_credito(card_id, quantidade):
    try:
        quantidade = int(quantidade)
        if quantidade <= 0:
            return "Erro: A quantidade deve ser maior que zero."
    except ValueError:
        return "Erro: Insira um número válido."
    
    hoje = datetime.now().date()
    conn = get_db_connection()
    result = conn.execute("SELECT creditos, data_expiracao FROM clientes WHERE card_id = ?", (card_id,)).fetchone()
    if result:
        creditos = result['creditos']
        expiracao = datetime.strptime(result['data_expiracao'], '%Y-%m-%d').date()
        if hoje > expiracao:
            conn.close()
            return "Créditos expirados. Necessário recarregar."
        if creditos >= quantidade:
            novo_creditos = creditos - quantidade
            conn.execute("UPDATE clientes SET creditos = ? WHERE card_id = ?", (novo_creditos, card_id))
            conn.commit()
            conn.close()
            return f"{quantidade} crédito(s) deduzido(s). Créditos restantes: {novo_creditos}"
        conn.close()
        return f"Erro: Créditos insuficientes. Disponível: {creditos}, solicitado: {quantidade}."
    conn.close()
    return "Cliente não encontrado."

def buscar_info_cliente(card_id):
    hoje = datetime.now().date()
    conn = get_db_connection()
    result = conn.execute("SELECT nome, creditos, data_expiracao FROM clientes WHERE card_id = ?", (card_id,)).fetchone()
    conn.close()
    if result:
        nome = result['nome']
        creditos = result['creditos']
        expiracao_str = result['data_expiracao']
        expiracao = datetime.strptime(expiracao_str, '%Y-%m-%d').date()
        if hoje > expiracao:
            dias_restantes = "Expirado"
        else:
            dias_restantes = (expiracao - hoje).days
        expiracao_formatada = expiracao.strftime('%d/%m/%Y')
        return nome, creditos, dias_restantes, expiracao_formatada
    return "Cliente não encontrado", None, None, None

@app.route('/', methods=['GET', 'POST'])
def index():
    mensagem = ""
    card_id_display = ""
    nome = ""
    creditos = ""
    dias = ""
    expiracao = ""
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
            quantidade = request.form.get('quantidade')
            if senha == "03842789":
                mensagem = adicionar_credito_manual(card_id, quantidade)
                nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
                card_id_display = card_id
            else:
                mensagem = "Senha incorreta!"
        elif action == 'deduzir':
            quantidade = request.form.get('quantidade')
            mensagem = deduzir_credito(card_id, quantidade)
            nome, creditos, dias, expiracao = buscar_info_cliente(card_id)
            card_id_display = card_id
    return render_template('index.html', mensagem=mensagem, card_id_display=card_id_display, nome=nome, creditos=creditos, dias=dias, expiracao=expiracao)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    mensagem = ""
    card_id = "CARD"
    nome_atual = ""
    celular_atual = ""
    mostrar_formulario_edicao = False
    mostrar_formulario_exclusao = False
    confirmar_exclusao = False
    confirmar_edicao = False
    clientes = []
    card_id_excluir = ""
    card_id_editar = ""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'mostrar_edicao':
            senha = request.form.get('senha')
            if senha == "03842789":
                mostrar_formulario_edicao = True
            else:
                mensagem = "Senha incorreta!"
        elif action == 'buscar_cliente':
            card_id_editar = request.form.get('card_id_editar')
            valido, nome_atual, celular_atual = buscar_nome_cliente(card_id_editar)
            if valido:
                mostrar_formulario_edicao = True
            else:
                mensagem = "Cliente não encontrado!"
        elif action == 'editar':
            card_id_editar = request.form.get('card_id')
            novo_nome = request.form.get('novo_nome')
            novo_celular = request.form.get('novo_celular')
            if not novo_nome or not novo_celular:
                mensagem = "Erro: Preencha nome e celular!"
            else:
                confirmar_edicao = True
        elif action == 'confirmar_edicao':
            card_id_editar = request.form.get('card_id')
            novo_nome = request.form.get('novo_nome')
            novo_celular = request.form.get('novo_celular')
            mensagem = atualizar_nome_cliente(card_id_editar, novo_nome, novo_celular)
            if "sucesso" in mensagem.lower():
                return redirect(url_for('index'))
        elif action == 'mostrar_exclusao':
            senha = request.form.get('senha')
            if senha == "03842789":
                clientes = listar_clientes()
                mostrar_formulario_exclusao = True
            else:
                mensagem = "Senha incorreta!"
        elif action == 'selecionar_exclusao':
            card_id_excluir = request.form.get('card_id_excluir')
            valido, nome_atual, _ = buscar_nome_cliente(card_id_excluir)
            if valido:
                confirmar_exclusao = True
            else:
                mensagem = "Cliente não encontrado!"
        elif action == 'confirmar_exclusao':
            card_id_excluir = request.form.get('card_id')
            mensagem = excluir_cliente(card_id_excluir)
            if "sucesso" in mensagem.lower():
                return redirect(url_for('index'))
        else:  # Cadastro de novo cliente
            nome = request.form.get('nome')
            card_id = request.form.get('card_id')
            celular = request.form.get('celular')
            if not nome or not celular:
                mensagem = "Erro: Preencha nome e celular!"
            else:
                valido, erro = validar_id(card_id)
                if not valido:
                    mensagem = erro
                else:
                    mensagem = cadastrar_cliente(nome, card_id, celular)
                    if "sucesso" in mensagem.lower():
                        return redirect(url_for('index'))
    return render_template('cadastro.html', mensagem=mensagem, card_id=card_id, nome_atual=nome_atual, celular_atual=celular_atual, mostrar_formulario_edicao=mostrar_formulario_edicao, mostrar_formulario_exclusao=mostrar_formulario_exclusao, confirmar_exclusao=confirmar_exclusao, confirmar_edicao=confirmar_edicao, clientes=clientes, card_id_excluir=card_id_excluir, card_id_editar=card_id_editar)

@app.route('/cliente', methods=['GET', 'POST'])
def cliente():
    mensagem = None
    cliente = None
    if request.method == 'POST':
        celular = request.form['celular'].strip()
        if not celular:
            mensagem = "Celular não pode estar vazio."
        else:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM clientes WHERE celular = ?", (celular,))
            cliente = c.fetchone()
            conn.close()
            if not cliente:
                mensagem = "Nenhum cliente encontrado com esse número de celular."
    return render_template('cliente.html', mensagem=mensagem, cliente=cliente)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)