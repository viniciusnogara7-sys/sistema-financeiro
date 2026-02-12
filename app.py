import streamlit as st
import pandas as pd
import gspread
import textwrap
import os
from datetime import date, datetime, timedelta

# --- 1. CONFIGURAÇÃO GERAL ---
st.set_page_config(page_title="Sistema V24.1 (Secure)", layout="centered", page_icon="🔐")

# --- SENHA DE ACESSO (MIGRADA DO V16) ---
SENHA_ACESSO = "60##0@7##70@Vna"

# --- CSS (CORREÇÃO DE CORES E ESTILO) ---
st.markdown("""
    <style>
    .stApp {background-color: #FAFAFA;}
    .block-container {padding-top: 1rem; padding-bottom: 8rem;}
    
    /* Texto Preto nos Inputs */
    div[role="radiogroup"] label p, div[data-baseweb="select"] span, 
    .stSelectbox label p, .stDateInput label p, .stTextInput label p, .stNumberInput label p {
        color: #333333 !important;
        font-weight: bold !important;
    }

    /* Botões de Navegação */
    div[data-testid="stHorizontalBlock"] > div > button {
        border-radius: 12px; height: 3.5em; border: none;
        background-color: white; box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
        color: #555; font-weight: 600;
    }
    div[data-testid="stHorizontalBlock"] > div > button:hover {
        color: #FF7F00; background-color: #FFF3E0;
    }
    div[data-testid="stHorizontalBlock"] > div > button:focus {
        color: #FF7F00 !important; border-bottom: 2px solid #FF7F00;
    }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 2. CONFIGURAÇÕES (MIGRADAS E ADAPTADAS) ---

# Mapeamento: Chave na Planilha -> Visual no App
CONFIG_CONTAS = {
    "Nubank":       {"Icon": "💜", "Cor": "#F5E6FA", "Nome": "Nubank"},
    "Itaú":         {"Icon": "🟧", "Cor": "#FFF0E6", "Nome": "Itaú"},
    "Inter":        {"Icon": "🧡", "Cor": "#FFF5E6", "Nome": "Inter"},
    "C6":           {"Icon": "🖤", "Cor": "#F0F0F0", "Nome": "C6 Bank"},
    "Porto Seguro": {"Icon": "🔵", "Cor": "#E3F2FD", "Nome": "Porto Seguro"}, # Mantido V16/V24
    "Custos Fixos": {"Icon": "💼", "Cor": "#ECEFF1", "Nome": "Empresa"},      # Mantido V16
}

CONFIG_NATUREZA = {
    "Alimentação":  {"Icon": "🥗", "Cor": "#E8F5E9", "Nome": "Alimentação"}, 
    "Transporte":   {"Icon": "⛽", "Cor": "#E1F5FE", "Nome": "Transporte"},
    "Lazer":        {"Icon": "🎉", "Cor": "#FFF8E1", "Nome": "Lazer"},
    "Moradia":      {"Icon": "🏠", "Cor": "#FCE4EC", "Nome": "Moradia"},
    "Educação":     {"Icon": "📚", "Cor": "#F3E5F5", "Nome": "Educação"},
    "Saúde":        {"Icon": "💊", "Cor": "#E0F2F1", "Nome": "Saúde"},
    "Outro":        {"Icon": "💸", "Cor": "#EEEEEE", "Nome": "Outros"},
}

# METAS (Vindas do seu código V16)
METAS = {
    "Nubank": 2500.00, 
    "Itaú": 1000.00, 
    "Inter": 800.00, 
    "C6": 500.00, 
    "Porto Seguro": 1500.00, # Adicionado
    "Custos Fixos": 2000.00, 
    # Metas de Natureza (Mantidas da V24 pois V16 não tinha separação clara)
    "Alimentação": 1200.00, "Transporte": 600.00, "Lazer": 400.00
}

# DIAS DE VENCIMENTO (V16)
DIAS_VENCIMENTO = {"Nubank": 26, "Itaú": 6, "Inter": 7, "C6": 2, "Porto Seguro": 5}

# PRESETS DE LANÇAMENTO (V16)
PRESET_FIXOS = [
    {"Categoria": "Custos Fixos", "Estabelecimento": "Governo", "Descricao": "DAS (Imposto)", "Valor": 432.00},
    {"Categoria": "Custos Fixos", "Estabelecimento": "Contabilidade", "Descricao": "Contador", "Valor": 300.00},
    {"Categoria": "Custos Fixos", "Estabelecimento": "Próprio", "Descricao": "Pro-labore", "Valor": 166.98},
]

PRESET_ASSINATURAS = [
    {"Categoria": "Nubank", "Estabelecimento": "Saúde", "Descricao": "Unimed", "Valor": 158.38},
    {"Categoria": "Nubank", "Estabelecimento": "Lazer", "Descricao": "Netflix", "Valor": 55.90},
    {"Categoria": "Nubank", "Estabelecimento": "Lazer", "Descricao": "Youtube Premium", "Valor": 16.90},
    {"Categoria": "Nubank", "Estabelecimento": "Seguros", "Descricao": "Seguro Vida", "Valor": 28.72},
]

# --- 3. BACKEND ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state.password_correct = False
    if st.session_state.password_correct: return True
    st.markdown("<br><h3 style='text-align: center;'>🔒 Sistema Seguro V24.1</h3>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        senha = st.text_input("Senha", type="password", label_visibility="collapsed")
        if st.button("Entrar", type="primary", use_container_width=True):
            if senha == SENHA_ACESSO:
                st.session_state.password_correct = True
                st.rerun()
            else: st.error("Senha incorreta.")
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

def tratar_valores_br(valor):
    if isinstance(valor, str):
        if not valor.strip(): return 0.0
        limpo = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        try: return float(limpo)
        except: return 0.0
    return float(valor)

if not check_password(): st.stop()
sheet = conectar_gsheets()

# --- 4. COMPONENTES VISUAIS ---
def render_navbar():
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("💳 Home", use_container_width=True):
            st.session_state['aba_atual'] = 'Principal'; st.rerun()
    with c2:
        if st.button("📊 Analítico", use_container_width=True):
            st.session_state['aba_atual'] = 'Analitico'; st.rerun()
    with c3:
        if st.button("💡 Dicas", use_container_width=True):
            st.session_state['aba_atual'] = 'Sugestao'; st.rerun()
    with c4:
        if st.button("📝 Editor", use_container_width=True):
            st.session_state['aba_atual'] = 'Editor'; st.rerun()

def render_card(titulo, icone, cor_fundo, gasto, limite, grande=False):
    cor_texto = "#333333"
    aviso = ""
    if limite > 0 and gasto > limite: 
        cor_texto = "#D32F2F"
        aviso = "⚠️"
    
    pct = (gasto / limite * 100) if limite > 0 else 0
    tamanho_icone = "40px" if grande else "32px"
    altura_barra = "8px" if grande else "5px"
    
    html = textwrap.dedent(f"""
<div class="card-container" style="background-color: white; border-radius: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 15px; border: 1px solid #f0f0f0; overflow: hidden;">
    <div style="background-color: {cor_fundo}; padding: 15px; text-align: center;">
        <div style="font-size: {tamanho_icone};">{icone}</div>
    </div>
    <div style="padding: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: bold; font-size: 13px; color: #444;">{titulo}</span>
            <span style="font-size: 12px;">{aviso}</span>
        </div>
        <div style="font-size: 10px; color: #888; margin-bottom: 5px;">Meta: {'∞' if limite == 0 else f'R$ {limite:,.0f}'}</div>
        <div style="font-weight: 800; font-size: 16px; color: {cor_texto};">R$ {gasto:,.2f}</div>
        <div style="background-color: #eee; height: {altura_barra}; border-radius: 4px; margin-top: 8px; overflow: hidden;">
            <div style="background-color: {cor_texto if pct > 100 else '#4CAF50'}; width: {min(pct, 100)}%; height: 100%;"></div>
        </div>
    </div>
</div>
""")
    st.markdown(html, unsafe_allow_html=True)

# --- 5. LÓGICA DE DADOS ---
def get_dados_filtrados():
    c1, c2 = st.columns([2, 1])
    with c1:
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        idx = min(date.today().month - 1, 11)
        if hasattr(st, "pills"):
            mes_nome = st.pills("Mês", meses, default=meses[idx], label_visibility="collapsed")
        else: mes_nome = st.selectbox("Mês", meses, index=idx)
    with c2:
        ano = st.selectbox("Ano", list(range(2020, 2031)), index=date.today().year - 2020, label_visibility="collapsed")

    mapa = {m: f"{i+1:02d}" for i, m in enumerate(meses)}
    comp = f"{ano}-{mapa[mes_nome]}"
    
    receita_total = 0
    gastos_conta = {}
    gastos_natureza = {}
    
    if sheet:
        df = pd.DataFrame(sheet.get_all_records())
        if not df.empty:
            for col in ['Valor']: df[col] = df[col].apply(tratar_valores_br)
            df_mes = df[df['Competencia'] == comp]
            
            receita_total = df_mes[df_mes['Categoria'] == 'Receita']['Valor'].sum()
            df_gastos = df_mes[(df_mes['Tipo'] == 'Gasto') & (df_mes['Categoria'] != 'Receita')]
            
            gastos_conta = df_gastos.groupby("Categoria")["Valor"].sum().to_dict()
            gastos_natureza = df_gastos.groupby("Estabelecimento")["Valor"].sum().to_dict()
    
    return mes_nome, ano, receita_total, gastos_conta, gastos_natureza

# --- 6. TELAS ---
def aba_principal():
    mes, ano, receita, gastos_conta, _ = get_dados_filtrados()
    total_despesas = sum(gastos_conta.values())
    saldo = receita - total_despesas
    
    # 1. ALERTAS DE VENCIMENTO (V16 RESTAURADO)
    hoje = date.today().day
    for c, d in DIAS_VENCIMENTO.items():
        if 0 <= d - hoje <= 5: 
            st.warning(f"⚠️ Fatura **{c}** vence dia {d}!")

    # 2. PLACAR
    st.markdown(textwrap.dedent(f"""
    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
        <div style="flex: 1; background: #E8F5E9; padding: 10px; border-radius: 12px; text-align: center; border: 1px solid #C8E6C9;">
            <p style="margin:0; font-size: 10px; color: #2E7D32; font-weight: bold;">ENTRADAS</p>
            <h4 style="margin:2px 0 0 0; color: #1B5E20;">R$ {receita:,.2f}</h4>
        </div>
        <div style="flex: 1; background: #FFEBEE; padding: 10px; border-radius: 12px; text-align: center; border: 1px solid #FFCDD2;">
            <p style="margin:0; font-size: 10px; color: #C62828; font-weight: bold;">SAÍDAS</p>
            <h4 style="margin:2px 0 0 0; color: #B71C1C;">R$ {total_despesas:,.2f}</h4>
        </div>
        <div style="flex: 1; background: #E3F2FD; padding: 10px; border-radius: 12px; text-align: center; border: 1px solid #BBDEFB;">
            <p style="margin:0; font-size: 10px; color: #1565C0; font-weight: bold;">SALDO</p>
            <h4 style="margin:2px 0 0 0; color: #0D47A1;">R$ {saldo:,.2f}</h4>
        </div>
    </div>
    """), unsafe_allow_html=True)

    if st.button("➕ Novo Lançamento", type="primary", use_container_width=True):
        st.session_state['tela_lancamento'] = True; st.rerun()

    st.write("")
    st.markdown("### 💳 Por Conta")
    
    cols = st.columns(2)
    bancos = list(CONFIG_CONTAS.keys())
    for i, conta in enumerate(bancos):
        val = gastos_conta.get(conta, 0.0)
        meta = METAS.get(conta, 0.0)
        conf = CONFIG_CONTAS.get(conta)
        with cols[i % 2]:
            render_card(conf["Nome"], conf["Icon"], conf["Cor"], val, meta)

    st.markdown("<br><br>", unsafe_allow_html=True)
    render_navbar()

def aba_analitico():
    st.markdown("### 📊 Por Classificação")
    mes, ano, _, _, gastos_natureza = get_dados_filtrados()
    naturezas = list(CONFIG_NATUREZA.keys())
    naturezas.sort(key=lambda x: gastos_natureza.get(x, 0), reverse=True)
    
    cols = st.columns(2)
    for i, nat in enumerate(naturezas):
        val = gastos_natureza.get(nat, 0.0)
        meta = METAS.get(nat, 0.0)
        conf = CONFIG_NATUREZA.get(nat)
        with cols[i % 2]:
            render_card(conf["Nome"], conf["Icon"], conf["Cor"], val, meta)
    st.markdown("<br><br>", unsafe_allow_html=True)
    render_navbar()

def aba_sugestoes():
    st.markdown("### 💡 Consultoria IA")
    mes, ano, receita, gastos_conta, _ = get_dados_filtrados()
    total_gasto = sum(gastos_conta.values())
    saldo = receita - total_gasto
    import plotly.graph_objects as go
    if total_gasto > 0 or receita > 0:
        fig = go.Figure(data=[go.Pie(labels=['Gastos', 'Saldo'], values=[total_gasto, max(0, saldo)], hole=.7, marker_colors=['#EF5350', '#66BB6A'])])
        fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=200)
        st.plotly_chart(fig, use_container_width=True)
    
    if saldo < 0: st.error("🚨 Você está no vermelho!")
    elif saldo > 0: st.success(f"✅ Sobrou R$ {saldo:,.2f}")
    st.markdown("<br><br>", unsafe_allow_html=True)
    render_navbar()

def aba_editor():
    st.markdown("### 📝 Editor & Lotes")
    
    # BOTÃO PARA LANÇAMENTO EM LOTE (V16 RESTAURADO)
    if st.button("🚀 Lançar Lotes (Fixos/Assinaturas)", use_container_width=True):
        st.session_state['tela_lote'] = True; st.rerun()

    st.info("Edição direta da planilha:")
    if sheet:
        df = pd.DataFrame(sheet.get_all_records())
        editado = st.data_editor(df, num_rows="dynamic", use_container_width=True, height=400)
        if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
            sheet.clear(); sheet.append_row(df.columns.tolist()); sheet.append_rows(editado.astype(str).values.tolist())
            st.success("✅ Atualizado!"); st.cache_data.clear()
    st.markdown("<br><br>", unsafe_allow_html=True)
    render_navbar()

# --- TELA DE LOTE (MIGRADA DO V16) ---
def tela_lancar_lote():
    st.markdown("### 📝 Lançar Pacote")
    if st.button("🔙 Voltar"):
        st.session_state['tela_lote'] = False; st.rerun()
        
    c1, c2 = st.columns(2)
    tipo = c1.selectbox("Selecione o Pacote", ["Custos Fixos", "Assinaturas"])
    
    # Inteligencia de data (V16)
    hoje = date.today()
    data_sug = hoje + timedelta(days=15) if hoje.day > 20 else hoje
    data_ref = c2.date_input("Vencimento", data_sug)
    
    df_base = pd.DataFrame(PRESET_FIXOS if tipo == "Custos Fixos" else PRESET_ASSINATURAS)
    st.caption(f"Competência: **{data_ref.strftime('%B/%Y')}**")
    
    editado = st.data_editor(df_base, num_rows="dynamic", use_container_width=True)
    
    if st.button("🚀 Lançar Tudo", type="primary", use_container_width=True):
        rows = []
        comp = data_ref.strftime("%Y-%m")
        for _, r in editado.iterrows():
            # Mapeia V16 para V24 (Estabelecimento vira Classificacao)
            rows.append([str(data_ref), comp, r['Categoria'], r['Estabelecimento'], r['Descricao'], float(r['Valor']), 1, 1, "Gasto"])
        sheet.append_rows(rows)
        st.success(f"✅ Lote processado para {comp}!"); st.cache_data.clear()
        
def tela_lancamento():
    st.markdown("### 📝 O que vamos registrar?")
    with st.container(border=True):
        tipo_op = st.radio("Selecione:", ["Gasto", "Receita", "Investimento"], horizontal=True, label_visibility="collapsed")

        if tipo_op == "Gasto": st.error("📉 REGISTRANDO SAÍDA (GASTO)")
        elif tipo_op == "Receita": st.success("💰 REGISTRANDO ENTRADA (RECEITA)")
        else: st.info("📈 REGISTRANDO INVESTIMENTO (APORTE)")

        st.markdown("---")
        with st.form("form_lanca"):
            data = st.date_input("Data", date.today())
            
            if tipo_op == "Gasto":
                c1, c2 = st.columns(2)
                with c1: conta = st.selectbox("💳 Conta", list(CONFIG_CONTAS.keys()))
                with c2: classificacao = st.selectbox("🏷️ Tipo", list(CONFIG_NATUREZA.keys()) + ["Outro"])
            else:
                conta = "Receita" if tipo_op == "Receita" else "Investimento"
                classificacao = st.selectbox("Detalhe", ["Salário", "Freelance", "Ações", "FIIs", "Renda Fixa"])

            desc = st.text_input("Descrição", placeholder="Detalhe...")
            val = st.number_input("Valor (R$)", min_value=0.01)
            
            parcelas = 1
            if tipo_op == "Gasto":
                c1, c2 = st.columns(2)
                pa = c1.number_input("Parcela Atual", 1, value=1)
                pt = c2.number_input("Total Parcelas", 1, value=1)
                parcelas = pt - pa + 1
            
            if st.form_submit_button("✅ CONFIRMAR", type="primary", use_container_width=True):
                comp = data.strftime("%Y-%m")
                if tipo_op == "Gasto" and data.day > 20: comp = (data + timedelta(days=15)).strftime("%Y-%m")
                
                rows = []
                try: y, m = map(int, comp.split('-'))
                except: st.error("Erro data"); st.stop()

                for i in range(parcelas):
                    mc = m + i
                    yc = y + (mc - 1) // 12
                    mc = (mc - 1) % 12 + 1
                    if tipo_op == "Gasto":
                        rows.append([str(data), f"{yc}-{mc:02d}", conta, classificacao, desc, val, pa+i, pt, "Gasto"])
                    elif tipo_op == "Receita": sheet.append_row([str(data), comp, "Receita", "Cliente", desc, val, 1, 1, "Receita"])
                    elif tipo_op == "Investimento": sheet.append_row([str(data), comp, "Investimento", classificacao, desc, val, 1, 1, "Investimento"])

                if tipo_op == "Gasto": sheet.append_rows(rows)
                st.toast("✅ Salvo!"); st.session_state['tela_lancamento'] = False; st.rerun()

    if st.button("🔙 Cancelar", use_container_width=True):
        st.session_state['tela_lancamento'] = False; st.rerun()

# --- 7. ROTEADOR ---
if 'aba_atual' not in st.session_state: st.session_state['aba_atual'] = 'Principal'
if 'tela_lancamento' not in st.session_state: st.session_state['tela_lancamento'] = False
if 'tela_lote' not in st.session_state: st.session_state['tela_lote'] = False

if st.session_state['tela_lancamento']: tela_lancamento()
elif st.session_state['tela_lote']: tela_lancar_lote()
elif st.session_state['aba_atual'] == 'Principal': aba_principal()
elif st.session_state['aba_atual'] == 'Analitico': aba_analitico()
elif st.session_state['aba_atual'] == 'Sugestao': aba_sugestoes()
elif st.session_state['aba_atual'] == 'Editor': aba_editor()
