import logging
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, ConversationHandler, CommandHandler
import json
import html
import traceback
import random
import os
import sqlite3
import datetime
from collections import defaultdict, Counter
from io import BytesIO
from PIL import Image
import threading
import time

# Configuração do logging detalhado
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = '8879459587:AAF0r0u886aeUtQGn8VNcmMJLyz6dk4Eg1c'
GRUPO_RASCUNHO_ID = -1003940381648
GRUPO_PROMOS_ID = -1003773466313

LOGO_POSSIBLE_FILENAMES = ['logo.jpeg', 'logo.jpg', 'logo.png', 'LOGO.jpeg', 'LOGO.jpg', 'LOGO.png']

SHOPEE_APP_ID = '18394560427'
SHOPEE_SECRET = 'MVWZVQAHOYQWQUIELG5YF455I23P4LUK'

# Links oficiais das vitrines e perfis sociais para garimpos encaminhados
LINK_VITRINE_SHOPEE = 'https://collshp.com/promosdonegao'
LINK_VITRINE_AMAZON = 'https://www.amazon.com.br?tag=promosdoneg00-20'
LINK_PERFIL_ML = 'https://www.mercadolivre.com.br/social/pp20251117152052'

# ====== CONFIGURAÇÃO DO SERVIDOR DE TRACKING ======
TRACKING_SERVER = os.environ.get('TRACKING_SERVER', 'https://promos-tracking.onrender.com')
DOMINIO_TRACKING = os.environ.get('DOMINIO_TRACKING', 'https://promos-tracking.onrender.com')

# ====== CONFIGURAÇÃO DE AFILIADOS ======
PARAMETROS_AFILIADOS = {
    'amazon': '?tag=promosdoneg00-20',
    'shopee': '?aff_id=18394560427',
    'mercadolivre': '?aff_id=pp20251117152052'
}

# ====== INTERVALO ENTRE POSTAGENS (MINUTOS) ======
INTERVALO_POSTAGEM_MINUTOS = 8

def adicionar_parametro_afiliado(link, plataforma):
    """Adiciona o parâmetro de afiliado ao link baseado na plataforma"""
    if not link:
        return link
    
    if plataforma not in PARAMETROS_AFILIADOS:
        return link
    
    if '?' in link:
        if plataforma == 'amazon' and 'tag=' in link:
            return link
        if plataforma == 'shopee' and 'aff_id=' in link:
            return link
        if plataforma == 'mercadolivre' and 'aff_id=' in link:
            return link
        return link + '&' + PARAMETROS_AFILIADOS[plataforma][1:]
    else:
        return link + PARAMETROS_AFILIADOS[plataforma]

# ====== BANCO DE DADOS DE MÉTRICAS E FILA ======
DB_METRICS_PATH = 'metricas_avancadas.db'
DB_PROMOS_PATH = 'promos_fila.db'

# Estados da conversa (ConversationHandler)
AGUARDANDO_PRECO = 1
CUPOM_TEXTO = 2
CUPOM_LINK = 3
CUPOM_IMAGEM = 4
EDITAR_ITEM_PASSO = 5
PERSONALIZAR_PRECOS_PASSO = 6

BOT_PAUSADO = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
}

# ====== FUNÇÕES PARA SALVAR/CARREGAR ÚLTIMO TIMESTAMP ======
def salvar_ultimo_timestamp(timestamp):
    """Salva o último timestamp de envio no banco"""
    try:
        conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS controle_bot (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )
        ''')
        cursor.execute('INSERT OR REPLACE INTO controle_bot (chave, valor) VALUES (?, ?)',
                       ('ultimo_envio', timestamp.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao salvar timestamp: {e}")

def carregar_ultimo_timestamp():
    """Carrega o último timestamp de envio do banco"""
    try:
        conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS controle_bot (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )
        ''')
        cursor.execute('SELECT valor FROM controle_bot WHERE chave = ?', ('ultimo_envio',))
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            try:
                return datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            except:
                return datetime.datetime.min
        return datetime.datetime.min
    except Exception as e:
        logger.error(f"Erro ao carregar timestamp: {e}")
        return datetime.datetime.min

# Carrega o timestamp ao iniciar
ULTIMO_ENVIO_TIMESTAMP = carregar_ultimo_timestamp()
logger.info(f"Último envio registrado: {ULTIMO_ENVIO_TIMESTAMP}")

# --- BANCO DE DADOS ESCALÁVEL E CONTROLE DE PERSISTÊNCIA ---

def inicializar_banco():
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute('PRAGMA journal_mode=WAL;')
    cursor.execute('PRAGMA synchronous=NORMAL;')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fila_postagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dados_json TEXT,
            link TEXT,
            texto_adicional TEXT,
            data_agendamento TEXT,
            origem TEXT DEFAULT 'manual',
            file_id_foto TEXT,
            status TEXT DEFAULT 'pendente'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_limpo TEXT,
            data_envio TEXT,
            short_code TEXT,
            categoria TEXT,
            plataforma TEXT,
            titulo TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contadores_plataforma (
            plataforma TEXT PRIMARY KEY,
            contador INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            detalhes TEXT,
            data_hora TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS frases_usadas_hoje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT,
            texto_frase TEXT,
            data_uso TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_interacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plataforma TEXT,
            hora_dia INTEGER,
            data_envio TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metricas_envio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_envio TEXT,
            plataforma TEXT,
            categoria TEXT,
            titulo_produto TEXT,
            preco_desconto REAL,
            preco_original REAL,
            desconto_percentual INTEGER,
            link_original TEXT,
            short_code TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS controle_bot (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    ''')
    conn.commit()
    
    cursor.execute("PRAGMA table_info(fila_postagens)")
    colunas = [col[1] for col in cursor.fetchall()]
    
    if 'origem' not in colunas:
        logger.info("Adicionando coluna 'origem' na tabela fila_postagens...")
        cursor.execute("ALTER TABLE fila_postagens ADD COLUMN origem TEXT DEFAULT 'manual'")
        conn.commit()
        
    if 'file_id_foto' not in colunas:
        logger.info("Adicionando coluna 'file_id_foto' na tabela fila_postagens...")
        cursor.execute("ALTER TABLE fila_postagens ADD COLUMN file_id_foto TEXT")
        conn.commit()
    
    if 'status' not in colunas:
        logger.info("Adicionando coluna 'status' na tabela fila_postagens...")
        cursor.execute("ALTER TABLE fila_postagens ADD COLUMN status TEXT DEFAULT 'pendente'")
        conn.commit()
        
    conn.close()
    registrar_log_sistema("inicializar_banco", "Banco de dados inicializado com sucesso.")
    inicializar_metricas_avancadas()

def inicializar_metricas_avancadas():
    conn = sqlite3.connect(DB_METRICS_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliques_detalhados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT,
            data_clique TEXT,
            hora_dia INTEGER,
            dia_semana INTEGER,
            plataforma TEXT,
            categoria TEXT,
            titulo_produto TEXT,
            preco_desconto REAL,
            preco_original REAL,
            desconto_percentual INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metricas_diarias (
            data_referencia TEXT PRIMARY KEY,
            total_cliques INTEGER DEFAULT 0,
            cliques_shopee INTEGER DEFAULT 0,
            cliques_mercadolivre INTEGER DEFAULT 0,
            cliques_amazon INTEGER DEFAULT 0,
            cliques_aliexpress INTEGER DEFAULT 0,
            cliques_kabum INTEGER DEFAULT 0,
            cliques_magalu INTEGER DEFAULT 0,
            cliques_outros INTEGER DEFAULT 0,
            postagens_dia INTEGER DEFAULT 0,
            taxa_clique_por_postagem REAL DEFAULT 0,
            soma_descontos REAL DEFAULT 0,
            media_desconto REAL DEFAULT 0,
            melhor_horario INTEGER DEFAULT 0,
            pior_horario INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metricas_categoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT,
            data_referencia TEXT,
            total_cliques INTEGER DEFAULT 0,
            total_postagens INTEGER DEFAULT 0,
            taxa_clique REAL DEFAULT 0,
            media_desconto REAL DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS relatorios_ia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_geracao TEXT,
            tipo_insight TEXT,
            mensagem TEXT,
            nivel_prioridade INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Banco de métricas avançadas inicializado")

def registrar_log_sistema(tipo, detalhes):
    try:
        conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
        cursor = conn.cursor()
        data_hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO log_operacoes (tipo, detalhes, data_hora) VALUES (?, ?, ?)", (tipo, detalhes, data_hora))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao gravar log no banco: {e}")

def registrar_evento_postagem(plataforma):
    try:
        conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
        cursor = conn.cursor()
        agora = datetime.datetime.now()
        hora_dia = agora.hour
        data_envio = agora.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO historico_interacoes (plataforma, hora_dia, data_envio) VALUES (?, ?, ?)",
            (plataforma, hora_dia, data_envio)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao registrar evento de interacao: {e}")

def ajustar_fila_ao_iniciar():
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    agora = datetime.datetime.now()
    cursor.execute("SELECT id, data_agendamento FROM fila_postagens WHERE status = 'pendente' ORDER BY id ASC")
    itens = cursor.fetchall()
    
    if not itens:
        conn.close()
        return

    proximo_horario = agora
    for item_id, _ in itens:
        proximo_horario += datetime.timedelta(minutes=INTERVALO_POSTAGEM_MINUTOS)
        novo_horario_str = proximo_horario.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE fila_postagens SET data_agendamento = ? WHERE id = ?", (novo_horario_str, item_id))

    conn.commit()
    conn.close()
    registrar_log_sistema("ajustar_fila", f"Horários de {len(itens)} itens reajustados na inicialização.")

def garantir_janela_funcionamento(dt):
    hora_minuto = dt.time()
    inicio = datetime.time(7, 15)
    fim = datetime.time(23, 30)

    if hora_minuto < inicio:
        dt = dt.replace(hour=7, minute=15, second=0, microsecond=0)
    elif hora_minuto > fim:
        dt += datetime.timedelta(days=1)
        dt = dt.replace(hour=7, minute=15, second=0, microsecond=0)
    return dt

def identificar_plataforma(link):
    if not link:
        return 'geral'
    link_lower = link.lower()
    if 'shopee' in link_lower or 'shp.ee' in link_lower or 'collshp.com' in link_lower:
        return 'shopee'
    elif 'mercadolivre' in link_lower or 'meli.la' in link_lower or 'mercadolibre' in link_lower:
        return 'mercadolivre'
    elif 'amazon' in link_lower or 'amzn.to' in link_lower or 'amzn.br' in link_lower:
        return 'amazon'
    elif 'aliexpress' in link_lower or 'ali.ski' in link_lower:
        return 'aliexpress'
    elif 'kabum' in link_lower:
        return 'kabum'
    elif 'magalu' in link_lower or 'magazineluiza' in link_lower or 'mglu.envio' in link_lower:
        return 'magalu'
    elif 'casasbahia' in link_lower or 'ponto.com' in link_lower:
        return 'casasbahia'
    elif 'ponto' in link_lower:
        return 'ponto'
    elif 'extra' in link_lower:
        return 'extra'
    elif 'fastshop' in link_lower:
        return 'fastshop'
    else:
        return 'geral'

def incrementar_e_verificar_contador_plataforma(plataforma):
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT contador FROM contadores_plataforma WHERE plataforma = ?', (plataforma,))
    row = cursor.fetchone()
    
    if row is None:
        atual = 1
        cursor.execute('INSERT INTO contadores_plataforma (plataforma, contador) VALUES (?, ?)', (plataforma, atual))
    else:
        atual = row[0] + 1
        if atual > 4:
            atual = 1
        cursor.execute('UPDATE contadores_plataforma SET contador = ? WHERE plataforma = ?', (atual, plataforma))
    
    conn.commit()
    conn.close()
    return atual

def identificar_categoria(titulo):
    titulo_lower = titulo.lower() if titulo else ''
    
    categorias = {
        'eletronicos': ['celular', 'smartphone', 'tablet', 'notebook', 'pc', 'gamer', 'mouse', 'teclado', 'monitor', 'fone', 'headset', 'tv', 'smart tv', 'processador', 'placa mãe', 'memória ram', 'ssd', 'hd'],
        'utilidades': ['panela', 'frigideira', 'copo', 'prato', 'talher', 'organizador', 'porta', 'cabide', 'vassoura', 'pano', 'detergente', 'sabão', 'amaciante'],
        'moda': ['camisa', 'camiseta', 'calça', 'vestido', 'sapato', 'tênis', 'bota', 'sandália', 'meia', 'cueca', 'sutiã', 'blusa', 'casaco', 'jaqueta'],
        'casa': ['sofá', 'cama', 'mesa', 'cadeira', 'armário', 'estante', 'rack', 'tapete', 'cortina', 'luminária', 'abajur', 'espelho'],
        'beleza': ['shampoo', 'condicionador', 'hidratante', 'creme', 'perfume', 'maquiagem', 'base', 'batom', 'esmalte', 'protetor solar'],
        'alimentos': ['arroz', 'feijão', 'macarrão', 'azeite', 'café', 'leite', 'pão', 'bolo', 'biscoito', 'refrigerante', 'suco', 'chocolate'],
        'brinquedos': ['boneca', 'boneco', 'carrinho', 'lego', 'jogo', 'quebra-cabeça', 'pelúcia', 'bola'],
        'livros': ['livro', 'revista', 'quadrinho', 'enciclopédia', 'dicionário'],
        'esporte': ['bola', 'chuteira', 'camisa', 'short', 'tenis', 'bicicleta', 'patins', 'skate']
    }
    
    for categoria, palavras in categorias.items():
        for palavra in palavras:
            if palavra in titulo_lower:
                return categoria
    
    return 'outros'

def limpar_url_para_verificacao(url):
    try:
        if not url:
            return ""
        url_limpa = re.sub(r'([?&])(si|spm|ref|utm_[a-z]+|click_id|aff_id|tag)=[^&]+', '', url)
        return url_limpa.strip()
    except Exception as e:
        logger.error(f"Erro ao limpar URL: {e}")
        return url

def verificar_duplicidade(link):
    link_limpo = limpar_url_para_verificacao(link)
    hoje = datetime.date.today().isoformat()
    
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM historico_links WHERE link_limpo = ? AND data_envio = ?', (link_limpo, hoje))
    count_hist = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM fila_postagens WHERE link LIKE ? AND status = ?', (f'%{link_limpo}%', 'pendente'))
    count_fila = cursor.fetchone()[0]
    
    conn.close()
    return (count_hist > 0 or count_fila > 0)

def registrar_envio_historico(link, short_code=None, categoria=None, titulo=None):
    link_limpo = limpar_url_para_verificacao(link)
    hoje = datetime.date.today().isoformat()
    plataforma = identificar_plataforma(link)
    
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO historico_links (link_limpo, data_envio, short_code, categoria, plataforma, titulo) VALUES (?, ?, ?, ?, ?, ?)',
                   (link_limpo, hoje, short_code, categoria, plataforma, titulo))
    conn.commit()
    conn.close()
    
    registrar_evento_postagem(plataforma)
    registrar_log_sistema("envio_historico", f"Link registrado no histórico: {link_limpo}")

def adicionar_fila(dados, link, texto_adicional, origem='manual', file_id_foto=None):
    duplicado = verificar_duplicidade(link)
    data_agendamento = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO fila_postagens (dados_json, link, texto_adicional, data_agendamento, origem, file_id_foto, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (json.dumps(dados), link, texto_adicional, data_agendamento, origem, file_id_foto, 'pendente')
    )
    conn.commit()
    novo_id = cursor.lastrowid
    
    cursor.execute('SELECT COUNT(*) FROM fila_postagens WHERE status = ?', ('pendente',))
    total_fila = cursor.fetchone()[0]
    conn.close()
    
    registrar_log_sistema("adicionar_fila", f"Novo item ID {novo_id} adicionado. Origem: {origem}")
    return total_fila, duplicado, novo_id

def proximo_da_fila():
    """Pega o próximo item da fila e remove da fila de pendentes"""
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, dados_json, link, texto_adicional, origem, file_id_foto 
        FROM fila_postagens 
        WHERE status = 'pendente' 
        ORDER BY id ASC 
        LIMIT 1
    ''')
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
    
    cursor.execute('DELETE FROM fila_postagens WHERE id = ?', (row[0],))
    conn.commit()
    conn.close()
    
    registrar_log_sistema("proximo_fila", f"Item ID {row[0]} retirado da fila para processamento.")
    
    return {
        'db_id': row[0],
        'dados': json.loads(row[1]),
        'link': row[2],
        'texto_adicional': row[3],
        'origem': row[4],
        'file_id_foto': row[5]
    }

def remover_da_fila(db_id):
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM fila_postagens WHERE id = ?', (db_id,))
    conn.commit()
    conn.close()
    registrar_log_sistema("remover_fila", f"Item ID {db_id} removido da fila.")

def limpar_toda_fila():
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM fila_postagens WHERE status = ?', ('pendente',))
    conn.commit()
    conn.close()
    registrar_log_sistema("limpar_fila", "Toda a fila de postagens foi zerada.")

def contar_fila_atual():
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM fila_postagens WHERE status = ?', ('pendente',))
    total = cursor.fetchone()[0]
    conn.close()
    return total

def obter_posicao_por_id(db_id):
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM fila_postagens WHERE status = ? ORDER BY id ASC', ('pendente',))
    rows = cursor.fetchall()
    conn.close()
    
    for index, row in enumerate(rows):
        if row[0] == db_id:
            return index + 1
    return len(rows)

def obter_item_por_posicao(posicao):
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT id, dados_json, link, texto_adicional, origem, file_id_foto FROM fila_postagens WHERE status = ? ORDER BY id ASC', ('pendente',))
    rows = cursor.fetchall()
    conn.close()
    
    if 1 <= posicao <= len(rows):
        row = rows[posicao - 1]
        return {'db_id': row[0], 'dados': json.loads(row[1]), 'link': row[2], 'texto_adicional': row[3], 'origem': row[4], 'file_id_foto': row[5]}
    return None

def atualizar_item_banco(db_id, dados, link, texto_adicional):
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE fila_postagens SET dados_json = ?, link = ?, texto_adicional = ? WHERE id = ?',
        (json.dumps(dados), link, texto_adicional, db_id)
    )
    conn.commit()
    conn.close()
    registrar_log_sistema("atualizar_item", f"Item ID {db_id} atualizado com novos dados.")

def contar_historico_hoje():
    hoje = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM historico_links WHERE data_envio = ?', (hoje,))
    total = cursor.fetchone()[0]
    conn.close()
    return total

def obter_logs_recentes(limite=10):
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT tipo, detalhes, data_hora FROM log_operacoes ORDER BY id DESC LIMIT ?', (limite,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def obter_ranking_plataformas_horario_atual():
    hora_atual = datetime.datetime.now().hour
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT plataforma, COUNT(*) as peso
        FROM historico_interacoes
        WHERE hora_dia = ?
        GROUP BY plataforma
        ORDER BY peso DESC
    ''', (hora_atual,))
    rows = cursor.fetchall()
    conn.close()
    
    ranking = [row[0] for row in rows]
    
    plataformas_padrao = ['shopee', 'mercadolivre', 'amazon', 'aliexpress', 'kabum', 'magalu', 'geral']
    for plat in plataformas_padrao:
        if plat not in ranking:
            ranking.append(plat)
            
    return ranking

def extrair_id_ou_chave_produto(row_item):
    try:
        dados = json.loads(row_item[1])
        titulo = dados.get('titulo', '').lower().strip()
        link = row_item[2].lower().strip()
        link_limpo = limpar_url_para_verificacao(link)
        return link_limpo if link_limpo else titulo
    except:
        return str(row_item[0])

def reordenar_fila_blocos_de_3():
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT id, dados_json, link, texto_adicional, origem, file_id_foto FROM fila_postagens WHERE status = ? ORDER BY id ASC', ('pendente',))
    rows = cursor.fetchall()
    
    if not rows:
        conn.close()
        return 0

    grupos = defaultdict(list)
    for row in rows:
        plat = identificar_plataforma(row[2])
        grupos[plat].append(row)

    ordem_prioridade = obter_ranking_plataformas_horario_atual()

    filas_ativas = []
    for plat in ordem_prioridade:
        if plat in grupos and len(grupos[plat]) > 0:
            filas_ativas.append((plat, grupos[plat]))
            
    for plat, lista in grupos.items():
        if plat not in ordem_prioridade and len(lista) > 0:
            filas_ativas.append((plat, lista))

    novos_itens_ordenados = []

    while filas_ativas:
        para_remover = []
        for i in range(len(filas_ativas)):
            plat, disponiveis = filas_ativas[i]
            bloco = []
            
            j = 0
            while j < len(disponiveis) and len(bloco) < 3:
                candidato = disponiveis[j]
                chave_candidato = extrair_id_ou_chave_produto(candidato)
                
                tem_repeticao_seguida = False
                if bloco:
                    chave_anterior = extrair_id_ou_chave_produto(bloco[-1])
                    if chave_candidato == chave_anterior:
                        tem_repeticao_seguida = True
                
                if not tem_repeticao_seguida:
                    bloco.append(disponiveis.pop(j))
                else:
                    j += 1
            
            while len(bloco) < 3 and disponiveis:
                bloco.append(disponiveis.pop(0))

            novos_itens_ordenados.extend(bloco)
            if not disponiveis:
                para_remover.append(i)
                
        for idx in reversed(para_remover):
            del filas_ativas[idx]

    cursor.execute('DELETE FROM fila_postagens WHERE status = ?', ('pendente',))
    
    for item in novos_itens_ordenados:
        _, dados_json, link, texto_adicional, origem, file_id_foto = item
        cursor.execute(
            'INSERT INTO fila_postagens (dados_json, link, texto_adicional, origem, file_id_foto, status) VALUES (?, ?, ?, ?, ?, ?)',
            (dados_json, link, texto_adicional, origem, file_id_foto, 'pendente')
        )

    conn.commit()
    conn.close()
    
    registrar_log_sistema("organizar_fila", f"{len(novos_itens_ordenados)} itens reorganizados por categoria em blocos de 3 com diversidade.")
    return len(novos_itens_ordenados)

# --- LISTAS AMPLIADAS DE TEMPLATES E CUPONS ---

TITULOS_SHOPEE = [
    "🔥 ACHADINHO IMPERDÍVEL NA SHOPEE", "⚡ OPORTUNIDADE RELÂMPAGO NA SHOPEE",
    "🎯 ACHADO DO DIA NA SHOPEE", "💥 PREÇO CAIU NA SHOPEE",
    "🚨 ALERTA DE MENOR PREÇO NA SHOPEE", "😱 VALOR SURREAL NA SHOPEE",
    "🤩 ACHADO POPULAR NA SHOPEE", "📉 DESCONTO ATIVADO NA SHOPEE",
    "💎 OFERTA TOP NA SHOPEE", "📦 PROMOÇÃO ESPECIAL NA SHOPEE",
    "👑 O MAIS DESEJADO DA SHOPEE", "🔍 GARIMPO DA SHOPEE",
    "⚠️ CORRE PRA VER NA SHOPEE", "🤑 ECONOMIA GARANTIDA NA SHOPEE",
    "🌟 ACHADO EXCLUSIVO NA SHOPEE", "🎉 SUPER DESCONTO NA SHOPEE",
    "🏆 TOP DICA DE COMPRA SHOPEE", "💰 OFERTA SELECIONADA SHOPEE",
    "🏷️ CUPOM E FRETE APLICADO NA SHOPEE", "🛍️ ITEM MAIS VENDIDO DA SHOPEE"
]

TITULOS_ML = [
    "🔥 OFERTA DESTAQUE NO MERCADO LIVRE", "⚡ FULL & PREÇO BAIXO NO MERCADO LIVRE",
    "🎯 ACHADINHO NO MERCADO LIVRE", "💥 DESCONTO BRUTO NO MERCADO LIVRE",
    "🚨 ALERTA DE PREÇO NO MERCADO LIVRE", "😱 VALOR IMPERDÍVEL NO MERCADO LIVRE",
    "🤩 OPORTUNIDADE NO MERCADO LIVRE", "📉 QUEDA DE PREÇO NO MERCADO LIVRE",
    "💎 ACHADO PREMIUM NO MERCADO LIVRE", "📦 PROMOÇÃO IMPERDÍVEL NO MERCADO LIVRE",
    "👑 CAMPEÃO DE VENDAS NO MERCADO LIVRE", "🔍 GARIMPO DO MERCADO LIVRE",
    "⚠️ CORRE QUE ACABA NO MERCADO LIVRE", "🤑 PREÇO DE ATACADO NO MERCADO LIVRE",
    "🌟 OFERTA ESPECIAL NO MERCADO LIVRE", "🚀 ENVIO FULL NO MERCADO LIVRE",
    "⭐ MAIS AVALIADO DO MERCADO LIVRE", "🏆 SELEÇÃO EXCLUSIVA MERCADO LIVRE",
    "🚚 FRETE RÁPIDO NO MERCADO LIVRE", "🏷️ LIQUIDAÇÃO NO MERCADO LIVRE"
]

TITULOS_AMAZON = [
    "🔥 OFERTA RELÂMPAGO NA AMAZON", "⚡ ACHADO IMPERDÍVEL NA AMAZON",
    "🎯 PREÇO BAIXO NA AMAZON", "💥 DESCONTO ESPECIAL NA AMAZON",
    "🚨 ALERTA DE OPORTUNIDADE NA AMAZON", "😱 VALOR HISTÓRICO NA AMAZON",
    "🤩 DESTAQUE DO DIA NA AMAZON", "📉 QUEDA DE VALOR NA AMAZON",
    "💎 ACHADO EXCLUSIVO NA AMAZON", "📦 PROMOÇÃO DA AMAZON",
    "👑 MAIS VENDIDO NA AMAZON", "🔍 GARIMPO DA AMAZON",
    "⚠️ CORRE ANTES QUE MUDE NA AMAZON", "🤑 ECONOMIA RESTE NA AMAZON",
    "🌟 ACHADO IMPERDÍVEL NA AMAZON", "📦 FRETE PRIME NA AMAZON",
    "⭐ ESCOLHA DA AMAZON", "🏆 DESTAQUE DA SEMANA AMAZON",
    "🏷️ DESCONTO PRIME NA AMAZON", "🛒 OFERTA IMPERDÍVEL AMAZON"
]

TITULOS_ALIEXPRESS = [
    "🔥 ACHADO INTERNACIONAL NO ALIEXPRESS", "⚡ OFERTA GLOBAL NO ALIEXPRESS",
    "🎯 PREÇO DE FÁBRICA NO ALIEXPRESS", "💥 DESCONTO IMPORTADO NO ALIEXPRESS",
    "🚨 ALERTA GERAL NO ALIEXPRESS", "😱 VALOR IMPOSSÍVEL NO ALIEXPRESS",
    "🤩 DESTAQUE GERAL NO ALIEXPRESS", "📉 QUEDA DE PREÇO NO ALIEXPRESS",
    "💎 ACHADO DOS GORDS NO ALIEXPRESS", "📦 PROMOÇÃO GLOBAL NO ALIEXPRESS",
    "👑 MAIS IMPORTADO NO ALIEXPRESS", "🔍 GARIMPO INTERNACIONAL",
    "⚠️ CORRE ANTES DA TRIBUTAÇÃO", "🤑 ECONOMIA MONSTRUOSA",
    "🌟 ACHADO ESPECIAL DE FORA", "🌐 DIRETO DO FABRICANTE NO ALIEXPRESS"
]

TITULOS_KABUM = [
    "🔥 OFERTA GAMER & TECH NA KABUM", "⚡ HARDWARE EM PROMOÇÃO NA KABUM",
    "🎯 ACHADO DE INFORMÁTICA NA KABUM", "💥 PREÇO DERRETIDO NA KABUM",
    "🚨 ALERTA TECH NA KABUM", "😱 VALOR INSANO NA KABUM",
    "🤩 SETUP UPGRADE NA KABUM", "📉 QUEDA DE PREÇO TECH",
    "💎 ACHADO EXCLUSIVO KABUM", "📦 PROMOÇÃO DO DIA KABUM",
    "👑 MAIS PROCURADO KABUM", "🔍 GARIMPO DE PLACA E PROCESSADOR",
    "⚠️ CORRE QUE O ESTOQUE É CURTO", "🤑 ECONOMIA NO SETUP",
    "🌟 HARDWARE TOP NA KABUM", "💻 TECH DE ALTA PERFORMANCE KABUM"
]

TITULOS_MAGALU = [
    "🔥 OFERTA ESPECIAIS MAGAZINE LUIZA", "⚡ ENTREGA RÁPIDA MAGALU",
    "🎯 ACHADINHO IMPERDÍVEL MAGALU", "💥 LIQUIDAÇÃO MAGALU",
    "🚨 ALERTA DE PREÇO BAIXO MAGALU", "😱 QUEIMA DE ESTOQUE MAGALU",
    "🤩 DESTAQUE DO DIA MAGALU", "📉 MENOR PREÇO MAGALU",
    "💎 OPORTUNIDADE EXCLUSIVA MAGALU", "📦 PROMOÇÃO RELÂMPAGO MAGALU",
    "👑 MAIS VENDIDO NO MAGALU", "🔍 GARIMPO MAGALU",
    "⚠️ CORRE ANTES QUE ACABE NO MAGALU", "🤑 PREÇO IMPERDÍVEL MAGALU",
    "🌟 ACHADO TOP MAGAZINE LUIZA", "🛒 OFERTA DO APLICATIVO MAGALU"
]

TITULOS_GERAIS = [
    "🔥 OFERTA IMPERDÍVEL DO DIA", "⚡ ACHADO ESPECIAL SELECIONADO",
    "🎯 PREÇO BAIXO DETECTADO", "💥 DESCONTO EXCLUSIVO LIBERADO",
    "🚨 ALERTA DE OPORTUNIDADE", "😱 VALOR SURPRESA ENCONTRADO",
    "🤩 DESTAQUE RECOMENDADO", "📉 MENOR VALOR DO MÊS",
    "💎 ACHADO VALIOSO", "📦 PROMOÇÃO RELÂMPAGO",
    "👑 ITEM MAIS BUSCADO", "🔍 GARIMPO DE PREÇO",
    "⚠️ CORRE ANTES QUE ACABE", "🤑 ECONOMIA TOTAL",
    "🌟 ACHADO TOP DO DIA", "🏆 MELHOR SELEÇÃO DO DIA"
]

CHAMADAS_SHOPEE = [
    "Frete grátis e cupom de desconto ativado no link!",
    "Menor valor histórico na plataforma, aproveite o frete!",
    "Achadinho viralizado com avaliação máxima garantida!",
    "Corre para resgatar os cupons de frete grátis do dia!",
    "Preço despencou direto no aplicativo da Shopee!",
    "Aproveite antes que o cupom de loja esgote!",
    "Item super bem avaliado pelos compradores!",
    "Garanta o seu com desconto exclusivo de hoje!",
    "Ótima oportunidade para economizar na Shopee!",
    "Um dos itens mais recomendados da categoria!"
]

CHAMADAS_ML = [
    "Full speed, entrega mais rápida do Brasil direto na sua casa!",
    "Menor preço garantido com envio imediato Full!",
    "Oportunidade única com parcelamento facilitado e desconto no link!",
    "Corre pra garantir o seu antes que o estoque Full esgote!",
    "Preço derreteu nas ofertas oficiais do Mercado Livre!",
    "Compra 100% garantida com devolução grátis!",
    "Estoque oficial no centro de distribuição Full!",
    "Entrega super rápida e compra garantida!",
    "Preço especial de promoção disponível por tempo limitado!",
    "Aproveite a oportunidade do Envio Full hoje!"
]

CHAMADAS_AMAZON = [
    "Frete grátis para assinantes Prime garantido!",
    "Menor preço do mês na gigante da tecnologia!",
    "Produto original com garantia e envio prioritário Amazon!",
    "Achadinho altamente recomendado pelos consumidores na Amazon!",
    "Corre que o estoque relâmpago da Amazon vai acabar!",
    "Entrega rápida e garantida direto pela Amazon!",
    "Excelente custo-benefício com avaliação 5 estrelas!",
    "Preço especial com os benefícios exclusivos Prime!",
    "Garanta antes que ocorra a alteração do valor!",
    "Desconto imperdível disponível por poucas horas!"
]

CHAMADAS_ALIEXPRESS = [
    "Preço de fábrica importado direto com super desconto!",
    "Achadinho internacional com envio otimizado para o Brasil!",
    "Menor valor registrado nas ofertas globais da semana!",
    "Garanta já o seu eletrônico de fora antes da variação!",
    "Desconto agressivo liberado no estoque internacional!",
    "Envio Choice com entrega rápida garantida!",
    "Super oferta global direto para a sua casa!",
    "Preço imbatível com desconto de importação!"
]

CHAMADAS_KABUM = [
    "Upgrade perfeito para o seu setup gamer e profissional!",
    "Preço derretido em hardware de ponta na Kabum!",
    "Componente mais desejado pelos entusiastas em promoção!",
    "Corre que o estoque desse item de informática voa rápido!",
    "Desconto exclusivo liberado nas ofertas de tecnologia Kabum!",
    "Garantia e nota fiscal nacional inclusas!",
    "Alta performance garantida pelo menor preço do mercado!",
    "Excelente oportunidade de upgrade para o seu equipamento!"
]

CHAMADAS_MAGALU = [
    "Retire na loja sem pagar frete ou receba rapidinho em casa!",
    "Liquidação oficial Magalu com preço de arrasar o quarteirão!",
    "Oportunidade imperdível na rede que você mais confia!",
    "Corre que o estoque express do Magalu está acabando!",
    "Menor preço do dia com selo de garantia Magazine Luiza!",
    "Preço especial de cupom no aplicativo!",
    "Qualidade garantida e entrega rápida pelo Magalu!",
    "Desconto exclusivo disponível no link oficial!"
]

CHAMADAS_GERAIS = [
    "Corre antes que o estoque acabe e mude o valor!",
    "Menor preço registrado nos últimos dias, aproveite!",
    "Vale cada centavo, excelente custo-benefício!",
    "Desconto aplicado direto no link oficial!",
    "Oportunidade perfeita para garantir o seu hoje!",
    "Garantia de menor preço e alta satisfação!",
    "Aproveite a promoção antes da virada de preço!",
    "Excelente achado com valor reduzido hoje!"
]

CUPONS_MERCADO_LIVRE = [
    "OFERTASMELI", "OFFMELI", "ESTILOML", "OFERTAML", "DESGONTOSML", "CUPONSML", "MELI60", "PROMO20", "MELI100"
]

CUPONS_AMAZON = [
    "FRETEGRATIS", "PRIMEIRACOMPRA", "SUPERMERCADO10", "ELETRONICOS20", "LIVROS10", "PROMOAMZ", "AMAZON15"
]

CUPONS_SHOPEE = [
    "FRETEGRATIS", "SHOPEE10", "VALEPRAMODA", "CUPOMPRACASA", "PRIMEIRACOMPRA", "ACHADOS20", "SHOPEE50"
]

CUPONS_GERAIS = [
    "FRETEGRATIS", "PRIMEIRACOMPRA", "DESCONTOGERAL", "OFERTADIARIA", "PROMOBOT", "CUPOMVIP"
]

# --- DIVERSIFICAÇÃO SEM REPETIÇÃO DIÁRIA ---

def obter_opcao_sem_repetir_no_dia(categoria, lista_opcoes):
    hoje = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT texto_frase FROM frases_usadas_hoje WHERE categoria = ? AND data_uso = ?',
        (categoria, hoje)
    )
    usadas = [row[0] for row in cursor.fetchall()]
    
    disponiveis = [item for item in lista_opcoes if item not in usadas]
    
    if not disponiveis:
        cursor.execute(
            'DELETE FROM frases_usadas_hoje WHERE categoria = ? AND data_uso = ?',
            (categoria, hoje)
        )
        conn.commit()
        disponiveis = list(lista_opcoes)
        
    escolhida = random.choice(disponiveis)
    
    cursor.execute(
        'INSERT INTO frases_usadas_hoje (categoria, texto_frase, data_uso) VALUES (?, ?, ?)',
        (categoria, escolhida, hoje)
    )
    conn.commit()
    conn.close()
    
    return escolhida

def extrair_preco_do_texto(texto):
    if not texto:
        return None
    padroes = [
        r'(?:preço|por|por apenas|de por|valor|à vista)\s*:?\s*(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*[\.,]\d{2})',
        r'(?:preço|por|por apenas|de por|valor|à vista)\s*:?\s*(?:R\$\s*)?(\d+)',
        r'(?:R\$\s*|-?\s*R\$\s*)(\d{1,3}(?:\.\d{3})*[\.,]\d{2})',
        r'(?:R\$\s*|-?\s*R\$\s*)(\d+)'
    ]
    for padrao in padroes:
        matches = re.findall(padrao, texto, re.IGNORECASE)
        if matches:
            for m in matches:
                val_limpo = m.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
                try:
                    val_float = float(val_limpo)
                    if val_float > 1.0:
                        return val_float
                except ValueError:
                    continue
    return None

def extrair_preco_original_do_texto(texto):
    if not texto:
        return None
    padroes = [
        r'(?:de|de R\$)\s*:?\s*(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*[\.,]\d{2})',
        r'(?:de|de R\$)\s*:?\s*(?:R\$\s*)?(\d+)'
    ]
    for padrao in padroes:
        matches = re.findall(padrao, texto, re.IGNORECASE)
        if matches:
            for m in matches:
                val_limpo = m.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
                try:
                    val_float = float(val_limpo)
                    if val_float > 1.0:
                        return val_float
                except ValueError:
                    continue
    return None

def limpar_texto_adicional(texto, link, titulo_produto=""):
    if not texto:
        return ""
    texto_limpo = texto.replace(link, '')
    texto_limpo = re.sub(r'(?:preço|por|valor|de|por apenas|à vista)\s*:?\s*R?\$?\s*\d+[\.,]?\d*', '', texto_limpo, flags=re.IGNORECASE)
    texto_limpo = re.sub(r'[💰💸📦🔥⚡⚠️✅❌]', '', texto_limpo)
    if titulo_produto:
        trecho_titulo = titulo_produto[:30].strip()
        if trecho_titulo:
            texto_limpo = texto_limpo.replace(trecho_titulo, '')
    
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo).strip()
    if len(texto_limpo) < 4:
        return ""
    return texto_limpo

def aplicar_marca_dagua(imagem_bytes):
    try:
        logo_path = None
        for nome in LOGO_POSSIBLE_FILENAMES:
            if os.path.exists(nome):
                logo_path = nome
                break
        if not logo_path:
            return imagem_bytes
            
        img_produto = Image.open(BytesIO(imagem_bytes)).convert("RGBA")
        img_logo = Image.open(logo_path).convert("RGBA")
        
        largura_p, altura_p = img_produto.size
        nova_largura_logo = int(largura_p * 0.20)
        proporcao = nova_largura_logo / float(img_logo.size[0])
        nova_altura_logo = int(float(img_logo.size[1]) * float(proporcao))
        
        img_logo = img_logo.resize((nova_largura_logo, nova_altura_logo), Image.Resampling.LANCZOS)
        pos_x = largura_p - nova_largura_logo - 15
        pos_y = altura_p - nova_altura_logo - 15
        
        img_produto.paste(img_logo, (pos_x, pos_y), img_logo)
        output = BytesIO()
        img_produto.convert("RGB").save(output, format="JPEG", quality=90)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Erro ao processar marca d'água: {e}")
        return imagem_bytes

def limpar_titulo(titulo):
    if not titulo:
        return ""
    titulo = re.sub(r'\s*[|:-]\s*.*?(?:Site|Perfil|Market|Amazon|Shopee|Loja|Ofertas|Pagina|Brasil|Compre|Mercado Livre|Aliexpress|Kabum|Magalu).*$', '', titulo, flags=re.IGNORECASE)
    titulo = re.sub(r'(?i)^\s*(?:frete grátis|melhor preço|promoção|oferta|produto shopee|produto amazon|compre)\s*[-:]?\s*', '', titulo)
    titulo = re.sub(r'\s+', ' ', titulo).strip()
    if len(titulo) > 80:
        titulo = titulo[:77] + "..."
    return titulo if len(titulo) >= 5 else ""

def extrair_dados_produto(link):
    dados = {'titulo': None, 'preco_original': None, 'preco_desconto': None}
    titulo_final = None
    preco_final = None
    
    try:
        session = requests.Session()
        response = session.get(link, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            if 'name' in item and not titulo_final:
                                titulo_final = limpar_titulo(item['name'])
                            if 'offers' in item:
                                offers = item['offers']
                                if isinstance(offers, list):
                                    offers = offers[0] if offers else None
                                if isinstance(offers, dict) and 'price' in offers:
                                    try:
                                        preco_final = float(offers['price'])
                                    except:
                                        pass
                elif isinstance(data, dict):
                    if 'name' in data and not titulo_final:
                        titulo_final = limpar_titulo(data['name'])
                    if 'offers' in data:
                        offers = data['offers']
                        if isinstance(offers, list):
                            offers = offers[0] if offers else None
                        if isinstance(offers, dict) and 'price' in offers:
                            try:
                                preco_final = float(offers['price'])
                            except:
                                pass
            except:
                continue

        if not titulo_final:
            meta_title = (soup.find('meta', {'property': 'og:title'}) or 
                          soup.find('meta', {'name': 'twitter:title'}) or 
                          soup.find('meta', {'name': 'title'}))
            if meta_title and meta_title.get('content'):
                titulo_final = limpar_titulo(meta_title.get('content'))

        if not titulo_final:
            h1_selectors = [
                'h1', 'span[class*="title"]', 'span[class*="product-name"]',
                'span[class*="ui-pdp-title"]', 'div[class*="product-title"]',
                'div[class*="item-title"]', 'span[itemprop="name"]', 'h1[itemprop="name"]'
            ]
            for selector in h1_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        titulo_final = limpar_titulo(elem.text)
                        if titulo_final and len(titulo_final) > 5:
                            break
                except:
                    continue

        if not titulo_final:
            title_tag = soup.find('title')
            if title_tag:
                titulo_final = limpar_titulo(title_tag.text)

        if 'amazon' in link.lower():
            price_selectors = [
                'span.a-price span.a-offscreen', 'span.a-price[data-a-size="xl"] span.a-offscreen',
                'span#priceblock_ourprice', 'span#priceblock_dealprice', 'span.a-price-whole'
            ]
            for selector in price_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        preco_texto = elem.text.replace('R$', '').replace('.', '').replace(',', '.').strip()
                        try:
                            preco_final = float(preco_texto)
                            break
                        except:
                            pass
                except:
                    continue
                    
        elif 'mercadolivre' in link.lower() or 'meli.la' in link.lower():
            price_selectors = [
                'span.andes-money-amount__fraction', 'span.ui-pdp-price__value',
                'meta[itemprop="price"]', '.ui-pdp-price--second-line .andes-money-amount__fraction'
            ]
            for selector in price_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        if elem.name == 'meta':
                            preco_texto = elem.get('content', '')
                        else:
                            preco_texto = elem.text
                        preco_texto = preco_texto.replace('.', '').replace(',', '.').strip()
                        try:
                            preco_final = float(preco_texto)
                            break
                        except:
                            pass
                except:
                    continue
                    
        elif 'shopee' in link.lower() or 'shp.ee' in link.lower():
            for script in soup.find_all('script'):
                if script.string and 'window.__INITIAL_STATE__' in script.string:
                    try:
                        import re
                        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            if 'product' in data and 'price' in data['product']:
                                preco_final = float(data['product']['price'] / 100000)
                            if 'product' in data and 'name' in data['product'] and not titulo_final:
                                titulo_final = limpar_titulo(data['product']['name'])
                    except:
                        pass

        if not preco_final:
            for script in soup.find_all('script'):
                if script.string:
                    matches = re.findall(r'[Rr]\$[\s]*([\d.,]+)', script.string)
                    for match in matches:
                        try:
                            val = float(match.replace('.', '').replace(',', '.'))
                            if val > 10:
                                preco_final = val
                                break
                        except:
                            pass
                    if preco_final:
                        break

        if not titulo_final or titulo_final == "Produto em Oferta Especial":
            url_parts = link.split('/')
            for part in url_parts:
                if len(part) > 10 and not part.startswith('http'):
                    titulo_final = limpar_titulo(part.replace('-', ' ').replace('_', ' '))
                    if titulo_final and len(titulo_final) > 5:
                        break
            
            if not titulo_final or titulo_final == "Produto em Oferta Especial":
                titulo_final = f"Produto em Oferta - {datetime.datetime.now().strftime('%H:%M')}"

        dados['titulo'] = titulo_final
        dados['preco_desconto'] = preco_final
        
        if 'amazon' in link.lower():
            for script in soup.find_all('script'):
                if script.string and 'price' in script.string.lower():
                    matches = re.findall(r'[Rr]\$[\s]*([\d.,]+)', script.string)
                    if len(matches) >= 2:
                        try:
                            preco_orig = float(matches[0].replace('.', '').replace(',', '.'))
                            preco_desc = float(matches[1].replace('.', '').replace(',', '.'))
                            if preco_orig > preco_desc:
                                dados['preco_original'] = preco_orig
                                dados['preco_desconto'] = preco_desc
                        except:
                            pass

        logger.info(f"Dados extraídos: Título='{titulo_final}', Preço={preco_final}")
        return dados
        
    except Exception as e:
        logger.error(f"Erro ao extrair dados: {e}")
        return {'titulo': 'Produto em Oferta Especial', 'preco_original': None, 'preco_desconto': None}

def selecionar_cupom_por_plataforma(plataforma):
    if plataforma == 'mercadolivre':
        return random.choice(CUPONS_MERCADO_LIVRE)
    elif plataforma == 'amazon':
        return random.choice(CUPONS_AMAZON)
    elif plataforma == 'shopee':
        return random.choice(CUPONS_SHOPEE)
    else:
        return random.choice(CUPONS_GERAIS)

def criar_link_rastreado(link_original, titulo, plataforma, preco_desc, preco_orig):
    try:
        link_original = adicionar_parametro_afiliado(link_original, plataforma)
        logger.info(f"Link com afiliado: {link_original}")
        
        desconto_perc = 0
        if preco_orig and preco_desc and preco_orig > preco_desc:
            desconto_perc = round(((preco_orig - preco_desc) / preco_orig) * 100)
        
        categoria = identificar_categoria(titulo)
        
        dados = {
            'link_original': link_original,
            'titulo': titulo,
            'plataforma': plataforma,
            'categoria': categoria,
            'preco_desconto': preco_desc,
            'preco_original': preco_orig
        }
        
        response = requests.post(
            f'{TRACKING_SERVER}/api/criar_link',
            json=dados,
            timeout=10
        )
        
        if response.status_code == 200:
            resultado = response.json()
            return {
                'short_code': resultado.get('short_code'),
                'link_encurtado': resultado.get('link_encurtado'),
                'categoria': categoria
            }
        else:
            logger.error(f"Erro ao criar link rastreável: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Erro ao criar link rastreável: {e}")
        return None

def montar_layout_mensagem(dados, link, texto_adicional, origem='manual'):
    p_desc = dados.get('preco_desconto')
    p_orig = dados.get('preco_original')
    
    porcentagem = 0
    if p_orig and p_desc and p_orig > p_desc:
        porcentagem = round(((p_orig - p_desc) / p_orig) * 100)
            
    titulo_produto = html.escape(dados.get('titulo', 'Produto em Oferta'))
    link_lower = link.lower()
    plataforma = identificar_plataforma(link)
    categoria = identificar_categoria(dados.get('titulo', ''))
    
    short_code = None
    link_final = link
    
    if origem == 'garimpo':
        if plataforma == 'shopee':
            link_final = LINK_VITRINE_SHOPEE
        elif plataforma == 'amazon':
            link_final = LINK_VITRINE_AMAZON
        elif plataforma == 'mercadolivre':
            link_final = LINK_PERFIL_ML
        else:
            link_final = LINK_VITRINE_SHOPEE
    else:
        link_rastreado = criar_link_rastreado(link, dados.get('titulo', ''), plataforma, p_desc, p_orig)
        if link_rastreado:
            link_final = link_rastreado.get('link_encurtado')
            short_code = link_rastreado.get('short_code')
            categoria = link_rastreado.get('categoria', categoria)
        else:
            link_final = adicionar_parametro_afiliado(link, plataforma)

    if 'shopee' in link_lower:
        titulo_topo = obter_opcao_sem_repetir_no_dia("titulo_shopee", TITULOS_SHOPEE)
        chamada_texto = obter_opcao_sem_repetir_no_dia("chamada_shopee", CHAMADAS_SHOPEE)
    elif 'mercadolivre' in link_lower or 'meli.la' in link_lower:
        titulo_topo = obter_opcao_sem_repetir_no_dia("titulo_ml", TITULOS_ML)
        chamada_texto = obter_opcao_sem_repetir_no_dia("chamada_ml", CHAMADAS_ML)
    elif 'amazon' in link_lower:
        titulo_topo = obter_opcao_sem_repetir_no_dia("titulo_amazon", TITULOS_AMAZON)
        chamada_texto = obter_opcao_sem_repetir_no_dia("chamada_amazon", CHAMADAS_AMAZON)
    elif 'aliexpress' in link_lower:
        titulo_topo = obter_opcao_sem_repetir_no_dia("titulo_aliexpress", TITULOS_ALIEXPRESS)
        chamada_texto = obter_opcao_sem_repetir_no_dia("chamada_aliexpress", CHAMADAS_ALIEXPRESS)
    elif 'kabum' in link_lower:
        titulo_topo = obter_opcao_sem_repetir_no_dia("titulo_kabum", TITULOS_KABUM)
        chamada_texto = obter_opcao_sem_repetir_no_dia("chamada_kabum", CHAMADAS_KABUM)
    elif 'magalu' in link_lower or 'magazineluiza' in link_lower:
        titulo_topo = obter_opcao_sem_repetir_no_dia("titulo_magalu", TITULOS_MAGALU)
        chamada_texto = obter_opcao_sem_repetir_no_dia("chamada_magalu", CHAMADAS_MAGALU)
    else:
        titulo_topo = obter_opcao_sem_repetir_no_dia("titulo_gerais", TITULOS_GERAIS)
        chamada_texto = obter_opcao_sem_repetir_no_dia("chamada_gerais", CHAMADAS_GERAIS)
    
    str_original = f"<s>R$ {p_orig:.2f}</s>".replace('.', ',') if p_orig else ""
    str_desconto = f"{p_desc:.2f}".replace('.', ',') if p_desc else "Veja no link"
    str_porcentagem = f"💥 <b>{porcentagem}% OFF</b>" if porcentagem > 0 else ""

    bloco_extra = ""
    contador_atual = incrementar_e_verificar_contador_plataforma(plataforma)
    if contador_atual == 4:
        cupom_escolhido = selecionar_cupom_por_plataforma(plataforma)
        bloco_extra += f"\n🎟️ <b>Cupom exclusivo desta loja:</b> <code>{cupom_escolhido}</code>"

    texto_adicional_limpo = limpar_texto_adicional(texto_adicional, link, dados.get('titulo', ''))

    badge_tracking = f"🔗 <i>Link rastreável gerado</i>" if short_code else ""
    badge_afiliado = f"🤝 <i>Link com código de afiliado</i>"

    template = "{titulo_topo}\n\n"
    template += "🔥 <b>{titulo_produto}</b>\n\n"
    
    if str_original:
        template += "❌ De: {str_original}\n"
        
    template += "🟢 <b>Por: R$ {str_desconto}</b>\n"
    
    if str_porcentagem:
        template += "{str_porcentagem}\n"
        
    if texto_adicional_limpo:
        template += f"\n<i>ℹ️ {html.escape(texto_adicional_limpo)}</i>\n"
    else:
        template += f"\n<i>⚡ {chamada_texto}</i>\n"

    rotulo_link = (
        "👉 <b>Garanta já o seu com desconto no link oficial:</b>\n<a href='{link}'>{link}</a>"
        if origem == 'garimpo'
        else "👉 <b>Link oficial da oferta:</b>\n<a href='{link}'>{link}</a>"
    )

    template += (
        "\n⚠️ <b>Estoque LIMITADO — corre antes que acabe!</b>"
        f"{bloco_extra}\n\n"
        f"{rotulo_link}"
    )
    
    if badge_tracking:
        template += f"\n\n{badge_tracking}"
    if badge_afiliado and short_code:
        template += f" • {badge_afiliado}"
    
    return template.format(
        titulo_topo=titulo_topo,
        titulo_produto=titulo_produto,
        str_original=str_original,
        str_desconto=str_desconto,
        str_porcentagem=str_porcentagem,
        bloco_extra=bloco_extra,
        link=link_final
    )

async def enviar_para_grupo_promos(context, dados, link, texto_adicional="", origem='manual', file_id_foto=None):
    global ULTIMO_ENVIO_TIMESTAMP
    mensagem = montar_layout_mensagem(dados, link, texto_adicional, origem)
    try:
        if file_id_foto:
            try:
                await context.bot.send_photo(
                    chat_id=GRUPO_PROMOS_ID, 
                    photo=file_id_foto, 
                    caption=mensagem, 
                    parse_mode='HTML'
                )
            except Exception as e_file:
                logger.error(f"Erro ao enviar com file_id do telegram: {e_file}")
                await context.bot.send_message(
                    chat_id=GRUPO_PROMOS_ID, 
                    text=mensagem, 
                    parse_mode='HTML', 
                    disable_web_page_preview=False
                )
        else:
            await context.bot.send_message(
                chat_id=GRUPO_PROMOS_ID, 
                text=mensagem, 
                parse_mode='HTML', 
                disable_web_page_preview=False
            )
        
        registrar_envio_historico(link, short_code=None, categoria=identificar_categoria(dados.get('titulo', '')), titulo=dados.get('titulo', ''))
        ULTIMO_ENVIO_TIMESTAMP = datetime.datetime.now()
        salvar_ultimo_timestamp(ULTIMO_ENVIO_TIMESTAMP)
        return True
    except Exception as e:
        logger.error(f"Erro envio final: {e}")
        return False

# --- CONTROLE COM INTERVALO RIGOROSO DE 8 MINUTOS CORRIGIDO ---
async def processador_fila_background(context: ContextTypes.DEFAULT_TYPE):
    global ULTIMO_ENVIO_TIMESTAMP, BOT_PAUSADO
    
    if BOT_PAUSADO:
        return

    # Garante a contagem exata em segundos do intervalo de 8 minutos
    agora = datetime.datetime.now()
    intervalo_segundos = INTERVALO_POSTAGEM_MINUTOS * 60
    tempo_desde_ultimo = (agora - ULTIMO_ENVIO_TIMESTAMP).total_seconds()
    
    if tempo_desde_ultimo < intervalo_segundos:
        faltam = int(intervalo_segundos - tempo_desde_ultimo)
        logger.info(f"Aguardando intervalo de 8 min: faltam {faltam}s ({faltam // 60}m {faltam % 60}s)")
        return

    total_fila = contar_fila_atual()
    if total_fila == 0:
        return

    item = proximo_da_fila()
    if item:
        dados = item['dados']
        link = item['link']
        texto_adicional = item['texto_adicional']
        origem = item['origem']
        file_id_foto = item['file_id_foto']
        
        sucesso = await enviar_para_grupo_promos(context, dados, link, texto_adicional, origem, file_id_foto)
        if sucesso:
            logger.info(f"✅ Postagem enviada com sucesso! Próxima em {INTERVALO_POSTAGEM_MINUTOS} minutos.")
        else:
            conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO fila_postagens (dados_json, link, texto_adicional, origem, file_id_foto, status) VALUES (?, ?, ?, ?, ?, ?)',
                (json.dumps(dados), link, texto_adicional, origem, file_id_foto, 'pendente')
            )
            conn.commit()
            conn.close()
            logger.warning("⚠️ Falha no envio, item retornado à fila.")

def calcular_horario_publicacao(ordem_na_data):
    agora = datetime.datetime.now()
    minutos_totais = agora.minute + (ordem_na_data * INTERVALO_POSTAGEM_MINUTOS)
    horas_extra = minutos_totais // 60
    minutos_final = minutos_totais % 60
    hora_final = (agora.hour + horas_extra) % 24
    return f"{hora_final:02d}:{minutos_final:02d}"

# --- COMANDOS ---

async def relatorio_completo_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return

    try:
        dados_cliques = None
        try:
            response = requests.get(f'{TRACKING_SERVER}/api/estatisticas', timeout=10)
            if response.status_code == 200:
                dados_cliques = response.json()
        except:
            pass

        conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('SELECT id, dados_json, link, origem FROM fila_postagens WHERE status = ? ORDER BY id ASC', ('pendente',))
        rows = cursor.fetchall()
        total_na_fila = len(rows)

        total_enviados_hoje = contar_historico_hoje()
        
        total_cliques = 0
        cliques_hoje = 0
        produto_top = "Nenhum"
        cliques_por_plataforma = []
        
        if dados_cliques:
            total_cliques = dados_cliques.get('total_cliques', 0)
            cliques_hoje = dados_cliques.get('cliques_hoje', 0)
            if dados_cliques.get('produto_mais_clicado'):
                produto_top = dados_cliques['produto_mais_clicado'][0][:35] if dados_cliques['produto_mais_clicado'] else "Nenhum"
            cliques_por_plataforma = dados_cliques.get('cliques_plataforma', [])

        conn_metrics = sqlite3.connect(DB_METRICS_PATH, timeout=30.0)
        cursor_metrics = conn_metrics.cursor()
        
        cursor_metrics.execute('SELECT COUNT(*) FROM cliques_detalhados')
        total_cliques_rastreados = cursor_metrics.fetchone()[0] or 0
        
        cursor_metrics.execute('''
            SELECT titulo_produto, COUNT(*) as total
            FROM cliques_detalhados
            GROUP BY titulo_produto
            ORDER BY total DESC
            LIMIT 1
        ''')
        produto_top_metrics = cursor_metrics.fetchone()
        
        conn_metrics.close()
        conn.close()

        status_bot = "⏸️ Pausado" if BOT_PAUSADO else "▶️ Em Execução"

        relatorio_msg = (
            "📈 <b>RELATÓRIO COMPLETO DE PERFORMANCE</b>\n"
            "──────────────────────────────────────────\n\n"
            f"🤖 <b>Status dos Disparos:</b> {status_bot}\n"
            f"📅 <b>Data:</b> {datetime.date.today().strftime('%d/%m/%Y')}\n"
            f"⏱️ <b>Último envio:</b> {ULTIMO_ENVIO_TIMESTAMP.strftime('%H:%M:%S')}\n"
            f"⏰ <b>Próximo envio em:</b> {INTERVALO_POSTAGEM_MINUTOS} minutos\n\n"
        )

        relatorio_msg += (
            "📦 <b>VOLUMETRIA</b>\n"
            f"• Enviados Hoje: <b>{total_enviados_hoje}</b>\n"
            f"• Aguardando Fila: <b>{total_na_fila}</b>\n\n"
        )

        if total_cliques > 0 or total_cliques_rastreados > 0:
            relatorio_msg += (
                "🖱️ <b>MÉTRICAS DE CLIQUES</b>\n"
                f"• Total de Cliques: <b>{total_cliques}</b>\n"
                f"• Cliques Hoje: <b>{cliques_hoje}</b>\n"
            )
            
            if produto_top_metrics:
                relatorio_msg += f"• 🏆 Produto Mais Clicado: <b>{html.escape(produto_top_metrics[0][:40])}</b> ({produto_top_metrics[1]} cliques)\n"
            
            if cliques_por_plataforma:
                relatorio_msg += "\n📊 <b>Cliques por Plataforma:</b>\n"
                for plat, qtd in cliques_por_plataforma[:5]:
                    relatorio_msg += f"  • {plat.upper()}: {qtd} cliques\n"
            
            relatorio_msg += "\n"

        relatorio_msg += (
            "──────────────────────────────────────────\n"
            f"⏰ <b>Intervalo entre postagens:</b> {INTERVALO_POSTAGEM_MINUTOS} minutos\n"
            "💡 <i>Use /comandos para ver todas as opções</i>"
        )

        await update.message.reply_text(relatorio_msg, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Erro no relatorio: {e}")
        await update.message.reply_text(f"❌ Erro ao gerar relatório: {str(e)}", parse_mode='HTML')

async def organizar_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
        
    total_fila = contar_fila_atual()
    if total_fila == 0:
        await update.message.reply_text("📦 A fila está vazia! Não há produtos para organizar.", parse_mode='HTML')
        return

    await update.message.reply_text("⚙️ <b>Analisando inteligência e reorganizando a fila em blocos de 3 com diversidade de produtos...</b>", parse_mode='HTML')
    
    total_processado = reordenar_fila_blocos_de_3()
    
    msg_sucesso = (
        f"✅ <b>FILA REORGANIZADA COM SUCESSO!</b>\n\n"
        f"📊 Total de itens organizados: <b>{total_processado}</b>\n"
        f"🧠 <b>Estratégia Aplicada:</b> Produtos agrupados em blocos de 3 por categoria/plataforma sem repetir o mesmo produto em sequência.\n\n"
        f"💡 <i>Use <code>/fila</code> para visualizar a nova sequência organizada!</i>"
    )
    
    await update.message.reply_text(msg_sucesso, parse_mode='HTML')

async def ver_fila_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('SELECT id, dados_json, link, data_agendamento, origem FROM fila_postagens WHERE status = ? ORDER BY id ASC', ('pendente',))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("📦 A fila de postagens está vazia no momento.")
        return
    
    cabecalho = f"📊 <b>STATUS DA FILA DE POSTAGENS</b>\n\nTotal na fila: <b>{len(rows)} itens</b>\n\n"
    
    mensagens = []
    mensagem_atual = cabecalho

    for idx, row in enumerate(rows, 1):
        try:
            dados = json.loads(row[1])
            titulo = dados.get('titulo', 'Produto em Oferta Especial')
            preco = dados.get('preco_desconto')
            preco_orig = dados.get('preco_original')
        except:
            titulo = "Produto em Oferta Especial"
            preco = None
            preco_orig = None
        
        origem_item = row[4]
        horario_previsto = calcular_horario_publicacao(idx)
        
        motivos_erro = []
        if not titulo or titulo == "Produto em Oferta Especial":
            motivos_erro.append("Título Genérico")
        if not preco or preco <= 1:
            motivos_erro.append("Preço faltando")
            
        status_emoji = "🟩" if not motivos_erro else "❌"
        detalhe_erro = f" <i>(Falta: {', '.join(motivos_erro)})</i>" if motivos_erro else ""
            
        titulo_exibicao = titulo if titulo else "Produto em Oferta Especial"
        if len(titulo_exibicao) > 40:
            titulo_exibicao = titulo_exibicao[:37] + "..."

        tag_origem = "🌐 [Garimpo]" if origem_item == 'garimpo' else "👤 [Manual]"
        preco_str = f"R$ {preco:.2f}".replace('.', ',') if preco and preco > 1 else "Não detectado"
        orig_str = f" (De: R$ {preco_orig:.2f})".replace('.', ',') if preco_orig and preco_orig > 0 else ""

        bloco_item = f"{idx}ª Posição | Às {horario_previsto} {tag_origem}\n"
        bloco_item += f"🛍️ <b>{html.escape(titulo_exibicao)}</b> | 💰 {preco_str}{orig_str} {status_emoji}{detalhe_erro}\n"
        bloco_item += f"💡 <i>Use /prever {idx} para testar | /personalizar {idx}</i>\n\n"
        
        if len(mensagem_atual) + len(bloco_item) > 3500:
            mensagens.append(mensagem_atual)
            mensagem_atual = bloco_item
        else:
            mensagem_atual += bloco_item

    if mensagem_atual:
        mensagens.append(mensagem_atual)

    for msg in mensagens:
        await update.message.reply_text(msg, parse_mode='HTML')

async def refresh_fila_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    await update.message.reply_text("ok")

async def remover_item_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Use: <code>/remover 3</code>", parse_mode='HTML')
        return
    try:
        posicao = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Posição inválida.")
        return
        
    item = obter_item_por_posicao(posicao)
    if not item:
        await update.message.reply_text(f"❌ Nenhum item na {posicao}ª posição.")
        return
        
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM fila_postagens WHERE id = ?', (item['db_id'],))
    conn.commit()
    conn.close()
    
    restantes = contar_fila_atual()
    await update.message.reply_text(f"🗑️ Item removido! Restantes na fila: <b>{restantes}</b>", parse_mode='HTML')

async def limpar_fila_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    total_antes = contar_fila_atual()
    if total_antes == 0:
        await update.message.reply_text("📦 A fila já está vazia!", parse_mode='HTML')
        return
    
    conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM fila_postagens WHERE status = ?', ('pendente',))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"🧹 Toda a fila foi limpa! Total de <b>{total_antes}</b> itens removidos.", parse_mode='HTML')

async def pausar_bot_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSADO
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    BOT_PAUSADO = True
    registrar_log_sistema("pausar", "Disparos pausados manualmente.")
    await update.message.reply_text("⏸️ Disparos pausados!", parse_mode='HTML')

async def retomar_bot_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSADO
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    BOT_PAUSADO = False
    registrar_log_sistema("retomar", "Disparos retomados manualmente.")
    await update.message.reply_text("▶️ Disparos retomados!", parse_mode='HTML')

async def desbugar_fila_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    global ULTIMO_ENVIO_TIMESTAMP
    ULTIMO_ENVIO_TIMESTAMP = datetime.datetime.min
    salvar_ultimo_timestamp(ULTIMO_ENVIO_TIMESTAMP)
    registrar_log_sistema("desbugar", "Timestamp resetado para forçar novo envio.")
    await update.message.reply_text("🛠️ Bot debugado! Próximo envio será imediato.", parse_mode='HTML')

async def ver_logs_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    logs = obter_logs_recentes(10)
    if not logs:
        await update.message.reply_text("📜 Nenhum registro encontrado no histórico de logs.", parse_mode='HTML')
        return
    
    texto_logs = "📜 <b>REGISTROS OPERACIONAIS RECENTES</b>\n\n"
    for tipo, detalhes, data_hora in logs:
        texto_logs += f"🕒 <code>{data_hora}</code> | <b>{tipo.upper()}</b>\n"
        texto_logs += f"💬 <i>{html.escape(detalhes)}</i>\n\n"
        
    await update.message.reply_text(texto_logs, parse_mode='HTML')

async def iniciar_edicao_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Use: <code>/editar 5</code>", parse_mode='HTML')
        return
    try:
        posicao = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Posição inválida.")
        return
    item = obter_item_por_posicao(posicao)
    if not item:
        await update.message.reply_text("❌ Item não encontrado.")
        return
    context.user_data['editar_db_id'] = item['db_id']
    await update.message.reply_text("👉 Envie o novo link do produto:", parse_mode='HTML')
    return EDITAR_ITEM_PASSO

async def receber_novo_link_edicao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return ConversationHandler.END
    novo_link = update.message.text.strip()
    db_id = context.user_data.get('editar_db_id')
    dados_novos = extrair_dados_produto(novo_link)
    if dados_novos:
        atualizar_item_banco(db_id, dados_novos, novo_link, "")
        await update.message.reply_text("✅ Item atualizado na fila!", parse_mode='HTML')
    else:
        await update.message.reply_text("❌ Falha ao extrair dados.")
    context.user_data.clear()
    return ConversationHandler.END

async def aplicar_alteracao_personalizar(update: Update, item: dict, preco_promo: float, preco_original: float):
    db_id = item['db_id']
    dados = item['dados']
    link = item['link']
    texto_adicional = item['texto_adicional']

    if preco_original > 0 and preco_original < preco_promo:
        preco_promo, preco_original = preco_original, preco_promo

    dados['preco_desconto'] = preco_promo
    dados['preco_original'] = preco_original if preco_original > 0 else None

    atualizar_item_banco(db_id, dados, link, texto_adicional)

    posicao = obter_posicao_por_id(db_id)
    p_promo_str = f"R$ {preco_promo:.2f}".replace('.', ',')
    
    if preco_original > preco_promo and preco_original > 0:
        p_orig_str = f"R$ {preco_original:.2f}".replace('.', ',')
        desconto_perc = round(((preco_original - preco_promo) / preco_original) * 100)
        str_desc = f" ({desconto_perc}% OFF)"
    else:
        p_orig_str = "Não definido"
        str_desc = ""

    msg_confirmacao = (
        f"✅ <b>Preços Atualizados no Item #{posicao}!</b>\n\n"
        f"🛍️ <b>{html.escape(dados.get('titulo', 'Produto'))}</b>\n"
        f"❌ <b>De:</b> {p_orig_str}\n"
        f"🟢 <b>Por:</b> {p_promo_str}{str_desc}\n\n"
        f"💡 <i>Use <code>/prever {posicao}</code> para conferir a postagem!</i>"
    )

    await update.message.reply_text(msg_confirmacao, parse_mode='HTML')

async def iniciar_personalizar_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return ConversationHandler.END

    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Use o comando informando a posição do item na fila.\n"
            "👉 Exemplo interativo: <code>/personalizar 1</code>\n"
            "👉 Exemplo direto: <code>/personalizar 1 2149 3900</code>",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    try:
        posicao = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Posição inválida. Use um número inteiro.", parse_mode='HTML')
        return ConversationHandler.END

    item = obter_item_por_posicao(posicao)
    if not item:
        await update.message.reply_text(f"❌ Nenhum item encontrado na {posicao}ª posição da fila.", parse_mode='HTML')
        return ConversationHandler.END

    context.user_data['personalizar_db_id'] = item['db_id']

    if len(args) >= 3:
        try:
            val1 = float(args[1].replace('.', '').replace(',', '.'))
            val2 = float(args[2].replace('.', '').replace(',', '.'))
            await aplicar_alteracao_personalizar(update, item, val1, val2)
            context.user_data.clear()
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text("❌ Os valores informados são inválidos. Digite apenas números.", parse_mode='HTML')
            return ConversationHandler.END
    
    elif len(args) == 2:
        try:
            val1 = float(args[1].replace('.', '').replace(',', '.'))
            preco_orig_atual = item['dados'].get('preco_original') or 0.0
            await aplicar_alteracao_personalizar(update, item, val1, preco_orig_atual)
            context.user_data.clear()
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text("❌ Valor informado inválido.", parse_mode='HTML')
            return ConversationHandler.END

    titulo = html.escape(item['dados'].get('titulo', 'Produto'))
    await update.message.reply_text(
        f"✏️ <b>Personalizando Preços do Item #{posicao}</b>\n"
        f"🛍️ <i>{titulo}</i>\n\n"
        f"Digite o <b>Preço com Desconto</b> e o <b>Preço Original</b> separados por espaço:\n"
        f"👉 Exemplo: <code>2149 3900</code> ou apenas <code>2149</code>",
        parse_mode='HTML'
    )
    return PERSONALIZAR_PRECOS_PASSO

async def receber_precos_personalizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return ConversationHandler.END

    texto = update.message.text.strip().replace(',', '.')
    partes = texto.split()

    if not partes:
        await update.message.reply_text("❌ Nenhum valor identificado. Digite os números (Ex: <code>2149 3900</code>):", parse_mode='HTML')
        return PERSONALIZAR_PRECOS_PASSO

    try:
        val_promo = float(partes[0])
        val_orig = float(partes[1]) if len(partes) >= 2 else 0.0

        db_id = context.user_data.get('personalizar_db_id')
        if not db_id:
            await update.message.reply_text("❌ Sessão expirada. Execute <code>/personalizar [posição]</code> novamente.", parse_mode='HTML')
            context.user_data.clear()
            return ConversationHandler.END

        conn = sqlite3.connect(DB_PROMOS_PATH, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('SELECT id, dados_json, link, texto_adicional, origem, file_id_foto FROM fila_postagens WHERE status = ? AND id = ?', ('pendente', db_id))
        row = cursor.fetchone()
        conn.close()

        if not row:
            await update.message.reply_text("❌ Item não encontrado na fila.", parse_mode='HTML')
            context.user_data.clear()
            return ConversationHandler.END

        item = {
            'db_id': row[0],
            'dados': json.loads(row[1]),
            'link': row[2],
            'texto_adicional': row[3],
            'origem': row[4],
            'file_id_foto': row[5]
        }

        await aplicar_alteracao_personalizar(update, item, val_promo, val_orig)
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ Formato inválido. Envie apenas números separados por espaço (Ex: <code>2149 3900</code>):", parse_mode='HTML')
        return PERSONALIZAR_PRECOS_PASSO

async def resumo_dia_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    total_fila = contar_fila_atual()
    total_enviados_hoje = contar_historico_hoje()
    status_bot = "⏸️ Pausado" if BOT_PAUSADO else "▶️ Ativo"
    
    resumo_texto = (
        f"📈 <b>RESUMO OPERACIONAL DO DIA</b>\n\n"
        f"⚙️ Status dos disparos: <b>{status_bot}</b>\n"
        f"✅ Publicados hoje: <b>{total_enviados_hoje}</b>\n"
        f"📦 Na fila atualmente: <b>{total_fila}</b>\n"
        f"⏰ Intervalo: <b>{INTERVALO_POSTAGEM_MINUTOS} minutos</b>\n\n"
        f"💡 <i>Dica: Para dados detalhados use <code>/relatorio</code></i>"
    )
    await update.message.reply_text(resumo_texto, parse_mode='HTML')

async def destravar_fila_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    
    global ULTIMO_ENVIO_TIMESTAMP
    ULTIMO_ENVIO_TIMESTAMP = datetime.datetime.min
    salvar_ultimo_timestamp(ULTIMO_ENVIO_TIMESTAMP)
    
    await processador_fila_background(context)
    await update.message.reply_text("🚀 Fila destravada! Verificando se há itens para enviar...", parse_mode='HTML')

async def prever_item_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Use o formato correto: <code>/prever 1</code>", parse_mode='HTML')
        return
    try:
        posicao = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Número de posição inválido.")
        return
        
    item = obter_item_por_posicao(posicao)
    if not item:
        await update.message.reply_text(f"❌ Não foi encontrado nenhum item na {posicao}ª posição da fila.")
        return
        
    dados = item['dados']
    link = item['link']
    texto_adicional = item['texto_adicional']
    origem = item['origem']
    file_id_foto = item['file_id_foto']
    
    mensagem_preview = montar_layout_mensagem(dados, link, texto_adicional, origem)
    
    await update.message.reply_text(
        f"🔍 <b>PRÉVIA DA {posicao}ª POSIÇÃO DA FILA:</b>\n"
        f"----------------------------------------",
        parse_mode='HTML'
    )
    
    try:
        if file_id_foto:
            await update.message.reply_photo(photo=file_id_foto, caption=mensagem_preview, parse_mode='HTML')
            return
    except Exception as e:
        logger.error(f"Erro ao enviar foto na prévia: {e}")
        
    await update.message.reply_text(text=mensagem_preview, parse_mode='HTML')

async def listar_comandos_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return
    
    texto_ajuda = (
        "📖 <b>GUIA DIDÁTICO E COMPLETO DE COMANDOS</b>\n"
        "───────────────────────────────\n\n"
        "📋 <b>Gerenciamento de Fila</b>\n"
        "• <code>/fila</code> — Lista todas as postagens agendadas em ordem de envio.\n"
        "• <code>/organizar</code> — Reorganiza a fila em blocos de 3 da mesma categoria.\n"
        "• <code>/prever [posição]</code> — Exibe como a postagem vai aparecer.\n\n"
        "✏️ <b>Edição e Ajustes</b>\n"
        "• <code>/personalizar [pos] [promo] [orig]</code> — Altera os preços.\n"
        "• <code>/editar [posição]</code> — Troca o link do produto.\n"
        "• <code>/remover [posição]</code> — Apaga um produto da fila.\n"
        "• <code>/limparfila</code> — Zera totalmente a fila.\n\n"
        "📊 <b>Métricas</b>\n"
        "• <code>/relatorio</code> — Relatório completo de performance.\n"
        "• <code>/resumo</code> — Resumo express do dia.\n\n"
        "⚙️ <b>Controle</b>\n"
        "• <code>/pausar</code> / <code>/retomar</code> — Pausa ou reativa as postagens.\n"
        "• <code>/destravar</code> — Força a publicação imediata.\n"
        "• <code>/desbugar</code> — Reseta o timer para enviar agora.\n"
        "• <code>/logs</code> — Mostra os registros técnicos.\n"
        "• <code>/cancelar</code> — Cancela operações interativas.\n\n"
        f"⏰ <b>Intervalo atual:</b> {INTERVALO_POSTAGEM_MINUTOS} minutos entre posts"
    )
    await update.message.reply_text(texto_ajuda, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID or not update.message:
        return
    
    is_forwarded = bool(
        getattr(update.message, 'forward_origin', None) or 
        getattr(update.message, 'forward_date', None) or 
        getattr(update.message, 'forward_from', None) or 
        getattr(update.message, 'forward_from_chat', None)
    )
    origem = 'garimpo' if is_forwarded else 'manual'
    
    file_id_foto = None
    if update.message.photo:
        file_id_foto = update.message.photo[-1].file_id
    elif update.message.caption and hasattr(update.message, 'effective_attachment') and update.message.effective_attachment:
        if isinstance(update.message.effective_attachment, list) and len(update.message.effective_attachment) > 0:
            file_id_foto = update.message.effective_attachment[-1].file_id

    mensagem_texto = update.message.text or update.message.caption or ""
    
    links = re.findall(r'https?://[^\s]+', mensagem_texto)
    if not links:
        return
    
    link = links[0]
    texto_adicional = limpar_texto_adicional(mensagem_texto, link)
    tipo_msg = "🌐 [Garimpo]" if origem == 'garimpo' else "👤 [Manual]"
    
    try:
        dados = extrair_dados_produto(link)
        if not dados or not dados.get('titulo'):
            dados = {'titulo': 'Produto em Oferta Especial', 'preco_original': None, 'preco_desconto': None}
        
        preco_sugerido = extrair_preco_do_texto(mensagem_texto) or dados.get('preco_desconto')
        preco_orig_sugerido = extrair_preco_original_do_texto(mensagem_texto) or dados.get('preco_original')
        
        if preco_orig_sugerido and not dados.get('preco_original'):
            dados['preco_original'] = preco_orig_sugerido

        context.user_data['dados_produto'] = dados
        context.user_data['link'] = link
        context.user_data['texto_adicional'] = texto_adicional
        context.user_data['origem'] = origem
        context.user_data['file_id_foto'] = file_id_foto
        
        sugestao_str = f" (Sugerido no texto: R$ {preco_sugerido:.2f})" if preco_sugerido and preco_sugerido > 1 else ""
        sugestao_str = sugestao_str.replace('.', ',')

        await update.message.reply_text(
            f"📥 <b>Link recebido!</b> {tipo_msg}\n"
            f"🛍️ <b>{html.escape(dados.get('titulo', 'Produto'))[:45]}...</b>\n\n"
            f"💰 <b>Por favor, digite o preço promocional para salvar na fila</b>{sugestao_str}\n"
            f"👉 <i>Digite ex: <code>49.90</code> ou <code>49.90 89.90</code> (Preço Promo + Preço Original)</i>",
            parse_mode='HTML'
        )
        return AGUARDANDO_PRECO
            
    except Exception as e:
        logger.error(f"Erro handler lote: {e}")

async def receber_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dados = context.user_data.get('dados_produto')
        link = context.user_data.get('link')
        texto_adicional = context.user_data.get('texto_adicional')
        origem = context.user_data.get('origem', 'manual')
        file_id_foto = context.user_data.get('file_id_foto')
        
        if not dados or not link:
            await update.message.reply_text("❌ Erro ao identificar o link anterior. Por favor, envie o link novamente.")
            context.user_data.clear()
            return ConversationHandler.END

        texto = update.message.text.replace(',', '.').strip()
        partes = texto.split()
        
        preco_promo = float(partes[0])
        preco_orig = float(partes[1]) if len(partes) >= 2 else dados.get('preco_original')
        
        if preco_promo <= 0:
            await update.message.reply_text("❌ Valor inválido. Digite um valor numérico positivo:")
            return AGUARDANDO_PRECO
            
        dados['preco_desconto'] = preco_promo
        if preco_orig and preco_orig > preco_promo:
            dados['preco_original'] = preco_orig
        
        _, _, novo_id = adicionar_fila(dados, link, texto_adicional, origem, file_id_foto)
        posicao_real = obter_posicao_por_id(novo_id)
        horario = calcular_horario_publicacao(posicao_real)
        
        preco_str = f"R$ {preco_promo:.2f}".replace('.', ',')
        orig_str = f" (De: R$ {dados['preco_original']:.2f})".replace('.', ',') if dados.get('preco_original') else ""
        
        await update.message.reply_text(
            f"✅ <b>Item adicionado à fila com sucesso!</b>\n"
            f"📊 <b>Posição na Fila: {posicao_real}º</b> (Horário previsto: {horario})\n"
            f"💰 Preço definido: <b>{preco_str}</b>{orig_str}\n\n"
            f"💡 <i>Use <code>/prever {posicao_real}</code> para ver a prévia | <code>/personalizar {posicao_real}</code> para alterar</i>",
            parse_mode='HTML'
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Erro preço: {e}")
        await update.message.reply_text("❌ Formato inválido. Digite apenas números (Ex: <code>44.90</code> ou <code>44.90 89.90</code>):", parse_mode='HTML')
        return AGUARDANDO_PRECO

async def iniciar_cupom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_RASCUNHO_ID:
        return ConversationHandler.END
    await update.message.reply_text("🎟️ Envie o texto do cupom:", parse_mode='HTML')
    return CUPOM_TEXTO

async def receber_cupom_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cupom_texto'] = update.message.text
    await update.message.reply_text("🔗 Envie o link:")
    return CUPOM_LINK

async def receber_cupom_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cupom_link'] = update.message.text.strip()
    await update.message.reply_text("🖼️ Envie a imagem ou digite <code>pular</code>", parse_mode='HTML')
    return CUPOM_IMAGEM

async def finalizar_cupom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        texto = context.user_data.get('cupom_texto')
        link = context.user_data.get('cupom_link')
        msg = f"🎟️ <b>CUPOM EXCLUSIVO LIBERADO!</b>\n\n{texto}\n\n👉 <b>Garanta no link oficial:</b>\n{link}"
        
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            await context.bot.send_photo(chat_id=GRUPO_PROMOS_ID, photo=file_id, caption=msg, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=GRUPO_PROMOS_ID, text=msg, parse_mode='HTML')
            
        await update.message.reply_text("🚀 Cupom postado com sucesso!")
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Erro cupom: {e}")
        context.user_data.clear()
        return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operação cancelada!")
    return ConversationHandler.END

def main():
    inicializar_banco()
    application = Application.builder().token(TOKEN).build()
    
    if application.job_queue:
        application.job_queue.run_repeating(processador_fila_background, interval=30.0, first=5.0)
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('comandos', listar_comandos_comando),
            CommandHandler('ajuda', listar_comandos_comando),
            CommandHandler('cupom', iniciar_cupom),
            CommandHandler('fila', ver_fila_comando),
            CommandHandler('organizar', organizar_comando),
            CommandHandler('relatorio', relatorio_completo_comando),
            CommandHandler('relatorio_completo', relatorio_completo_comando),
            CommandHandler('refresh', refresh_fila_comando),
            CommandHandler('atualizar', refresh_fila_comando),
            CommandHandler('remover', remover_item_comando),
            CommandHandler('limparfila', limpar_fila_comando),
            CommandHandler('resumo', resumo_dia_comando),
            CommandHandler('destravar', destravar_fila_comando),
            CommandHandler('desbugar', desbugar_fila_comando),
            CommandHandler('logs', ver_logs_comando),
            CommandHandler('editar', iniciar_edicao_comando),
            CommandHandler('personalizar', iniciar_personalizar_comando),
            CommandHandler('pausar', pausar_bot_comando),
            CommandHandler('retomar', retomar_bot_comando),
            CommandHandler('prever', prever_item_comando),
            MessageHandler(filters.TEXT | filters.PHOTO | filters.CAPTION, handle_message)
        ],
        states={
            AGUARDANDO_PRECO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_preco)],
            CUPOM_TEXTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_cupom_texto)],
            CUPOM_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_cupom_link)],
            CUPOM_IMAGEM: [MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), finalizar_cupom)],
            EDITAR_ITEM_PASSO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_novo_link_edicao)],
            PERSONALIZAR_PRECOS_PASSO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_precos_personalizar)]
        },
        fallbacks=[CommandHandler('cancelar', cancelar)],
        per_chat=True, per_user=True, per_message=False
    )
    
    application.add_handler(conv_handler)
    
    print("=" * 60)
    print("🚀 BOT RODANDO COM SUCESSO!")
    print(f"⏰ Intervalo entre postagens: {INTERVALO_POSTAGEM_MINUTOS} minutos")
    print(f"🕐 Último envio registrado: {ULTIMO_ENVIO_TIMESTAMP}")
    print("📊 Dashboard de métricas: https://promos-tracking.onrender.com")
    print("=" * 60)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
