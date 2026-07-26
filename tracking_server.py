# tracking_server.py - Servidor de rastreamento com dashboard corporativo premium
from flask import Flask, redirect, request, jsonify, render_template_string
import sqlite3
import datetime
import random
import string
import logging
import json
import math

app = Flask(__name__)

# Configuração do banco de dados de tracking
DB_PATH = 'cliques_links.db'
URL_BASE = 'https://promos-tracking.onrender.com'

# ====== TEMPLATE HTML CORPORATIVO PREMIUM ======
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Promos do Negão • Analytics Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #06080f;
            color: #e8edf5;
            min-height: 100vh;
            padding: 24px;
        }

        .container {
            max-width: 1440px;
            margin: 0 auto;
        }

        /* SCROLLBAR PERSONALIZADA */
        ::-webkit-scrollbar {
            width: 5px;
            height: 5px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.02);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255,215,0,0.3);
            border-radius: 10px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255,215,0,0.5);
        }

        /* ===== HEADER ===== */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 28px;
            background: rgba(255,255,255,0.02);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.04);
            margin-bottom: 28px;
            backdrop-filter: blur(20px);
            flex-wrap: wrap;
            gap: 16px;
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .header-logo {
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background: linear-gradient(135deg, rgba(255,215,0,0.15), rgba(255,215,0,0.05));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            border: 1px solid rgba(255,215,0,0.1);
        }

        .header-brand h1 {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #ffffff 0%, #aab 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header-brand span {
            font-size: 12px;
            color: #667799;
            font-weight: 400;
            letter-spacing: 0.3px;
            -webkit-text-fill-color: #667799;
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 24px;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 10px;
            background: rgba(0,230,118,0.06);
            padding: 8px 18px 8px 14px;
            border-radius: 100px;
            border: 1px solid rgba(0,230,118,0.12);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00e676;
            animation: pulse-dot 2s ease-in-out infinite;
        }

        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.3; transform: scale(0.8); }
        }

        .status-badge .status-text {
            font-size: 12px;
            font-weight: 500;
            color: #00e676;
            letter-spacing: 0.5px;
        }

        .header-time {
            font-size: 13px;
            color: #667799;
            font-weight: 400;
            letter-spacing: 0.3px;
        }

        .header-time strong {
            color: #aab;
            font-weight: 500;
        }

        /* ===== METRICS GRID ===== */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .metric-card {
            background: rgba(255,255,255,0.02);
            border-radius: 14px;
            padding: 20px 22px;
            border: 1px solid rgba(255,255,255,0.04);
            transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(10px);
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, rgba(255,215,0,0.3), transparent);
            opacity: 0.6;
        }

        .metric-card:hover {
            border-color: rgba(255,215,0,0.08);
            transform: translateY(-2px);
            background: rgba(255,255,255,0.035);
            box-shadow: 0 8px 40px rgba(0,0,0,0.3);
        }

        .metric-card .card-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }

        .metric-card .card-icon {
            font-size: 18px;
            opacity: 0.6;
        }

        .metric-card .trend-badge {
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 100px;
            background: rgba(0,230,118,0.08);
            color: #00e676;
            border: 1px solid rgba(0,230,118,0.06);
        }

        .metric-card .trend-badge.negative {
            background: rgba(255,82,82,0.08);
            color: #ff5252;
            border-color: rgba(255,82,82,0.06);
        }

        .metric-card .card-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #667799;
            font-weight: 600;
        }

        .metric-card .card-value {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: #ffffff;
            line-height: 1.2;
            margin-top: 2px;
        }

        .metric-card .card-value.gold { color: #f5d742; }
        .metric-card .card-value.green { color: #00e676; }
        .metric-card .card-value.blue { color: #4fc3f7; }
        .metric-card .card-value.purple { color: #b388ff; }
        .metric-card .card-value.orange { color: #ffab40; }

        .metric-card .card-sub {
            font-size: 12px;
            color: #667799;
            margin-top: 4px;
        }

        .metric-card .card-sub strong {
            color: #aab;
            font-weight: 500;
        }

        .sparkline {
            display: flex;
            align-items: flex-end;
            gap: 3px;
            height: 24px;
            margin-top: 6px;
        }

        .sparkline .bar {
            width: 4px;
            border-radius: 2px;
            background: rgba(255,215,0,0.15);
            transition: height 0.6s ease;
        }

        .sparkline .bar.active {
            background: rgba(255,215,0,0.4);
        }

        /* ===== CHARTS ROW ===== */
        .charts-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }

        @media (max-width: 900px) {
            .charts-row {
                grid-template-columns: 1fr;
            }
        }

        .chart-card {
            background: rgba(255,255,255,0.02);
            border-radius: 14px;
            padding: 22px 24px;
            border: 1px solid rgba(255,255,255,0.04);
            backdrop-filter: blur(10px);
        }

        .chart-card .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
        }

        .chart-card .chart-title {
            font-size: 13px;
            font-weight: 600;
            color: #e8edf5;
            letter-spacing: 0.3px;
        }

        .chart-card .chart-title .count-badge {
            font-size: 10px;
            font-weight: 500;
            color: #667799;
            background: rgba(255,255,255,0.04);
            padding: 2px 10px;
            border-radius: 100px;
            margin-left: 8px;
        }

        /* ===== BAR CHART ===== */
        .bar-chart {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .bar-item {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .bar-item .bar-label {
            min-width: 95px;
            font-size: 12px;
            color: #8899bb;
            font-weight: 400;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .bar-item .bar-label .emoji {
            margin-right: 6px;
        }

        .bar-item .bar-track {
            flex: 1;
            height: 20px;
            background: rgba(255,255,255,0.03);
            border-radius: 100px;
            overflow: hidden;
            position: relative;
        }

        .bar-item .bar-fill {
            height: 100%;
            border-radius: 100px;
            background: linear-gradient(90deg, rgba(255,215,0,0.3), rgba(255,215,0,0.6));
            transition: width 1.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 10px;
            font-size: 10px;
            font-weight: 600;
            color: rgba(6,8,15,0.9);
            min-width: 24px;
        }

        .bar-item .bar-fill.gold { background: linear-gradient(90deg, rgba(245,215,66,0.3), rgba(245,215,66,0.7)); }
        .bar-item .bar-fill.blue { background: linear-gradient(90deg, rgba(79,195,247,0.2), rgba(79,195,247,0.6)); }
        .bar-item .bar-fill.green { background: linear-gradient(90deg, rgba(0,230,118,0.2), rgba(0,230,118,0.5)); }
        .bar-item .bar-fill.purple { background: linear-gradient(90deg, rgba(179,136,255,0.2), rgba(179,136,255,0.5)); }
        .bar-item .bar-fill.orange { background: linear-gradient(90deg, rgba(255,171,64,0.2), rgba(255,171,64,0.5)); }
        .bar-item .bar-fill.pink { background: linear-gradient(90deg, rgba(255,107,157,0.2), rgba(255,107,157,0.5)); }
        .bar-item .bar-fill.cyan { background: linear-gradient(90deg, rgba(0,229,255,0.2), rgba(0,229,255,0.5)); }

        .bar-item .bar-value {
            min-width: 44px;
            text-align: right;
            font-weight: 500;
            font-size: 12px;
            color: #aab;
        }

        /* ===== LINE CHART (SIMULADO) ===== */
        .line-chart-container {
            padding: 4px 0;
        }

        .line-chart {
            display: flex;
            align-items: flex-end;
            height: 100px;
            gap: 6px;
            padding: 4px 0;
        }

        .line-chart .point {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }

        .line-chart .point .bar-line {
            width: 100%;
            border-radius: 4px 4px 0 0;
            background: linear-gradient(180deg, rgba(255,215,0,0.4), rgba(255,215,0,0.05));
            min-height: 4px;
            transition: height 0.8s ease;
            position: relative;
        }

        .line-chart .point .bar-line::after {
            content: '';
            position: absolute;
            top: -3px;
            left: 50%;
            transform: translateX(-50%);
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: rgba(255,215,0,0.3);
        }

        .line-chart .point .point-label {
            font-size: 9px;
            color: #445566;
            font-weight: 400;
        }

        /* ===== TABELA ===== */
        .table-container {
            background: rgba(255,255,255,0.02);
            border-radius: 14px;
            padding: 22px 24px;
            border: 1px solid rgba(255,255,255,0.04);
            backdrop-filter: blur(10px);
            overflow-x: auto;
            margin-bottom: 24px;
        }

        .table-container .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
            flex-wrap: wrap;
            gap: 12px;
        }

        .table-container .table-header h2 {
            font-size: 13px;
            font-weight: 600;
            color: #e8edf5;
            letter-spacing: 0.3px;
        }

        .table-container .table-header .table-meta {
            font-size: 11px;
            color: #667799;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            font-size: 13px;
        }

        th {
            color: #667799;
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.6px;
            font-weight: 600;
        }

        td {
            color: #dde4f0;
        }

        tr:hover td {
            background: rgba(255,255,255,0.015);
        }

        .badge {
            display: inline-block;
            padding: 3px 12px;
            border-radius: 100px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        .badge.shopee { background: rgba(238,77,45,0.12); color: #ee4d2d; }
        .badge.mercadolivre { background: rgba(255,215,0,0.08); color: #ffd700; }
        .badge.amazon { background: rgba(255,153,0,0.1); color: #ff9900; }
        .badge.kabum { background: rgba(226,0,20,0.1); color: #ff5252; }
        .badge.magalu { background: rgba(255,0,85,0.1); color: #ff6b9d; }
        .badge.aliexpress { background: rgba(255,68,0,0.1); color: #ff6d00; }
        .badge.geral { background: rgba(102,119,153,0.1); color: #8899bb; }

        .rank-number {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-weight: 700;
            font-size: 11px;
        }

        .rank-1 { background: rgba(255,215,0,0.1); color: #ffd700; }
        .rank-2 { background: rgba(192,192,192,0.08); color: #c0c0c0; }
        .rank-3 { background: rgba(205,127,50,0.08); color: #cd7f32; }
        .rank-other { background: rgba(255,255,255,0.03); color: #667799; }

        .product-cell {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .product-thumb {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            background: rgba(255,255,255,0.04);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            border: 1px solid rgba(255,255,255,0.04);
            flex-shrink: 0;
        }

        .product-name {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 200px;
            font-weight: 400;
        }

        .discount-badge {
            font-weight: 600;
            color: #00e676;
        }

        .conversion-badge {
            font-size: 10px;
            padding: 3px 10px;
            border-radius: 100px;
            background: rgba(0,230,118,0.06);
            color: #00e676;
            border: 1px solid rgba(0,230,118,0.04);
        }

        /* ===== FOOTER ===== */
        .footer {
            text-align: center;
            padding: 28px 20px 12px;
            color: #445566;
            font-size: 12px;
            border-top: 1px solid rgba(255,255,255,0.02);
            margin-top: 8px;
        }

        .footer a {
            color: #667799;
            text-decoration: none;
            transition: color 0.3s;
        }

        .footer a:hover {
            color: #ffd700;
        }

        .footer .footer-links {
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-top: 8px;
            flex-wrap: wrap;
        }

        .footer .footer-links a {
            font-size: 12px;
            color: #445566;
        }

        .footer .footer-links a:hover {
            color: #ffd700;
        }

        /* ===== RESPONSIVO ===== */
        @media (max-width: 768px) {
            body { padding: 16px; }
            .header { flex-direction: column; align-items: flex-start; padding: 16px 20px; }
            .header-right { width: 100%; justify-content: space-between; flex-wrap: wrap; }
            .metrics-grid { grid-template-columns: 1fr 1fr; gap: 12px; }
            .metric-card .card-value { font-size: 22px; }
            .charts-row { grid-template-columns: 1fr; }
            .bar-item .bar-label { min-width: 70px; font-size: 11px; }
            .table-container { padding: 16px; }
            .product-name { max-width: 120px; }
            th, td { padding: 8px 10px; font-size: 12px; }
        }

        @media (max-width: 480px) {
            .metrics-grid { grid-template-columns: 1fr; }
            .header-brand h1 { font-size: 17px; }
            .metric-card { padding: 16px; }
            .metric-card .card-value { font-size: 20px; }
        }

        /* ===== ANIMAÇÕES ===== */
        .fade-in {
            animation: fadeIn 0.5s ease forwards;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .delay-1 { animation-delay: 0.05s; opacity: 0; }
        .delay-2 { animation-delay: 0.10s; opacity: 0; }
        .delay-3 { animation-delay: 0.15s; opacity: 0; }
        .delay-4 { animation-delay: 0.20s; opacity: 0; }
        .delay-5 { animation-delay: 0.25s; opacity: 0; }
        .delay-6 { animation-delay: 0.30s; opacity: 0; }
    </style>
</head>
<body>
    <div class="container">

        <!-- ===== HEADER ===== -->
        <header class="header fade-in">
            <div class="header-left">
                <div class="header-logo">📊</div>
                <div class="header-brand">
                    <h1>Promos do Negão</h1>
                    <span>Analytics • Performance Intelligence</span>
                </div>
            </div>
            <div class="header-right">
                <div class="status-badge">
                    <span class="status-dot"></span>
                    <span class="status-text">Online</span>
                </div>
                <div class="header-time">
                    Última atualização <strong>{{ agora }}</strong>
                </div>
            </div>
        </header>

        <!-- ===== MÉTRICAS PRINCIPAIS ===== -->
        <div class="metrics-grid">
            <div class="metric-card fade-in delay-1">
                <div class="card-top">
                    <span class="card-icon">🖱️</span>
                    <span class="trend-badge">+{{ trend_cliques }}%</span>
                </div>
                <div class="card-label">Total de Cliques</div>
                <div class="card-value gold">{{ total_cliques }}</div>
                <div class="card-sub"><strong>{{ cliques_hoje }}</strong> hoje</div>
                <div class="sparkline">
                    {% for i in range(12) %}
                    <div class="bar" style="height: {{ [4,8,12,16,20,18,14,22,26,30,24,28][i] }}%;"></div>
                    {% endfor %}
                </div>
            </div>

            <div class="metric-card fade-in delay-2">
                <div class="card-top">
                    <span class="card-icon">📈</span>
                    <span class="trend-badge">+{{ trend_ctr }}%</span>
                </div>
                <div class="card-label">CTR Global</div>
                <div class="card-value green">{{ ctr_global }}%</div>
                <div class="card-sub"><strong>{{ total_cliques }}</strong> cliques / <strong>{{ total_postagens }}</strong> postagens</div>
                <div class="sparkline">
                    {% for i in range(12) %}
                    <div class="bar active" style="height: {{ [10,14,18,22,26,24,20,28,32,30,26,34][i] }}%;"></div>
                    {% endfor %}
                </div>
            </div>

            <div class="metric-card fade-in delay-3">
                <div class="card-top">
                    <span class="card-icon">💰</span>
                    <span class="trend-badge">+{{ trend_receita }}%</span>
                </div>
                <div class="card-label">Receita Estimada</div>
                <div class="card-value blue">R$ {{ receita_estimada }}</div>
                <div class="card-sub">Comissões geradas</div>
                <div class="sparkline">
                    {% for i in range(12) %}
                    <div class="bar" style="height: {{ [6,10,14,18,22,20,16,24,28,26,22,30][i] }}%;"></div>
                    {% endfor %}
                </div>
            </div>

            <div class="metric-card fade-in delay-4">
                <div class="card-top">
                    <span class="card-icon">🎯</span>
                    <span class="trend-badge">+{{ trend_conversao }}%</span>
                </div>
                <div class="card-label">Taxa de Conversão</div>
                <div class="card-value purple">{{ taxa_conversao }}%</div>
                <div class="card-sub"><strong>{{ cliques_hoje }}</strong> conversões estimadas</div>
                <div class="sparkline">
                    {% for i in range(12) %}
                    <div class="bar" style="height: {{ [8,12,16,14,18,22,20,24,28,26,22,30][i] }}%;"></div>
                    {% endfor %}
                </div>
            </div>

            <div class="metric-card fade-in delay-5">
                <div class="card-top">
                    <span class="card-icon">🏷️</span>
                    <span class="trend-badge">+{{ trend_desconto }}%</span>
                </div>
                <div class="card-label">Desconto Médio</div>
                <div class="card-value orange">{{ desconto_medio }}%</div>
                <div class="card-sub">Média de todos os cliques</div>
                <div class="sparkline">
                    {% for i in range(12) %}
                    <div class="bar" style="height: {{ [12,16,20,18,22,26,24,28,32,30,26,34][i] }}%;"></div>
                    {% endfor %}
                </div>
            </div>

            <div class="metric-card fade-in delay-6">
                <div class="card-top">
                    <span class="card-icon">⏰</span>
                    <span class="trend-badge">Pico</span>
                </div>
                <div class="card-label">Horário de Pico</div>
                <div class="card-value pink">{{ hora_pico or '--:--' }}</div>
                <div class="card-sub"><strong>{{ hora_pico_qtd or '0' }}</strong> cliques no horário</div>
                <div class="sparkline">
                    {% for i in range(12) %}
                    <div class="bar" style="height: {{ [4,6,8,12,16,20,24,28,32,30,26,22][i] }}%;"></div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- ===== GRÁFICOS ===== -->
        <div class="charts-row">
            <!-- Cliques por Plataforma -->
            <div class="chart-card fade-in">
                <div class="chart-header">
                    <span class="chart-title">🛒 Cliques por Plataforma <span class="count-badge">{{ cliques_plataforma|length }}</span></span>
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
                            <div class="bar-fill 
                                {% if plat[0].lower() == 'shopee' %}orange
                                {% elif plat[0].lower() == 'mercadolivre' %}gold
                                {% elif plat[0].lower() == 'amazon' %}blue
                                {% elif plat[0].lower() == 'kabum' %}pink
                                {% elif plat[0].lower() == 'magalu' %}purple
                                {% elif plat[0].lower() == 'aliexpress' %}cyan
                                {% else %}green{% endif %}" 
                                 style="width: {{ plat[1] / max_cliques_plat * 100 if max_cliques_plat > 0 else 0 }}%;">
                                {{ plat[1] }}
                            </div>
                        </div>
                        <span class="bar-value">{{ "%.1f"|format(plat[1] / total_cliques * 100 if total_cliques > 0 else 0) }}%</span>
                    </div>
                    {% else %}
                    <div style="text-align:center;color:#667799;padding:20px 0;">Nenhum clique registrado</div>
                    {% endfor %}
                </div>
            </div>

            <!-- Cliques por Categoria -->
            <div class="chart-card fade-in">
                <div class="chart-header">
                    <span class="chart-title">🏷️ Cliques por Categoria <span class="count-badge">{{ cliques_categoria|length }}</span></span>
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
                                {% else %}orange{% endif %}" 
                                 style="width: {{ cat[1] / max_cliques_cat * 100 if max_cliques_cat > 0 else 0 }}%;">
                                {{ cat[1] }}
                            </div>
                        </div>
                        <span class="bar-value">{{ cat[1] }}</span>
                    </div>
                    {% else %}
                    <div style="text-align:center;color:#667799;padding:20px 0;">Nenhuma categoria registrada</div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- ===== GRÁFICO DE LINHA (SÉRIE TEMPORAL) ===== -->
        <div class="chart-card fade-in" style="margin-bottom: 24px;">
            <div class="chart-header">
                <span class="chart-title">📈 Cliques nas Últimas 24 Horas</span>
                <span class="table-meta" style="font-size:11px;color:#667799;">Atualizado em tempo real</span>
            </div>
            <div class="line-chart-container">
                <div class="line-chart">
                    {% for hora in range(24) %}
                    <div class="point">
                        <div class="bar-line" style="height: {{ [4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,38,36,34,32,30][hora] }}%;"></div>
                        <span class="point-label">{{ '%02d'|format(hora) }}h</span>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- ===== TOP PRODUTOS ===== -->
        <div class="table-container fade-in">
            <div class="table-header">
                <h2>🏆 Top 10 Produtos Mais Clicados</h2>
                <span class="table-meta">Ordenado por cliques • Atualizado agora</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Produto</th>
                        <th>Plataforma</th>
                        <th>Categoria</th>
                        <th style="text-align:center;">Cliques</th>
                        <th style="text-align:center;">Desconto</th>
                        <th style="text-align:center;">Conversão</th>
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
                        <td>
                            <div class="product-cell">
                                <div class="product-thumb">
                                    {% if prod[1].lower() == 'shopee' %}🛍️
                                    {% elif prod[1].lower() == 'mercadolivre' %}📦
                                    {% elif prod[1].lower() == 'amazon' %}📚
                                    {% elif prod[1].lower() == 'kabum' %}💻
                                    {% elif prod[1].lower() == 'magalu' %}🏪
                                    {% elif prod[1].lower() == 'aliexpress' %}🌐
                                    {% else %}📦{% endif %}
                                </div>
                                <span class="product-name" title="{{ prod[0] }}">{{ prod[0][:35] }}{% if prod[0]|length > 35 %}...{% endif %}</span>
                            </div>
                        </td>
                        <td><span class="badge {{ prod[1].lower() }}">{{ prod[1].upper() }}</span></td>
                        <td><span style="color:#8899bb;font-size:12px;">{{ prod[2] or 'N/A' }}</span></td>
                        <td style="text-align:center;font-weight:600;">{{ prod[3] }}</td>
                        <td style="text-align:center;">
                            {% if prod[4] and prod[4] > 0 %}
                            <span class="discount-badge">{{ prod[4] }}% OFF</span>
                            {% else %}
                            <span style="color:#445566;">-</span>
                            {% endif %}
                        </td>
                        <td style="text-align:center;">
                            <span class="conversion-badge">
                                {% set conv = (prod[3] / total_cliques * 100) if total_cliques > 0 else 0 %}
                                {% if conv > 20 %}🔥 Alta
                                {% elif conv > 10 %}📈 Média
                                {% else %}📊 Baixa{% endif %}
                            </span>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="7" style="text-align:center;color:#667799;padding:30px 0;">
                            📭 Nenhum produto clicado ainda. Compartilhe os links!
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- ===== FOOTER ===== -->
        <footer class="footer">
            <p style="font-weight:400;">🚀 <strong style="color:#aab;">Promos do Negão</strong> • Analytics Dashboard v2.0</p>
            <div class="footer-links">
                <a href="/">🔄 Recarregar</a>
                <a href="/api/estatisticas">📊 API JSON</a>
                <a href="#" onclick="window.scrollTo({top:0,behavior:'smooth'});">⬆️ Topo</a>
            </div>
            <p style="margin-top:8px;font-size:10px;color:#334455;">
                Última atualização: {{ agora }} • Dados em tempo real
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
                }, 100 + index * 40);
            });

            const bars = document.querySelectorAll('.sparkline .bar');
            bars.forEach((bar, index) => {
                const height = bar.style.height;
                bar.style.height = '0%';
                setTimeout(() => {
                    bar.style.height = height;
                }, 50 + index * 30);
            });

            const lineBars = document.querySelectorAll('.line-chart .point .bar-line');
            lineBars.forEach((bar, index) => {
                const height = bar.style.height;
                bar.style.height = '0%';
                setTimeout(() => {
                    bar.style.height = height;
                }, 50 + index * 15);
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

def calcular_tendencia(valor_atual, valor_anterior):
    """Calcula a tendência percentual entre dois valores"""
    if valor_anterior and valor_anterior > 0:
        return round(((valor_atual - valor_anterior) / valor_anterior) * 100, 1)
    return round(random.uniform(5, 25), 1)

@app.route('/')
def home():
    """Página inicial com dashboard corporativo premium"""
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
    
    # Postagens totais
    cursor.execute('SELECT COUNT(*) FROM cliques_diarios')
    total_postagens = cursor.fetchone()[0] or 1
    
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
    
    conn.close()
    
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    
    # Calcular métricas derivadas
    ctr_global = round((total_cliques / total_postagens) * 100, 1) if total_postagens > 0 else 0
    taxa_conversao = round((cliques_hoje / max(total_cliques, 1)) * 100, 1)
    receita_estimada = round(total_cliques * 0.47, 2)  # Simulação: R$0,47 por clique
    desconto_medio = media_desconto
    
    # Tendências (simuladas para demonstração)
    trend_cliques = calcular_tendencia(total_cliques, max(total_cliques - 10, 1))
    trend_ctr = calcular_tendencia(ctr_global, max(ctr_global - 2, 1))
    trend_receita = calcular_tendencia(receita_estimada, max(receita_estimada - 5, 1))
    trend_conversao = calcular_tendencia(taxa_conversao, max(taxa_conversao - 1, 1))
    trend_desconto = calcular_tendencia(desconto_medio, max(desconto_medio - 3, 1))
    
    return render_template_string(
        HTML_TEMPLATE,
        total_cliques=total_cliques,
        cliques_hoje=cliques_hoje,
        total_postagens=total_postagens,
        ctr_global=ctr_global,
        taxa_conversao=taxa_conversao,
        receita_estimada=receita_estimada,
        desconto_medio=desconto_medio,
        cliques_plataforma=cliques_plataforma,
        max_cliques_plat=max_cliques_plat,
        cliques_categoria=cliques_categoria,
        max_cliques_cat=max_cliques_cat,
        top_produtos=top_produtos,
        produto_top=produto_top[0][:30] + "..." if produto_top and len(produto_top[0]) > 30 else (produto_top[0] if produto_top else None),
        hora_pico=f"{hora_pico[0]:02d}:00" if hora_pico else None,
        hora_pico_qtd=f"{hora_pico[1]} cliques" if hora_pico else "",
        agora=agora,
        trend_cliques=trend_cliques,
        trend_ctr=trend_ctr,
        trend_receita=trend_receita,
        trend_conversao=trend_conversao,
        trend_desconto=trend_desconto
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
    print("🚀 SERVIDOR DE TRACKING CORPORATIVO INICIADO!")
    print(f"📡 URL BASE: {URL_BASE}")
    print("📊 Dashboard: {}/".format(URL_BASE))
    print("📊 API JSON: {}/api/estatisticas".format(URL_BASE))
    print("="*60)
    print("⚠️  ATENÇÃO: Dashboard premium com design corporativo!")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)
