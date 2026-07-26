# tracking_server.py - Servidor de rastreamento de cliques com interface profissional
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
URL_BASE = 'https://promos-tracking.onrender.com'

# ====== TEMPLATE HTML PROFISSIONAL E MODERNO ======
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Promos do Negão - Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0a0e1a;
            color: #e4e9f2;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        /* HEADER */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 30px;
            background: linear-gradient(135deg, #141b2d 0%, #1a2335 100%);
            border-radius: 20px;
            border: 1px solid rgba(255, 215, 0, 0.15);
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .header-left .logo {
            font-size: 2.5em;
        }
        
        .header-left h1 {
            font-size: 1.8em;
            background: linear-gradient(45deg, #f7971e, #ffd200);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header-left .subtitle {
            color: #8899bb;
            font-size: 0.9em;
            -webkit-text-fill-color: #8899bb;
        }
        
        .header-right {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(0, 200, 80, 0.15);
            padding: 8px 18px;
            border-radius: 30px;
            border: 1px solid rgba(0, 200, 80, 0.3);
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00e676;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        .header-right .time {
            color: #667799;
            font-size: 0.9em;
        }
        
        /* GRID DE MÉTRICAS */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: linear-gradient(145deg, #141b2d, #1a2335);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #f7971e, #ffd200);
            opacity: 0.6;
        }
        
        .metric-card:hover {
            transform: translateY(-4px);
            border-color: rgba(255, 215, 0, 0.2);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
        }
        
        .metric-card .icon {
            font-size: 2em;
            margin-bottom: 8px;
        }
        
        .metric-card .label {
            color: #8899bb;
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }
        
        .metric-card .value {
            font-size: 2.4em;
            font-weight: 700;
            margin: 6px 0;
            line-height: 1.2;
        }
        
        .metric-card .value.gold { color: #ffd700; }
        .metric-card .value.green { color: #00e676; }
        .metric-card .value.blue { color: #40c4ff; }
        .metric-card .value.pink { color: #ff6b9d; }
        .metric-card .value.purple { color: #b388ff; }
        .metric-card .value.orange { color: #ffab40; }
        
        .metric-card .sub {
            color: #667799;
            font-size: 0.85em;
        }
        
        .metric-card .trend {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
            margin-top: 4px;
        }
        
        .trend.up { background: rgba(0, 230, 118, 0.15); color: #00e676; }
        .trend.down { background: rgba(255, 82, 82, 0.15); color: #ff5252; }
        .trend.neutral { background: rgba(255, 215, 0, 0.15); color: #ffd700; }
        
        /* SEÇÃO DE GRÁFICOS */
        .charts-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        
        .chart-card {
            background: linear-gradient(145deg, #141b2d, #1a2335);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }
        
        .chart-card .chart-title {
            font-size: 1.1em;
            font-weight: 600;
            margin-bottom: 20px;
            color: #e4e9f2;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .chart-card .chart-title .badge-count {
            background: rgba(255, 215, 0, 0.15);
            padding: 2px 12px;
            border-radius: 20px;
            font-size: 0.7em;
            color: #ffd700;
        }
        
        .bar-chart {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .bar-item {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .bar-item .bar-label {
            min-width: 100px;
            font-size: 0.85em;
            color: #b0bdd4;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .bar-item .bar-label .emoji {
            margin-right: 6px;
        }
        
        .bar-item .bar-track {
            flex: 1;
            height: 24px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            overflow: hidden;
            position: relative;
        }
        
        .bar-item .bar-fill {
            height: 100%;
            border-radius: 12px;
            background: linear-gradient(90deg, #f7971e, #ffd200);
            transition: width 1s ease;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 10px;
            font-size: 0.7em;
            font-weight: 600;
            color: #0a0e1a;
            min-width: 30px;
        }
        
        .bar-item .bar-fill.blue { background: linear-gradient(90deg, #1a73e8, #40c4ff); }
        .bar-item .bar-fill.green { background: linear-gradient(90deg, #00c853, #00e676); }
        .bar-item .bar-fill.pink { background: linear-gradient(90deg, #e91e63, #ff6b9d); }
        .bar-item .bar-fill.purple { background: linear-gradient(90deg, #7c4dff, #b388ff); }
        .bar-item .bar-fill.orange { background: linear-gradient(90deg, #ff6f00, #ffab40); }
        .bar-item .bar-fill.red { background: linear-gradient(90deg, #c62828, #ff5252); }
        .bar-item .bar-fill.teal { background: linear-gradient(90deg, #00695c, #1de9b6); }
        
        .bar-item .bar-value {
            min-width: 50px;
            text-align: right;
            font-weight: 600;
            font-size: 0.9em;
            color: #e4e9f2;
        }
        
        /* TABELA DE PRODUTOS */
        .table-container {
            background: linear-gradient(145deg, #141b2d, #1a2335);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            margin-bottom: 30px;
            overflow-x: auto;
        }
        
        .table-container .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .table-container .table-header h2 {
            font-size: 1.1em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .table-container .table-header .filter {
            display: flex;
            gap: 10px;
        }
        
        .table-container .table-header .filter select {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #e4e9f2;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 0.85em;
            cursor: pointer;
        }
        
        .table-container .table-header .filter select:focus {
            outline: none;
            border-color: #ffd700;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        th {
            color: #8899bb;
            text-transform: uppercase;
            font-size: 0.7em;
            letter-spacing: 0.5px;
            font-weight: 600;
        }
        
        td {
            color: #dde4f0;
            font-size: 0.9em;
        }
        
        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }
        
        .badge {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .badge.shopee { background: rgba(238, 77, 45, 0.2); color: #ee4d2d; }
        .badge.mercadolivre { background: rgba(255, 230, 0, 0.15); color: #ffd700; }
        .badge.amazon { background: rgba(255, 153, 0, 0.2); color: #ff9900; }
        .badge.kabum { background: rgba(226, 0, 20, 0.2); color: #ff5252; }
        .badge.magalu { background: rgba(255, 0, 85, 0.2); color: #ff6b9d; }
        .badge.aliexpress { background: rgba(255, 68, 0, 0.2); color: #ff6d00; }
        .badge.geral { background: rgba(102, 119, 153, 0.2); color: #8899bb; }
        
        .rank-number {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            font-weight: 700;
            font-size: 0.8em;
        }
        
        .rank-1 { background: rgba(255, 215, 0, 0.2); color: #ffd700; }
        .rank-2 { background: rgba(192, 192, 192, 0.15); color: #c0c0c0; }
        .rank-3 { background: rgba(205, 127, 50, 0.15); color: #cd7f32; }
        .rank-other { background: rgba(255, 255, 255, 0.05); color: #667799; }
        
        /* FOOTER */
        .footer {
            text-align: center;
            padding: 30px 20px;
            color: #667799;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            margin-top: 20px;
        }
        
        .footer a {
            color: #ffd700;
            text-decoration: none;
            transition: color 0.3s;
        }
        
        .footer a:hover {
            color: #fff;
            text-decoration: underline;
        }
        
        .footer .footer-links {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 10px;
            flex-wrap: wrap;
        }
        
        .footer .footer-links a {
            color: #667799;
            font-size: 0.85em;
        }
        
        .footer .footer-links a:hover {
            color: #ffd700;
        }
        
        /* RESPONSIVO */
        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                text-align: center;
                padding: 20px;
            }
            
            .header-left {
                flex-direction: column;
            }
            
            .charts-row {
                grid-template-columns: 1fr;
            }
            
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .bar-item .bar-label {
                min-width: 70px;
                font-size: 0.75em;
            }
            
            .table-container .table-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .metric-card .value {
                font-size: 1.8em;
            }
        }
        
        @media (max-width: 480px) {
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            
            .header-left h1 {
                font-size: 1.3em;
            }
        }
        
        /* ANIMAÇÕES */
        .fade-in {
            animation: fadeIn 0.6s ease forwards;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .delay-1 { animation-delay: 0.1s; opacity: 0; }
        .delay-2 { animation-delay: 0.2s; opacity: 0; }
        .delay-3 { animation-delay: 0.3s; opacity: 0; }
        .delay-4 { animation-delay: 0.4s; opacity: 0; }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        
        ::-webkit-scrollbar-track {
            background: #0a0e1a;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #2a3350;
            border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #3a4a6a;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <header class="header fade-in">
            <div class="header-left">
                <span class="logo">🚀</span>
                <div>
                    <h1>Promos do Negão</h1>
                    <span class="subtitle">📊 Sistema de Rastreamento de Cliques</span>
                </div>
            </div>
            <div class="header-right">
                <div class="status-badge">
                    <span class="status-dot"></span>
                    <span style="color: #00e676; font-weight: 500;">Online</span>
                </div>
                <span class="time">🕐 {{ agora }}</span>
            </div>
        </header>

        <!-- MÉTRICAS PRINCIPAIS -->
        <div class="metrics-grid">
            <div class="metric-card fade-in delay-1">
                <div class="icon">🖱️</div>
                <div class="label">Total de Cliques</div>
                <div class="value gold">{{ total_cliques }}</div>
                <div class="sub">Última atualização: {{ agora }}</div>
            </div>
            
            <div class="metric-card fade-in delay-2">
                <div class="icon">📊</div>
                <div class="label">Cliques Hoje</div>
                <div class="value green">{{ cliques_hoje }}</div>
                <div class="sub">Média de desconto: <b>{{ media_desconto }}%</b></div>
            </div>
            
            <div class="metric-card fade-in delay-3">
                <div class="icon">🏆</div>
                <div class="label">Produto Mais Clicado</div>
                <div class="value blue">{{ produto_top or 'Nenhum ainda' }}</div>
                <div class="sub">{{ produto_cliques or '' }}</div>
            </div>
            
            <div class="metric-card fade-in delay-4">
                <div class="icon">⏰</div>
                <div class="label">Horário de Pico</div>
                <div class="value pink">{{ hora_pico or '--:--' }}</div>
                <div class="sub">{{ hora_pico_qtd or '' }}</div>
            </div>
        </div>

        <!-- GRÁFICOS -->
        <div class="charts-row">
            <!-- Gráfico por Plataforma -->
            <div class="chart-card fade-in">
                <div class="chart-title">
                    🛒 Cliques por Plataforma
                    <span class="badge-count">{{ cliques_plataforma|length }}</span>
                </div>
                <div class="bar-chart">
                    {% for plat in cliques_plataforma %}
                    <div class="bar-item">
                        <span class="bar-label">
                            <span class="emoji">
                                {% if plat[0].lower() == 'shopee' %}🛍️
                                {% elif plat[0].lower() == 'mercadolivre' %}📦
                                {% elif plat[0].lower() == 'amazon' %}📚
                                {% elif plat[0].lower() == 'kabum' %}💻
                                {% elif plat[0].lower() == 'magalu' %}🏪
                                {% elif plat[0].lower() == 'aliexpress' %}🌐
                                {% else %}🔗{% endif %}
                            </span>
                            {{ plat[0].upper() }}
                        </span>
                        <div class="bar-track">
                            <div class="bar-fill {% if plat[0].lower() == 'shopee' %}orange{% elif plat[0].lower() == 'mercadolivre' %}gold{% elif plat[0].lower() == 'amazon' %}blue{% elif plat[0].lower() == 'kabum' %}red{% elif plat[0].lower() == 'magalu' %}pink{% elif plat[0].lower() == 'aliexpress' %}purple{% else %}teal{% endif %}" 
                                 style="width: {{ plat[1] / max_cliques_plat * 100 if max_cliques_plat > 0 else 0 }}%;">
                                {{ plat[1] }}
                            </div>
                        </div>
                        <span class="bar-value">{{ "%.1f"|format(plat[1] / total_cliques * 100 if total_cliques > 0 else 0) }}%</span>
                    </div>
                    {% else %}
                    <div style="text-align: center; color: #667799; padding: 30px 0;">Nenhum clique registrado ainda</div>
                    {% endfor %}
                </div>
            </div>

            <!-- Gráfico por Categoria -->
            <div class="chart-card fade-in">
                <div class="chart-title">
                    🏷️ Cliques por Categoria
                    <span class="badge-count">{{ cliques_categoria|length }}</span>
                </div>
                <div class="bar-chart">
                    {% for cat in cliques_categoria %}
                    <div class="bar-item">
                        <span class="bar-label">
                            <span class="emoji">
                                {% if cat[0].lower() == 'eletronicos' %}📱
                                {% elif cat[0].lower() == 'moda' %}👕
                                {% elif cat[0].lower() == 'casa' %}🏠
                                {% elif cat[0].lower() == 'beleza' %}💄
                                {% elif cat[0].lower() == 'alimentos' %}🍕
                                {% elif cat[0].lower() == 'brinquedos' %}🎮
                                {% elif cat[0].lower() == 'esporte' %}⚽
                                {% elif cat[0].lower() == 'livros' %}📚
                                {% elif cat[0].lower() == 'utilidades' %}🔧
                                {% else %}📌{% endif %}
                            </span>
                            {{ cat[0].upper() }}
                        </span>
                        <div class="bar-track">
                            <div class="bar-fill 
                                {% if loop.index == 1 %}gold
                                {% elif loop.index == 2 %}blue
                                {% elif loop.index == 3 %}green
                                {% elif loop.index == 4 %}pink
                                {% elif loop.index == 5 %}purple
                                {% else %}teal{% endif %}" 
                                 style="width: {{ cat[1] / max_cliques_cat * 100 if max_cliques_cat > 0 else 0 }}%;">
                                {{ cat[1] }}
                            </div>
                        </div>
                        <span class="bar-value">{{ cat[1] }}</span>
                    </div>
                    {% else %}
                    <div style="text-align: center; color: #667799; padding: 30px 0;">Nenhuma categoria registrada</div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- TOP PRODUTOS -->
        <div class="table-container fade-in">
            <div class="table-header">
                <h2>🏆 Top 10 Produtos Mais Clicados</h2>
                <div class="filter">
                    <span style="color: #667799; font-size: 0.85em;">Ordenado por cliques</span>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Produto</th>
                        <th>Plataforma</th>
                        <th>Categoria</th>
                        <th>Cliques</th>
                        <th>Desconto</th>
                    </tr>
                </thead>
                <tbody>
                    {% for prod in top_produtos %}
                    <tr>
                        <td>
                            <span class="rank-number 
                                {% if loop.index == 1 %}rank-1
                                {% elif loop.index == 2 %}rank-2
                                {% elif loop.index == 3 %}rank-3
                                {% else %}rank-other{% endif %}">
                                {{ loop.index }}
                            </span>
                        </td>
                        <td style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            {{ prod[0][:40] }}{% if prod[0]|length > 40 %}...{% endif %}
                        </td>
                        <td><span class="badge {{ prod[1].lower() }}">{{ prod[1].upper() }}</span></td>
                        <td><span style="color: #8899bb;">{{ prod[2] or 'N/A' }}</span></td>
                        <td><strong>{{ prod[3] }}</strong></td>
                        <td>
                            {% if prod[4] and prod[4] > 0 %}
                            <span style="color: #00e676;">{{ prod[4] }}% OFF</span>
                            {% else %}
                            <span style="color: #667799;">-</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="6" style="text-align: center; color: #667799; padding: 30px 0;">
                            📭 Nenhum produto clicado ainda. Compartilhe os links!
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- HORÁRIOS -->
        <div class="charts-row">
            <div class="chart-card fade-in">
                <div class="chart-title">
                    📈 Top 5 Horários com Mais Cliques
                    <span class="badge-count">Pico</span>
                </div>
                <div class="bar-chart">
                    {% for hora in top_horarios %}
                    <div class="bar-item">
                        <span class="bar-label">
                            <span class="emoji">
                                {% if loop.index == 1 %}🥇
                                {% elif loop.index == 2 %}🥈
                                {% elif loop.index == 3 %}🥉
                                {% else %}⏰{% endif %}
                            </span>
                            {{ hora[0] }}:00
                        </span>
                        <div class="bar-track">
                            <div class="bar-fill {% if loop.index == 1 %}gold{% elif loop.index == 2 %}blue{% else %}green{% endif %}" 
                                 style="width: {{ hora[1] / top_horarios[0][1] * 100 if top_horarios else 0 }}%;">
                                {{ hora[1] }}
                            </div>
                        </div>
                        <span class="bar-value">{{ hora[1] }}</span>
                    </div>
                    {% else %}
                    <div style="text-align: center; color: #667799; padding: 30px 0;">Nenhum dado de horário disponível</div>
                    {% endfor %}
                </div>
            </div>

            <!-- Dias da Semana -->
            <div class="chart-card fade-in">
                <div class="chart-title">
                    📅 Cliques por Dia da Semana
                    <span class="badge-count">Semanal</span>
                </div>
                <div class="bar-chart">
                    {% for dia in cliques_por_dia %}
                    <div class="bar-item">
                        <span class="bar-label">
                            <span class="emoji">
                                {% if loop.index == 0 %}🌙
                                {% elif loop.index == 1 %}🌙
                                {% elif loop.index == 2 %}🌙
                                {% elif loop.index == 3 %}🌙
                                {% elif loop.index == 4 %}🌙
                                {% elif loop.index == 5 %}⭐
                                {% else %}⭐{% endif %}
                            </span>
                            {{ dia[0] }}
                        </span>
                        <div class="bar-track">
                            <div class="bar-fill {% if loop.index >= 5 %}gold{% else %}blue{% endif %}" 
                                 style="width: {{ dia[1] / max_dia_cliques * 100 if max_dia_cliques > 0 else 0 }}%;">
                                {{ dia[1] }}
                            </div>
                        </div>
                        <span class="bar-value">{{ dia[1] }}</span>
                    </div>
                    {% else %}
                    <div style="text-align: center; color: #667799; padding: 30px 0;">Nenhum dado disponível</div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- FOOTER -->
        <footer class="footer">
            <p>🚀 <strong>Promos do Negão</strong> © 2026 • Sistema de Rastreamento de Cliques</p>
            <div class="footer-links">
                <a href="/">🔄 Recarregar</a>
                <a href="/api/estatisticas">📊 API JSON</a>
                <a href="#" onclick="window.scrollTo({top:0,behavior:'smooth'});">⬆️ Voltar ao topo</a>
            </div>
            <p style="margin-top: 10px; font-size: 0.75em; color: #445566;">
                Última atualização: {{ agora }}
            </p>
        </footer>
    </div>

    <script>
        // Animar barras ao carregar
        document.addEventListener('DOMContentLoaded', function() {
            const fills = document.querySelectorAll('.bar-fill');
            fills.forEach((fill, index) => {
                const width = fill.style.width;
                fill.style.width = '0%';
                setTimeout(() => {
                    fill.style.width = width;
                }, 100 + index * 50);
            });
        });
    </script>
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
    """Página inicial com dashboard profissional"""
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
    max_cliques_plat = cliques_plataforma[0][1] if cliques_plataforma else 1
    
    # Cliques por categoria
    cursor.execute('''
        SELECT categoria, COUNT(*) as total
        FROM cliques_tracking t
        JOIN cliques_registrados r ON t.short_code = r.short_code
        GROUP BY categoria
        ORDER BY total DESC
        LIMIT 10
    ''')
    cliques_categoria = cursor.fetchall()
    max_cliques_cat = cliques_categoria[0][1] if cliques_categoria else 1
    
    # Top produtos
    cursor.execute('''
        SELECT t.titulo_produto, t.plataforma, t.categoria, COUNT(*) as total, t.desconto_percentual
        FROM cliques_tracking t
        JOIN cliques_registrados r ON t.short_code = r.short_code
        GROUP BY t.titulo_produto
        ORDER BY total DESC
        LIMIT 10
    ''')
    top_produtos = cursor.fetchall()
    
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
    top_horarios = cursor.fetchall()
    
    # Cliques por dia da semana
    dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    cursor.execute('''
        SELECT dia_semana, COUNT(*) as total
        FROM cliques_registrados
        GROUP BY dia_semana
        ORDER BY dia_semana
    ''')
    cliques_dia_raw = cursor.fetchall()
    
    cliques_por_dia = []
    for i, dia in enumerate(dias_semana):
        encontrado = False
        for dia_raw, total in cliques_dia_raw:
            if dia_raw == i:
                cliques_por_dia.append((dia, total))
                encontrado = True
                break
        if not encontrado:
            cliques_por_dia.append((dia, 0))
    
    max_dia_cliques = max([c[1] for c in cliques_por_dia]) if cliques_por_dia else 1
    
    conn.close()
    
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    
    return render_template_string(
        HTML_TEMPLATE,
        total_cliques=total_cliques,
        cliques_hoje=cliques_hoje,
        media_desconto=media_desconto,
        cliques_plataforma=cliques_plataforma,
        max_cliques_plat=max_cliques_plat,
        cliques_categoria=cliques_categoria,
        max_cliques_cat=max_cliques_cat,
        top_produtos=top_produtos,
        produto_top=produto_top[0][:30] + "..." if produto_top and len(produto_top[0]) > 30 else (produto_top[0] if produto_top else None),
        produto_cliques=f"{produto_top[1]} cliques" if produto_top else "",
        hora_pico=f"{hora_pico[0]:02d}:00" if hora_pico else None,
        hora_pico_qtd=f"{hora_pico[1]} cliques" if hora_pico else "",
        top_horarios=top_horarios,
        cliques_por_dia=cliques_por_dia,
        max_dia_cliques=max_dia_cliques,
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
    print("⚠️  ATENÇÃO: Para PRODUÇÃO, use o Render!")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)
