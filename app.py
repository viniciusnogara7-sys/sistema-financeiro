import streamlit as st
import pandas as pd
import gspread
import textwrap
import plotly.express as px
import plotly.graph_objects as go
import re
import pdfplumber
import os
from datetime import date, datetime, timedelta

# --- 1. CONFIGURAÇÃO GERAL ---
st.set_page_config(page_title="Finanças V33.1", layout="centered", page_icon="🍊")

# --- 👥 CADASTRO DE USUÁRIOS ---
USUARIOS = {
    "60330273370": "Vinicius Nogueira",
    "03692490380": "Ana Vitoria"
}

# --- 📦 PRESETS (LOTE AUTOMÁTICO) ---
MEUS_GASTOS_FIXOS = [
    {"Conta": "Custos Fixos", "Classificacao": "Governo", "Descricao": "DAS (Imposto)", "Valor": 432.00},
    {"Conta": "Custos Fixos", "Classificacao": "Outro",   "Descricao": "Contador", "Valor": 300.00},
    {"Conta": "Custos Fixos", "Classificacao": "Outro",   "Descricao": "Pro-labore", "Valor": 166.98},
    {"Conta": "Nubank", "Classificacao": "Saúde", "Descricao": "Plano de Saúde (Unimed)", "Valor": 158.38},
    {"Conta": "Nubank", "Classificacao": "Lazer", "Descricao": "Netflix", "Valor": 55.90},
    {"Conta": "Nubank", "Classificacao": "Lazer", "Descricao": "Youtube Premium", "Valor": 16.90},
    {"Conta": "Nubank", "Classificacao": "Saúde", "Descricao": "Seguro de Vida", "Valor": 28.72},
]

# --- 2. DADOS PADRÃO ---
DEFAULTS_CONTAS = {
    "Nubank":       {"Icon": "💜", "Cor": "#820AD1", "Nome": "Nubank", "Meta": 2500.00, "Fecha": 19},
    "Itaú":         {"Icon": "🟧", "Cor": "#FF6200", "Nome": "Itaú", "Meta": 1000.00, "Fecha": 28},
    "Inter":        {"Icon": "🧡", "Cor": "#FF7A00", "Nome": "Inter", "Meta": 800.00, "Fecha": 28},
    "C6":           {"Icon": "🖤", "Cor": "#2C2C2C", "Nome": "C6 Bank", "Meta": 500.00, "Fecha": 21},
    "Porto Seguro": {"Icon": "🔵", "Cor": "#004691", "Nome": "Porto Seguro", "Meta": 1500.00, "Fecha": 27},
    "Custos Fixos": {"Icon": "💼", "Cor": "#455A64", "Nome": "Empresa", "Meta": 3000.00, "Fecha": 32},
    "Pessoal":      {"Icon": "👤", "Cor": "#00796B", "Nome": "Conta Pessoal", "Meta": 1000.00, "Fecha": 32},
}

CONFIG_NATUREZA = {
    "Alimentação":  {"Icon": "🥗", "Cor": "#2E7D32", "Nome": "Alimentação"}, 
    "Transporte":   {"Icon": "⛽", "Cor": "#0277BD", "Nome": "Transporte"},
    "Lazer":        {"Icon": "🎉", "Cor": "#F57F17", "Nome": "Lazer"},
    "Moradia":      {"Icon": "🏠", "Cor": "#C2185B", "Nome": "Moradia"},
    "Educação":     {"Icon": "📚", "Cor": "#6A1B9A", "Nome": "Educação"},
    "Saúde":        {"Icon": "💊", "Cor": "#00695C", "Nome": "Saúde"},
    "Beleza":       {"Icon": "💅", "Cor": "#AD1457", "Nome": "Beleza/Cuidados"},
    "Governo":      {"Icon": "🏛️", "Cor": "#546E7A", "Nome": "Impostos"},
    "Outro":        {"Icon": "💸", "Cor": "#616161", "Nome": "Outros"},
}

if 'config_contas' not in st.session_state:
    st.session_state['config_contas'] = DEFAULTS_CONTAS.copy()

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 5rem;}
    div[data-testid="stHorizontalBlock"] > div > button {
        border-radius: 12px; height: 3.5em; border: 1px solid #333;
        background-color: #1E1E1E; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        color: #E0E0E0; font-weight: 600;
    }
    div[data-testid="stHorizontalBlock"] > div > button:hover {
        color: #FF7F00; border-color: #FF7F00; background-color: #252525;
    }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. INTELIGÊNCIA ARTIFICIAL (PDF & NLP) ---
def classificar_gasto(descricao):
    desc_lower = descricao.lower()
    mapa = {
        "uber": "Transporte", "99": "Transporte", "posto": "Transporte", "shell": "Transporte",
        "ifood": "Alimentação", "restaurante": "Alimentação", "mercado": "Alimentação", "assai": "Alimentação", "pgto": "Outro",
        "netflix": "Lazer", "spotify": "Lazer", "amazon": "Outro", "farmacia": "Saúde", "drogaria": "Saúde", "pagaleve": "Outro"
    }
    for k, v in mapa.items():
        if k in desc_lower: return v
    return "Outro"

def extrair_pdf_nubank(texto):
    transacoes = []
    padrao = r'(\d{2}\s[A-Z]{3})\s+(.*?)\s+R\$\s([\d\.,]+)'
    for linha in texto.split('\n'):
        match = re.search(padrao, linha)
        if match:
            d, desc, v = match.groups()
            if "Pagamento" not in desc and "desconto" not in desc.lower():
                transacoes.append({"Data": d, "Descricao": desc.strip(), "Valor": float(v.replace('.','').replace(',','.')), "Classificacao": classificar_gasto(desc)})
    return transacoes

def extrair_pdf_inter(texto):
    transacoes = []
    for linha in texto.split('\n'):
        if "R$" in linha and ("COMPRA" in linha or "PAGAMENTO" not in linha):
            try:
                partes = linha.split("R$")
                desc = partes[0].strip()
                # Limpa a data do desc se houver
                desc = re.sub(r'\d{2} de [a-z]{3}\. \d{4}', '', desc).strip()
                valor = float(partes[1].strip().replace('.','').replace(',','.'))
                transacoes.append({"Data": "", "Descricao": desc, "Valor": valor, "Classificacao": classificar_gasto(desc)})
            except: pass
    return transacoes

def extrair_pdf_itau(texto):
    transacoes = []
    padrao = r'(\d{2}/\d{2})\s+(.*?)\s+(\d+[\.,]\d{2})'
    for linha in texto.split('\n'):
        match = re.search(padrao, linha)
        if match:
            d, desc, v = match.groups()
            if "Pagamento" not in desc and "Total" not in desc:
                transacoes.append({"Data": d, "Descricao": desc.strip(), "Valor": float(v.replace('.','').replace(',','.')), "Classificacao": classificar_gasto(desc)})
    return transacoes

def processar_pdf(uploaded_file):
    with pdfplumber.open(uploaded_file) as pdf:
        texto = "".join([p.extract_text() for p in pdf.pages])
        if "Nubank" in texto: return "Nubank", extrair_pdf_nubank(texto)
        elif "inter" in texto.lower(): return "Inter", extrair_pdf_inter(texto)
        elif "itaú" in texto.lower() or "itau" in texto.lower(): return "Itaú", extrair_pdf_itau(texto)
        return "Desconhecido", []

def processar_texto_inteligente(texto):
    texto = texto.lower()
    valor_final = 0.0
    match_valor = re.search(r'[\d\.]*\,?\d{2}', texto.replace("r$", ""))
    if match_valor:
        try: valor_final = float(match_valor.group(0).replace('.', '').replace(',', '.'))
        except: pass

    banco = "Nubank"
    if "itaú" in texto: banco = "Itaú"
    elif "inter" in texto: banco = "Inter"
    elif "c6" in texto: banco = "C6"
    
    cat = classificar_gasto(texto)
    return valor_final, banco, cat, "Compra Detectada"

# --- 4. BACKEND ---
def logout():
    st.query_params.clear()
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()

def check_login():
    if st.query_params.get("cpf_token") in USUARIOS:
        st.session_state['cpf_usuario'] = st.query_params["cpf_token"]
        st.session_state['nome_usuario'] = USUARIOS[st.session_state['cpf_usuario']]
        return True
    if "cpf_usuario" in st.session_state: return True

    st.markdown("<br><br><h2 style='text-align: center;'>🍊 Finanças Casal</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        cpf = st.text_input("CPF", placeholder="Somente números", label_visibility="collapsed")
        lembrar = st.checkbox("Manter conectado")
        if st.button("Entrar", type="primary", use_container_width=True):
            clean_cpf = cpf.replace(".", "").replace("-", "").strip()
            if clean_cpf in USUARIOS:
                st.session_state['cpf_usuario'] = clean_cpf
                st.session_state['nome_usuario'] = USUARIOS[clean_cpf]
                if lembrar: st.query_params["cpf_token"] = clean_cpf
                st.rerun()
            else: st.error("CPF não encontrado.")
    return False

@st.cache_resource
def conectar_gsheets():
    try:
        if os.path.exists("credentials.json"):
            gc = gspread.service_account(filename="credentials.json")
        elif "gcp_service_account" in st.secrets:
            gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        else: return None
        return gc.open("Financas_Master").sheet1
    except: return None

def tratar_valores_br(val):
    if isinstance(val, str):
        try: return float(val.replace('R$', '').replace('.', '').replace(',', '.').strip())
        except: return 0.0
    return float(val)

if not check_login(): st.stop()
sheet = conectar_gsheets()

# --- 5. COMPONENTES VISUAIS ---
def render_top_bar():
    c1, c2 = st.columns([3, 1])
    with c1: st.markdown(f"<h3 style='margin:0; padding-top:5px;'>Olá, {st.session_state['nome_usuario'].split()[0]}! 👋</h3>", unsafe_allow_html=True)
    with c2: 
        if st.button("🔄 Sair", use_container_width=True): logout()

def render_navbar():
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        if st.button("💳 Home", use_container_width=True): st.session_state['aba_atual'] = 'Principal'; st.rerun()
    with c2: 
        if st.button("📊 Dados", use_container_width=True): st.session_state['aba_atual'] = 'Analitico'; st.rerun()
    with c3: 
        if st.button("💡 Dicas", use_container_width=True): st.session_state['aba_atual'] = 'Sugestao'; st.rerun()
    with c4: 
        if st.button("⚙️ Config", use_container_width=True): st.session_state['aba_atual'] = 'Config'; st.rerun()

def render_card(titulo, icone, cor_fundo, gasto, limite):
    cor_val, cor_bar = "#FFFFFF", "#66BB6A"
    if limite > 0 and gasto > limite: cor_val, cor_bar = "#FF5252", "#FF5252"
    pct = (gasto / limite * 100) if limite > 0 else 0
    st.markdown(textwrap.dedent(f"""
    <div style="background-color: #1E1E1E; border-radius: 16px; margin-bottom: 15px; border: 1px solid #333; overflow: hidden;">
        <div style="display: flex; align-items: center; padding: 12px;">
            <div style="background-color: {cor_fundo}33; padding: 10px; border-radius: 12px; margin-right: 12px; min-width: 45px; text-align: center; border: 1px solid {cor_fundo}66;">
                <div style="font-size: 28px;">{icone}</div>
            </div>
            <div style="flex-grow: 1;">
                <div style="font-weight: bold; font-size: 13px; color: #B0B0B0;">{titulo}</div>
                <div style="font-weight: bold; font-size: 18px; color: {cor_val};">R$ {gasto:,.2f}</div>
                <div style="font-size: 10px; color: #666;">Limite: R$ {limite:,.0f}</div>
            </div>
        </div>
        <div style="background-color: #333; height: 4px; width: 100%;"><div style="background-color: {cor_bar}; width: {min(pct, 100)}%; height: 100%;"></div></div>
    </div>"""), unsafe_allow_html=True)

def render_extrato(df_user):
    st.markdown("### 📜 Histórico Recente")
    if not df_user.empty:
        df_view = df_user.sort_values(by='Data_Obj', ascending=False).head(8)
        for _, row in df_view.iterrows():
            class_name = row.get('Classificacao', row.get('Estabelecimento', 'Outro'))
            conf = CONFIG_NATUREZA.get(class_name, CONFIG_NATUREZA['Outro'])
            cor = "#66BB6A" if row['Tipo'] == 'Receita' else "#FF5252"
            sinal = "+" if row['Tipo'] == 'Receita' else "-"
            st.markdown(f"""
            <div style="background-color: #1E1E1E; padding: 10px; border-radius: 12px; margin-bottom: 8px; border: 1px solid #333; display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; gap: 12px; align-items: center;">
                    <div style="font-size: 18px;">{conf['Icon']}</div>
                    <div><div style="font-weight: 600; font-size: 13px; color: #E0E0E0;">{row['Descricao']}</div><div style="font-size: 11px; color: #888;">{row['Categoria']}</div></div>
                </div>
                <div style="font-weight: bold; color: {cor}; font-size: 13px;">{sinal} R$ {row['Valor']:,.2f}</div>
            </div>""", unsafe_allow_html=True)
    else: st.info("Sem dados recentes.")

# --- 6. LÓGICA DE DADOS ---
def get_dados():
    render_top_bar()
    c1, c2 = st.columns([2, 1])
    with c1: mes = st.selectbox("Mês", ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"], index=min(date.today().month-1, 11))
    with c2: ano = st.selectbox("Ano", list(range(2020, 2031)), index=date.today().year-2020)
    
    mapa = {m: f"{i+1:02d}" for i, m in enumerate(["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"])}
    comp = f"{ano}-{mapa[mes]}"
    
    rec = 0; gastos = {}; nat = {}; df_u = pd.DataFrame()
    if sheet:
        df = pd.DataFrame(sheet.get_all_records())
        if not df.empty:
            if 'CPF' in df.columns: df = df[df['CPF'].astype(str) == st.session_state['cpf_usuario']]
            elif st.session_state['cpf_usuario'] != "60330273370": df = pd.DataFrame(columns=df.columns)
            
            for col in ['Valor']: df[col] = df[col].apply(tratar_valores_br)
            if 'Estabelecimento' in df.columns: df = df.rename(columns={'Estabelecimento': 'Classificacao'})
            
            df['Data_Obj'] = pd.to_datetime(df['Data'], format='%Y-%m-%d', errors='coerce')
            df_u = df
            
            df_m = df[df['Competencia'] == comp]
            rec = df_m[df_m['Categoria'] == 'Receita']['Valor'].sum()
            gastos = df_m[df_m['Tipo'] == 'Gasto'].groupby("Categoria")["Valor"].sum().to_dict()
            nat = df_m[df_m['Tipo'] == 'Gasto'].groupby("Classificacao")["Valor"].sum().to_dict()
            
    return rec, gastos, nat, df_u

# --- 7. TELAS ---
def aba_principal():
    rec, gastos, _, df = get_dados()
    tot = sum(gastos.values()); saldo = rec - tot
    
    st.markdown(textwrap.dedent(f"""
    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
        <div style="flex: 1; background: #1B5E20; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #2E7D32;">
            <p style="margin:0; font-size: 10px; color: #A5D6A7; font-weight: bold;">ENTRADAS</p><h4 style="margin:2px 0 0 0; color: #FFFFFF;">R$ {rec:,.2f}</h4>
        </div>
        <div style="flex: 1; background: #B71C1C; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #C62828;">
            <p style="margin:0; font-size: 10px; color: #EF9A9A; font-weight: bold;">SAÍDAS</p><h4 style="margin:2px 0 0 0; color: #FFFFFF;">R$ {tot:,.2f}</h4>
        </div>
        <div style="flex: 1; background: #0D47A1; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #1565C0;">
            <p style="margin:0; font-size: 10px; color: #90CAF9; font-weight: bold;">SALDO</p><h4 style="margin:2px 0 0 0; color: #FFFFFF;">R$ {saldo:,.2f}</h4>
        </div>
    </div>"""), unsafe_allow_html=True)

    if st.button("➕ Novo Lançamento", type="primary", use_container_width=True): st.session_state['tela'] = 'Lanca'; st.rerun()
    
    st.write(""); st.markdown("### 💳 Carteiras")
    cols = st.columns(2)
    cfg = st.session_state['config_contas']
    for i, k in enumerate(cfg.keys()):
        with cols[i % 2]: render_card(cfg[k]["Nome"], cfg[k]["Icon"], cfg[k]["Cor"], gastos.get(k, 0.0), cfg[k]["Meta"])
    
    st.write(""); render_extrato(df); st.markdown("<br><br>", unsafe_allow_html=True); render_navbar()

def aba_analitico():
    _, _, nat, df = get_dados()
    st.markdown("### 📊 Pareto (80/20)")
    if not df.empty and len(nat) > 0:
        df_p = df[df['Tipo']=='Gasto'].groupby("Classificacao")["Valor"].sum().reset_index().sort_values("Valor", ascending=False)
        df_p["Acum"] = df_p["Valor"].cumsum() / df_p["Valor"].sum() * 100
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_p["Classificacao"], y=df_p["Valor"], name="R$", marker_color="#FF5252"))
        fig.add_trace(go.Scatter(x=df_p["Classificacao"], y=df_p["Acum"], name="%", yaxis="y2", marker_color="white"))
        fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis2=dict(overlaying="y", side="right", range=[0,110]), showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("### 🏷️ Categorias")
    cols = st.columns(2)
    for i, k in enumerate(sorted(nat, key=nat.get, reverse=True)):
        with cols[i % 2]: render_card(k, CONFIG_NATUREZA.get(k, {}).get("Icon", "🏷️"), "#333", nat[k], 0)
    st.markdown("<br><br>", unsafe_allow_html=True); render_navbar()

def aba_sugestoes():
    rec, gastos, _, _ = get_dados()
    tot = sum(gastos.values()); saldo = rec - tot
    st.markdown("### 💡 Inteligência")
    if tot > 0:
        fig = go.Figure(data=[go.Pie(labels=['Gastos', 'Saldo'], values=[tot, max(0, saldo)], hole=.7, marker_colors=['#FF5252', '#66BB6A'])])
        fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', height=250, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    if saldo < 0: st.error("🚨 Vermelho! Controle seus gastos essenciais.")
    else: st.success("✅ Azul! Que tal investir o excedente?")
    st.markdown("<br><br>", unsafe_allow_html=True); render_navbar()

# --- AQUI ESTÁ A CORREÇÃO DO EDITOR DE PLANILHA COM MULTI-USER ---
def aba_config():
    render_top_bar(); st.markdown("### ⚙️ Configurações")
    
    with st.expander("💳 Editar Cartões e Limites", expanded=True):
        sel = st.selectbox("Conta", list(st.session_state['config_contas'].keys()))
        d = st.session_state['config_contas'][sel]
        c1, c2 = st.columns(2)
        m = c1.number_input("Limite", value=float(d['Meta']))
        f = c2.number_input("Fecha dia", value=int(d['Fecha']))
        if st.button("Salvar Cartão"):
            st.session_state['config_contas'][sel]['Meta'] = m
            st.session_state['config_contas'][sel]['Fecha'] = f
            st.success("Salvo!"); st.rerun()

    with st.expander("📝 Editor de Planilha (Banco de Dados)"):
        st.info("Aqui você edita, apaga ou corrige APENAS os seus lançamentos.")
        if sheet:
            df_full = pd.DataFrame(sheet.get_all_records())
            if not df_full.empty and 'CPF' in df_full.columns:
                cpf_atual = st.session_state['cpf_usuario']
                
                # Separa: Seus dados x Dados da Ana
                mask_usuario = df_full['CPF'].astype(str) == cpf_atual
                df_user = df_full[mask_usuario].reset_index(drop=True)
                df_outros = df_full[~mask_usuario]
                
                editado = st.data_editor(df_user, num_rows="dynamic", use_container_width=True)
                
                if st.button("💾 Salvar Planilha na Nuvem", type="primary"):
                    # Junta os seus dados editados com os dados intocados dela
                    df_novo = pd.concat([df_outros, editado], ignore_index=True)
                    
                    sheet.clear()
                    sheet.append_row(df_novo.columns.tolist())
                    sheet.append_rows(df_novo.astype(str).values.tolist())
                    
                    st.success("✅ Banco de dados atualizado!")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.warning("Nenhum dado encontrado para edição.")

    st.markdown("<br><br>", unsafe_allow_html=True); render_navbar()

def tela_lanca():
    st.markdown("### 📝 Registrar")
    c1, c2 = st.columns(2)
    if c1.button("📑 Lote Fixo", use_container_width=True):
        df_l = pd.DataFrame(MEUS_GASTOS_FIXOS)
        edit = st.data_editor(df_l, num_rows="dynamic", use_container_width=True)
        if st.button("🚀 Lançar Lote"):
            rows = []
            for _, r in edit.iterrows():
                rows.append([str(date.today()), date.today().strftime("%Y-%m"), r['Conta'], r['Classificacao'], r['Descricao'], float(r['Valor']), 1, 1, "Gasto", st.session_state['cpf_usuario']])
            sheet.append_rows(rows); st.success("Feito!"); st.session_state['tela'] = ''; st.rerun()
            
    if c2.button("📂 PDF Fatura", use_container_width=True):
        up = st.file_uploader("Arraste o PDF", type="pdf")
        if up:
            banco, dados = processar_pdf(up)
            if banco != "Desconhecido":
                st.success(f"Fatura {banco}!")
                edit = st.data_editor(pd.DataFrame(dados), num_rows="dynamic")
                if st.button("💾 Salvar PDF"):
                    rows = []
                    venc = st.date_input("Vencimento", date.today())
                    for _, r in edit.iterrows():
                        data_str = r['Data'] if pd.notnull(r['Data']) and r['Data'] != "" else str(venc)
                        rows.append([data_str, venc.strftime("%Y-%m"), banco, r['Classificacao'], r['Descricao'], float(r['Valor']), 1, 1, "Gasto", st.session_state['cpf_usuario']])
                    sheet.append_rows(rows); st.success("Importado!"); st.session_state['tela'] = ''; st.rerun()

    st.markdown("---")
    txt = st.text_area("Colar Texto (NLP)", height=70, placeholder="Ex: Uber 15,90 Nubank")
    v_nlp, b_nlp, c_nlp, d_nlp = processar_texto_inteligente(txt) if txt else (0.0, "Nubank", "Outro", "")
    
    with st.form("lanca"):
        d = st.date_input("Data", date.today())
        tipo = st.radio("Tipo", ["Gasto", "Receita", "Investimento"], horizontal=True)
        c1, c2 = st.columns(2)
        conta = c1.selectbox("Conta", list(st.session_state['config_contas'].keys()), index=list(st.session_state['config_contas'].keys()).index(b_nlp) if b_nlp in st.session_state['config_contas'] else 0)
        clas = c2.selectbox("Classe", list(CONFIG_NATUREZA.keys()) + ["Outro"], index=list(CONFIG_NATUREZA.keys()).index(c_nlp) if c_nlp in CONFIG_NATUREZA else 0)
        desc = st.text_input("Desc", value=d_nlp)
        val = st.number_input("Valor", value=v_nlp)
        parc = st.number_input("Parcelas", 1)
        
        if st.form_submit_button("Salvar", type="primary", use_container_width=True):
            comp = d.strftime("%Y-%m")
            if tipo == "Gasto" and d.day >= st.session_state['config_contas'][conta]['Fecha']:
                comp = (d.replace(day=1) + timedelta(days=32)).strftime("%Y-%m")
            
            rows = []
            for i in range(parc):
                dt_p = (d.replace(day=1) + timedelta(days=32*i)).replace(day=d.day)
                rows.append([str(d), comp, conta, clas, desc, val, 1+i, parc, tipo, st.session_state['cpf_usuario']])
            sheet.append_rows(rows); st.success("Salvo!"); st.session_state['tela'] = ''; st.rerun()
            
    if st.button("🔙 Voltar", use_container_width=True): st.session_state['tela'] = ''; st.rerun()

# --- 8. ROTEADOR ---
if 'aba_atual' not in st.session_state: st.session_state['aba_atual'] = 'Principal'
if 'tela' not in st.session_state: st.session_state['tela'] = ''

if st.session_state['tela'] == 'Lanca': tela_lanca()
elif st.session_state['aba_atual'] == 'Principal': aba_principal()
elif st.session_state['aba_atual'] == 'Analitico': aba_analitico()
elif st.session_state['aba_atual'] == 'Sugestao': aba_sugestoes()
elif st.session_state['aba_atual'] == 'Config': aba_config()
