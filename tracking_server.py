# tracking_server.py - Servidor de rastreamento de cliques com interface bonita
from flask import Flask, redirect, request, jsonify, render_template_string
import sqlite3
import datetime
import random
import string
import logging
import json

app = Flask(__name__)

# Configuração do banco de dados de tracking
DB_PATH = 'cliques_links.db'
URL_BASE = 'http://localhost:5000'

# ====== TEMPLATE HTML BONITO ======
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Promos do Negão - Tracking</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            padding: 40px 0;
            border-bottom: 2px solid rgba(255,255,255,0.1);
            margin-bottom: 40px;
        }
        .header h1 {
            font-size: 3em;
            background: linear-gradient(45deg, #f7971e, #ffd200);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: none;
        }
        .header p {
            color: #8899bb;
            margin-top: 10px;
            font-size: 1.1em;
        }
        .header .status {
            display: inline-block;
            background: #00c853;
            color: #fff;
            padding: 5px 20px;
            border-radius: 20px;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255,255,255,0.08);
            transition: all 0.3s ease;
        }
        .card:hover {
            transform: translateY(-5px);
            background: rgba(255,255,255,0.08);
            border-color: rgba(255,255,255,0.15);
        }
        .card .icon {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .card .label {
            color: #8899bb;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .card .value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 8px 0;
        }
        .card .value.gold {
            color: #ffd700;
        }
        .card .value.green {
            color: #00e676;
        }
        .card .value.blue {
            color: #40c4ff;
        }
        .card .value.pink {
            color: #ff6b9d;
        }
        .card .sub {
            color: #667799;
            font-size: 0.9em;
        }
        .table-container {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255,255,255,0.08);
            margin-top: 20px;
            overflow-x: auto;
        }
        .table-container h2 {
            margin-bottom: 20px;
            color: #ffd700;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        th {
            color: #8899bb;
            text-transform: uppercase;
            font-size: 0.8em;
            letter-spacing: 1px;
        }
        td {
            color: #dde4f0;
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
        }
        .badge.shopee { background: #ee4d2d; color: #fff; }
        .badge.mercadolivre { background: #ffe600; color: #333; }
        .badge.amazon { background: #ff9900; color: #fff; }
        .badge.kabum { background: #e20014; color: #fff; }
        .badge.magalu { background: #ff0055; color: #fff; }
        .badge.geral { background: #667799; color: #fff; }
        .progress-bar {
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 6px;
        }
        .progress-bar .fill {
            height: 100%;
            background: linear-gradient(90deg, #f7971e, #ffd200);
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #667799;
            border-top: 1px solid rgba(255,255,255,0.05);
        }
        .footer a {
            color: #ffd700;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        @media (max-width: 600px) {
            .header h1 { font-size: 2em; }
            .card .value { font-size: 1.8em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Promos do Negão</h1>
            <p>Sistema de Rastreamento de Cliques</p>
            <span class="status">🟢 Online</span>
        </div>

        <div class="grid">
            <div class="card">
                <div class="icon">🖱️</div>
                <div class="label">Total de Cliques</div>
                <div class="value gold">{{ total_cliques }}</div>
                <div class="sub">Última atualização: {{ agora }}</div>
            </div>
            <div class="card">
                <div class="icon">📊</div>
                <div class="label">Cliques Hoje</div>
                <div class="value green">{{ cliques_hoje }}</div>
                <div class="sub">Média de descontos: {{ media_desconto }}%</div>
            </div>
            <div class="card">
                <div class="icon">🏆</div>
                <div class="label">Produto Mais Clicado</div>
                <div class="value blue">{{ produto_top or 'Nenhum ainda' }}</div>
                <div class="sub">{{ produto_cliques or '' }}</div>
            </div>
            <div class="card">
                <div class="icon">⏰</div>
                <div class="label">Horário de Pico</div>
                <div class="value pink">{{ hora_pico or '--:--' }}</div>
                <div class="sub">{{ hora_pico_qtd or '' }}</div>
            </div>
        </div>

        <div class="table-container">
            <h2>📈 Performance por Plataforma</h2>
            <table>
                <thead>
                    <tr>
                        <th>Plataforma</th>
                        <th>Cliques</th>
                        <th>Share</th>
                        <th>Progresso</th>
                    </tr>
                </thead>
                <tbody>
                    {% for plat in cliques_plataforma %}
                    <tr>
                        <td><span class="badge {{ plat[0].lower() }}">{{ plat[0].upper() }}</span></td>
                        <td>{{ plat[1] }}</td>
                        <td>{{ "%.1f"|format(plat[1] / total_cliques * 100 if total_cliques > 0 else 0) }}%</td>
                        <td style="width: 40%;">
                            <div class="progress-bar">
                                <div class="fill" style="width: {{ plat[1] / total_cliques * 100 if total_cliques > 0 else 0 }}%;"></div>
                            </div>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" style="text-align: center; color: #667799;">Nenhum clique registrado ainda</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="table-container">
            <h2>🕐 Top 5 Horários com Mais Cliques</h2>
            <table>
                <thead>
                    <tr>
                        <th>Horário</th>
                        <th>Cliques</th>
                        <th>Progresso</th>
                    </tr>
                </thead>
                <tbody>
                    {% for hora in cliques_por_hora %}
                    <tr>
                        <td><b>{{ hora[0] }}:00</b></td>
                        <td>{{ hora[1] }}</td>
                        <td style="width: 60%;">
                            <div class="progress-bar">
                                <div class="fill" style="width: {{ hora[1] / cliques_por_hora[0][1] * 100 if cliques_por_hora else 0 }}%;"></div>
                            </div>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="3" style="text-align: center; color: #667799;">Nenhum dado de horário disponível</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>💡 <a href="/api/estatisticas">API JSON</a> • <a href="/">Recarregar</a></p>
            <p style="margin-top: 10px; font-size: 0.8em;">Promos do Negão © 2026 • Sistema de Tracking</p>
        </div>
    </div>
</body>
</html>
'''

def init_tracking_db():
    """Inicializa o banco de dados de tracking"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliques_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE,
            link_original TEXT,
            titulo_produto TEXT,
            plataforma TEXT,
            categoria TEXT,
            preco_desconto REAL,
            preco_original REAL,
            desconto_percentual INTEGER,
            data_criacao TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliques_registrados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT,
            ip_cliente TEXT,
            user_agent TEXT,
            referer TEXT,
            timestamp_clique TEXT,
            hora_dia INTEGER,
            dia_semana INTEGER,
            data_clique TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliques_diarios (
            data_clique TEXT PRIMARY KEY,
            total_cliques INTEGER DEFAULT 0,
            cliques_shopee INTEGER DEFAULT 0,
            cliques_mercadolivre INTEGER DEFAULT 0,
            cliques_amazon INTEGER DEFAULT 0,
            cliques_aliexpress INTEGER DEFAULT 0,
            cliques_kabum INTEGER DEFAULT 0,
            cliques_magalu INTEGER DEFAULT 0,
            cliques_geral INTEGER DEFAULT 0,
            soma_descontos REAL DEFAULT 0,
            media_desconto REAL DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Banco de dados de tracking inicializado")

def gerar_short_code():
    """Gera um código curto único"""
    caracteres = string.ascii_lowercase + string.digits
    return ''.join(random.choices(caracteres, k=6))

@app.route('/')
def home():
    """Página inicial com dashboard bonito"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    # Total de cliques
    cursor.execute('SELECT COUNT(*) FROM cliques_registrados')
    total_cliques = cursor.fetchone()[0] or 0
    
    # Cliques hoje
    hoje = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute('SELECT total_cliques, media_desconto FROM cliques_diarios WHERE data_clique = ?', (hoje,))
    row_hoje = cursor.fetchone()
    cliques_hoje = row_hoje[0] if row_hoje else 0
    media_desconto = round(row_hoje[1] or 0, 1) if row_hoje else 0
    
    # Cliques por plataforma
    cursor.execute('''
        SELECT plataforma, COUNT(*) as total
        FROM cliques_tracking t
        JOIN cliques_registrados r ON t.short_code = r.short_code
        GROUP BY plataforma
        ORDER BY total DESC
    ''')
    cliques_plataforma = cursor.fetchall()
    
    # Produto mais clicado
    cursor.execute('''
        SELECT t.titulo_produto, COUNT(*) as total
        FROM cliques_tracking t
        JOIN cliques_registrados r ON t.short_code = r.short_code
        GROUP BY t.titulo_produto
        ORDER BY total DESC
        LIMIT 1
    ''')
    produto_top = cursor.fetchone()
    
    # Horário de pico
    cursor.execute('''
        SELECT hora_dia, COUNT(*) as total
        FROM cliques_registrados
        GROUP BY hora_dia
        ORDER BY total DESC
        LIMIT 1
    ''')
    hora_pico = cursor.fetchone()
    
    # Top 5 horários
    cursor.execute('''
        SELECT hora_dia, COUNT(*) as total
        FROM cliques_registrados
        GROUP BY hora_dia
        ORDER BY total DESC
        LIMIT 5
    ''')
    cliques_por_hora = cursor.fetchall()
    
    conn.close()
    
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    
    return render_template_string(
        HTML_TEMPLATE,
        total_cliques=total_cliques,
        cliques_hoje=cliques_hoje,
        media_desconto=media_desconto,
        cliques_plataforma=cliques_plataforma,
        produto_top=produto_top[0][:35] + "..." if produto_top and len(produto_top[0]) > 35 else (produto_top[0] if produto_top else None),
        produto_cliques=f"{produto_top[1]} cliques" if produto_top else "",
        hora_pico=f"{hora_pico[0]:02d}:00" if hora_pico else None,
        hora_pico_qtd=f"{hora_pico[1]} cliques" if hora_pico else "",
        cliques_por_hora=cliques_por_hora,
        agora=agora
    )

@app.route('/<short_code>')
def redirecionar(short_code):
    """Redireciona o clique registrando no banco"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute('SELECT link_original, titulo_produto, plataforma, categoria, preco_desconto, preco_original, desconto_percentual FROM cliques_tracking WHERE short_code = ?', (short_code,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return "Link não encontrado", 404
    
    link_original, titulo, plataforma, categoria, preco_desc, preco_orig, desconto = row
    
    agora = datetime.datetime.now()
    data_clique = agora.strftime("%Y-%m-%d")
    hora_dia = agora.hour
    dia_semana = agora.weekday()
    timestamp = agora.strftime("%Y-%m-%d %H:%M:%S")
    
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    referer = request.headers.get('Referer', '')
    
    cursor.execute('''
        INSERT INTO cliques_registrados 
        (short_code, ip_cliente, user_agent, referer, timestamp_clique, hora_dia, dia_semana, data_clique)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (short_code, ip, user_agent, referer, timestamp, hora_dia, dia_semana, data_clique))
    
    cursor.execute('SELECT total_cliques FROM cliques_diarios WHERE data_clique = ?', (data_clique,))
    dia_row = cursor.fetchone()
    
    if dia_row:
        campo_plataforma = f'cliques_{plataforma.lower()}'
        cursor.execute(f'''
            UPDATE cliques_diarios 
            SET total_cliques = total_cliques + 1,
                {campo_plataforma} = {campo_plataforma} + 1,
                soma_descontos = soma_descontos + ?,
                media_desconto = (soma_descontos + ?) / (total_cliques + 1)
            WHERE data_clique = ?
        ''', (desconto, desconto, data_clique))
    else:
        cursor.execute('''
            INSERT INTO cliques_diarios 
            (data_clique, total_cliques, cliques_shopee, cliques_mercadolivre, cliques_amazon, 
             cliques_aliexpress, cliques_kabum, cliques_magalu, cliques_geral, soma_descontos, media_desconto)
            VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data_clique,
            1 if plataforma.lower() == 'shopee' else 0,
            1 if plataforma.lower() == 'mercadolivre' else 0,
            1 if plataforma.lower() == 'amazon' else 0,
            1 if plataforma.lower() == 'aliexpress' else 0,
            1 if plataforma.lower() == 'kabum' else 0,
            1 if plataforma.lower() == 'magalu' else 0,
            1 if plataforma.lower() == 'geral' else 0,
            desconto,
            desconto
        ))
    
    conn.commit()
    conn.close()
    
    return redirect(link_original, code=302)

@app.route('/api/criar_link', methods=['POST'])
def criar_link_rastreado():
    """Cria um link encurtado rastreável"""
    dados = request.json
    
    if not dados or not dados.get('link_original'):
        return jsonify({'erro': 'Link original é obrigatório'}), 400
    
    link_original = dados.get('link_original')
    titulo = dados.get('titulo', 'Produto em Oferta')
    plataforma = dados.get('plataforma', 'geral')
    categoria = dados.get('categoria', 'geral')
    preco_desc = dados.get('preco_desconto', 0)
    preco_orig = dados.get('preco_original', 0)
    
    desconto = 0
    if preco_orig > preco_desc and preco_orig > 0:
        desconto = round(((preco_orig - preco_desc) / preco_orig) * 100)
    
    short_code = gerar_short_code()
    
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute('''
        INSERT INTO cliques_tracking 
        (short_code, link_original, titulo_produto, plataforma, categoria, 
         preco_desconto, preco_original, desconto_percentual, data_criacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (short_code, link_original, titulo, plataforma, categoria, 
          preco_desc, preco_orig, desconto, agora))
    
    conn.commit()
    conn.close()
    
    link_encurtado = f"{URL_BASE}/{short_code}"
    
    return jsonify({
        'short_code': short_code,
        'link_encurtado': link_encurtado,
        'link_original': link_original
    })

@app.route('/api/estatisticas')
def estatisticas():
    """Retorna estatísticas de cliques em JSON"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM cliques_registrados')
    total_cliques = cursor.fetchone()[0] or 0
    
    cursor.execute('''
        SELECT plataforma, COUNT(*) as total
        FROM cliques_tracking t
        JOIN cliques_registrados r ON t.short_code = r.short_code
        GROUP BY plataforma
        ORDER BY total DESC
    ''')
    cliques_plataforma = cursor.fetchall()
    
    cursor.execute('''
        SELECT t.titulo_produto, COUNT(*) as total
        FROM cliques_tracking t
        JOIN cliques_registrados r ON t.short_code = r.short_code
        GROUP BY t.titulo_produto
        ORDER BY total DESC
        LIMIT 1
    ''')
    produto_top = cursor.fetchone()
    
    cursor.execute('''
        SELECT hora_dia, COUNT(*) as total
        FROM cliques_registrados
        GROUP BY hora_dia
        ORDER BY total DESC
        LIMIT 5
    ''')
    cliques_hora_top = cursor.fetchall()
    
    cursor.execute('''
        SELECT AVG(desconto_percentual)
        FROM cliques_tracking t
        JOIN cliques_registrados r ON t.short_code = r.short_code
    ''')
    media_desconto = cursor.fetchone()[0] or 0
    
    hoje = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute('SELECT total_cliques FROM cliques_diarios WHERE data_clique = ?', (hoje,))
    cliques_hoje = cursor.fetchone()
    cliques_hoje = cliques_hoje[0] if cliques_hoje else 0
    
    conn.close()
    
    return jsonify({
        'total_cliques': total_cliques,
        'cliques_hoje': cliques_hoje,
        'cliques_plataforma': cliques_plataforma,
        'produto_mais_clicado': produto_top,
        'cliques_por_hora': cliques_hora_top,
        'media_desconto': round(media_desconto, 1)
    })

if __name__ == '__main__':
    init_tracking_db()
    print("="*60)
    print("🔄 SERVIDOR DE TRACKING INICIADO!")
    print(f"📡 URL BASE: {URL_BASE}")
    print("📊 Dashboard: {}/".format(URL_BASE))
    print("📊 API JSON: {}/api/estatisticas".format(URL_BASE))
    print("="*60)
    print("⚠️  ATENÇÃO: Para TESTE LOCAL, use http://localhost:5000")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)