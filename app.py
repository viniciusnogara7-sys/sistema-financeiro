import streamlit as st
import pandas as pd
import gspread
import textwrap
import plotly.express as px
import plotly.graph_objects as go
import re
import os
from datetime import date, datetime, timedelta

# --- 1. CONFIGURAÇÃO GERAL ---
st.set_page_config(page_title="Finanças V32", layout="centered", page_icon="🍊")

# --- 👥 CADASTRO DE USUÁRIOS ---
# ATENÇÃO: Se for tornar o repositório PÚBLICO, mova isso para st.secrets!
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

# --- 3. BACKEND ---
def processar_texto_inteligente(texto):
    texto = texto.lower()
    padrao_valor = r'[\d\.]*\,?\d{2}' 
    match_valor = re.search(padrao_valor, texto.replace("r$", ""))
    valor_final = 0.0
    if match_valor:
        try:
            v_str = match_valor.group(0).replace('.', '').replace(',', '.')
            valor_final = float(v_str)
        except: pass

    banco_detectado = "Nubank" 
    if "itaú" in texto or "itau" in texto: banco_detectado = "Itaú"
    elif "inter" in texto: banco_detectado = "Inter"
    elif "c6" in texto: banco_detectado = "C6"
    elif "porto" in texto: banco_detectado = "Porto Seguro"
    
    cat_detectada = "Outro"
    descricao_sugerida = "Compra Detectada"
    
    mapa_palavras = {
        "uber": ("Transporte", "Uber"), "99": ("Transporte", "99 Pop"),
        "posto": ("Transporte", "Combustível"), "shell": ("Transporte", "Combustível"),
        "ifood": ("Alimentação", "Ifood"), "restaurante": ("Alimentação", "Restaurante"),
        "mercado": ("Alimentação", "Supermercado"), "assai": ("Alimentação", "Assaí"),
        "amazon": ("Outro", "Amazon"), "shein": ("Pessoal", "Roupas"),
        "farmacia": ("Saúde", "Farmácia"), "drogaria": ("Saúde", "Farmácia"),
    }
    
    for chave, (cat, desc) in mapa_palavras.items():
        if chave in texto:
            cat_detectada = cat; descricao_sugerida = desc; break
            
    return valor_final, banco_detectado, cat_detectada, descricao_sugerida

def logout():
    st.query_params.clear()
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

def check_login():
    if "cpf_token" in st.query_params:
        token = st.query_params["cpf_token"]
        if token in USUARIOS:
            st.session_state['cpf_usuario'] = token
            st.session_state['nome_usuario'] = USUARIOS[token]
            return True
    if "cpf_usuario" in st.session_state: return True

    st.markdown("<br><br><h2 style='text-align: center;'>🍊 Finanças Dark</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        cpf_input = st.text_input("CPF", placeholder="Somente números", label_visibility="collapsed")
        lembrar = st.checkbox("Manter conectado")
        if st.button("Entrar", type="primary", use_container_width=True):
            cpf_limpo = cpf_input.replace(".", "").replace("-", "").strip()
            if cpf_limpo in USUARIOS:
                st.session_state['cpf_usuario'] = cpf_limpo
                st.session_state['nome_usuario'] = USUARIOS[cpf_limpo]
                if lembrar: st.query_params["cpf_token"] = cpf_limpo
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

def tratar_valores_br(valor):
    if isinstance(valor, str):
        if not valor.strip(): return 0.0
        limpo = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        try: return float(limpo)
        except: return 0.0
    return float(valor)

if not check_login(): st.stop()
sheet = conectar_gsheets()

# --- 4. COMPONENTES VISUAIS ---
def render_top_bar():
    c1, c2 = st.columns([3, 1])
    with c1:
        nome = st.session_state['nome_usuario'].split()[0]
        st.markdown(f"<h3 style='margin:0; padding-top:5px;'>Olá, {nome}! 👋</h3>", unsafe_allow_html=True)
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

def render_card(titulo, icone, cor_fundo, gasto, limite, grande=False):
    cor_valor = "#FFFFFF"; aviso = ""; cor_barra = "#66BB6A"
    if limite > 0 and gasto > limite: cor_valor = "#FF5252"; aviso = "⚠️"; cor_barra = "#FF5252"
    pct = (gasto / limite * 100) if limite > 0 else 0
    tamanho_icone = "35px" if grande else "28px"
    
    html = textwrap.dedent(f"""
<div style="background-color: #1E1E1E; border-radius: 16px; margin-bottom: 15px; border: 1px solid #333; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
    <div style="display: flex; align-items: center; padding: 12px;">
        <div style="background-color: {cor_fundo}33; padding: 10px; border-radius: 12px; margin-right: 12px; min-width: 45px; text-align: center; border: 1px solid {cor_fundo}66;">
            <div style="font-size: {tamanho_icone};">{icone}</div>
        </div>
        <div style="flex-grow: 1;">
            <div style="display: flex; justify-content: space-between;">
                <span style="font-weight: bold; font-size: 13px; color: #B0B0B0;">{titulo}</span>
                <span style="font-size: 12px;">{aviso}</span>
            </div>
            <div style="font-weight: bold; font-size: 18px; color: {cor_valor}; margin-top: 2px;">R$ {gasto:,.2f}</div>
            <div style="font-size: 10px; color: #666;">Limite: {'∞' if limite == 0 else f'R$ {limite:,.0f}'}</div>
        </div>
    </div>
    <div style="background-color: #333; height: 4px; width: 100%;">
        <div style="background-color: {cor_barra}; width: {min(pct, 100)}%; height: 100%;"></div>
    </div>
</div>
""")
    st.markdown(html, unsafe_allow_html=True)

def render_extrato(df_user):
    st.markdown("### 📜 Histórico Recente")
    if not df_user.empty:
        df_user['Data_Obj'] = pd.to_datetime(df_user['Data'], format='%Y-%m-%d', errors='coerce')
        df_view = df_user.sort_values(by='Data_Obj', ascending=False).head(8)
        for _, row in df_view.iterrows():
            tipo = row['Tipo']; val = tratar_valores_br(row['Valor']); desc = row['Descricao']; cat = row['Categoria']
            dia = row['Data_Obj'].strftime('%d/%m') if pd.notnull(row['Data_Obj']) else ""
            
            if tipo == "Receita": icone, cor, sinal = "💰", "#66BB6A", "+"
            elif tipo == "Investimento": icone, cor, sinal = "📈", "#42A5F5", ""
            else:
                # Segurança para encontrar o nome da categoria
                class_name = row.get('Classificacao', row.get('Estabelecimento', 'Outro'))
                conf = CONFIG_NATUREZA.get(class_name, CONFIG_NATUREZA['Outro'])
                icone = conf['Icon']; cor, sinal = "#FF5252", "-"
            
            st.markdown(f"""
            <div style="background-color: #1E1E1E; padding: 12px; border-radius: 12px; margin-bottom: 8px; border: 1px solid #333; display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; gap: 12px; align-items: center;">
                    <div style="font-size: 18px;">{icone}</div>
                    <div>
                        <div style="font-weight: 600; font-size: 13px; color: #E0E0E0;">{desc}</div>
                        <div style="font-size: 11px; color: #888;">{dia} • {cat}</div>
                    </div>
                </div>
                <div style="font-weight: bold; color: {cor}; font-size: 13px;">{sinal} R$ {val:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    else: st.info("Sem dados recentes.")

def plot_pareto(df_user):
    st.markdown("### 📉 Lei de Pareto (80/20)")
    st.info("Foque nos itens à esquerda. Eles representam a maior parte do seu custo.")
    if not df_user.empty:
        df_pareto = df_user[df_user['Tipo'] == 'Gasto'].groupby("Classificacao")["Valor"].sum().reset_index()
        df_pareto = df_pareto.sort_values(by="Valor", ascending=False)
        df_pareto["Acumulado"] = df_pareto["Valor"].cumsum()
        total = df_pareto["Valor"].sum()
        df_pareto["Perc_Acumulado"] = (df_pareto["Acumulado"] / total) * 100
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_pareto["Classificacao"], y=df_pareto["Valor"], name="Gasto (R$)", marker_color="#FF5252"))
        fig.add_trace(go.Scatter(x=df_pareto["Classificacao"], y=df_pareto["Perc_Acumulado"], name="% Acumulado", yaxis="y2", marker_color="#FFFFFF", mode="lines+markers"))
        fig.update_layout(xaxis_title=None, yaxis=dict(title="Valor (R$)", showgrid=False), yaxis2=dict(title="Acumulado (%)", overlaying="y", side="right", showgrid=False, range=[0, 110]), template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=350, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# --- 5. LÓGICA DE DADOS ---
def get_dados_filtrados():
    render_top_bar()
    c1, c2 = st.columns([2, 1])
    with c1:
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        idx = min(date.today().month - 1, 11)
        if hasattr(st, "pills"): mes_nome = st.pills("Mês", meses, default=meses[idx], label_visibility="collapsed")
        else: mes_nome = st.selectbox("Mês", meses, index=idx)
    with c2:
        ano = st.selectbox("Ano", list(range(2020, 2031)), index=date.today().year - 2020, label_visibility="collapsed")

    mapa = {m: f"{i+1:02d}" for i, m in enumerate(meses)}
    comp = f"{ano}-{mapa[mes_nome]}"
    
    receita_total = 0; gastos_conta = {}; gastos_natureza = {}; df_filtrado_user = pd.DataFrame()
    
    if sheet:
        df = pd.DataFrame(sheet.get_all_records())
        if not df.empty:
            if 'CPF' in df.columns: df = df[df['CPF'].astype(str) == st.session_state['cpf_usuario']]
            elif st.session_state['cpf_usuario'] != "60330273370": df = pd.DataFrame(columns=df.columns)

            for col in ['Valor']: df[col] = df[col].apply(tratar_valores_br)
            # PADRONIZAÇÃO DE COLUNAS
            if 'Estabelecimento' in df.columns: df = df.rename(columns={'Estabelecimento': 'Classificacao'})
            
            df_filtrado_user = df
            df_mes = df[df['Competencia'] == comp]
            
            receita_total = df_mes[df_mes['Categoria'] == 'Receita']['Valor'].sum()
            df_gastos = df_mes[(df_mes['Tipo'] == 'Gasto') & (df_mes['Categoria'] != 'Receita')]
            gastos_conta = df_gastos.groupby("Categoria")["Valor"].sum().to_dict()
            gastos_natureza = df_gastos.groupby("Classificacao")["Valor"].sum().to_dict()
    
    return mes_nome, ano, receita_total, gastos_conta, gastos_natureza, df_filtrado_user

# --- 6. TELAS ---
def aba_principal():
    mes, ano, receita, gastos_conta, _, df_user = get_dados_filtrados()
    total_despesas = sum(gastos_conta.values())
    saldo = receita - total_despesas
    
    st.markdown(textwrap.dedent(f"""
    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
        <div style="flex: 1; background: #1B5E20; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #2E7D32;">
            <p style="margin:0; font-size: 10px; color: #A5D6A7; font-weight: bold;">ENTRADAS</p>
            <h4 style="margin:2px 0 0 0; color: #FFFFFF;">R$ {receita:,.2f}</h4>
        </div>
        <div style="flex: 1; background: #B71C1C; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #C62828;">
            <p style="margin:0; font-size: 10px; color: #EF9A9A; font-weight: bold;">SAÍDAS</p>
            <h4 style="margin:2px 0 0 0; color: #FFFFFF;">R$ {total_despesas:,.2f}</h4>
        </div>
        <div style="flex: 1; background: #0D47A1; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #1565C0;">
            <p style="margin:0; font-size: 10px; color: #90CAF9; font-weight: bold;">SALDO</p>
            <h4 style="margin:2px 0 0 0; color: #FFFFFF;">R$ {saldo:,.2f}</h4>
        </div>
    </div>
    """), unsafe_allow_html=True)

    if st.button("➕ Novo Lançamento", type="primary", use_container_width=True):
        st.session_state['tela_lancamento'] = True; st.rerun()

    st.write("")
    st.markdown("### 💳 Carteiras")
    cols = st.columns(2)
    config_atual = st.session_state['config_contas']
    for i, conta_key in enumerate(config_atual.keys()):
        val = gastos_conta.get(conta_key, 0.0)
        dados_conta = config_atual[conta_key]
        with cols[i % 2]: render_card(dados_conta["Nome"], dados_conta["Icon"], dados_conta["Cor"], val, dados_conta["Meta"])

    st.write(""); render_extrato(df_user)
    st.markdown("<br><br>", unsafe_allow_html=True); render_navbar()

def aba_analitico():
    st.markdown("### 📊 Análise")
    mes, ano, _, _, gastos_natureza, df_total = get_dados_filtrados()
    if not df_total.empty: plot_pareto(df_total)
    
    st.markdown("### 🏷️ Categorias")
    naturezas = list(CONFIG_NATUREZA.keys()); naturezas.sort(key=lambda x: gastos_natureza.get(x, 0), reverse=True)
    cols = st.columns(2)
    for i, nat in enumerate(naturezas):
        val = gastos_natureza.get(nat, 0.0); conf = CONFIG_NATUREZA.get(nat)
        with cols[i % 2]: render_card(conf["Nome"], conf["Icon"], conf["Cor"], val, 1000.0)
    st.markdown("<br><br>", unsafe_allow_html=True); render_navbar()

def aba_sugestoes():
    st.markdown("### 💡 Inteligência")
    mes, ano, receita, gastos_conta, _, _ = get_dados_filtrados()
    total_gasto = sum(gastos_conta.values()); saldo = receita - total_gasto
    if total_gasto > 0 or receita > 0:
        fig = go.Figure(data=[go.Pie(labels=['Gastos', 'Saldo'], values=[total_gasto, max(0, saldo)], hole=.7, marker_colors=['#FF5252', '#66BB6A'])])
        fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=200, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
    if saldo < 0: st.error("🚨 Você está no vermelho!")
    else: st.success(f"✅ Saldo positivo!")
    st.markdown("<br><br>", unsafe_allow_html=True); render_navbar()

def aba_configuracoes():
    render_top_bar()
    st.markdown("### ⚙️ Configurações")
    with st.expander("💳 Gerenciar Cartões e Limites", expanded=True):
        conta_selecionada = st.selectbox("Editar qual conta?", list(st.session_state['config_contas'].keys()))
        dados = st.session_state['config_contas'][conta_selecionada]
        c1, c2 = st.columns(2)
        novo_limite = c1.number_input("Limite (Meta)", value=float(dados['Meta']))
        novo_dia = c2.number_input("Dia Fechamento", value=int(dados['Fecha']), min_value=1, max_value=31)
        novo_nome = st.text_input("Nome de Exibição", value=dados['Nome'])
        if st.button("💾 Salvar Alterações"):
            st.session_state['config_contas'][conta_selecionada]['Meta'] = novo_limite
            st.session_state['config_contas'][conta_selecionada]['Fecha'] = novo_dia
            st.session_state['config_contas'][conta_selecionada]['Nome'] = novo_nome
            st.success(f"Atualizado!"); st.rerun()

    with st.expander("📝 Editor de Planilha"):
        if sheet:
            df = pd.DataFrame(sheet.get_all_records())
            if 'CPF' in df.columns:
                df_user = df[df['CPF'].astype(str) == st.session_state['cpf_usuario']]
                st.dataframe(df_user, use_container_width=True)
    st.markdown("<br><br>", unsafe_allow_html=True); render_navbar()

def tela_lancar_lote():
    st.markdown("### 📑 Lote Rápido")
    if st.button("🔙 Voltar"): st.session_state['tela_lote'] = False; st.rerun()
    st.info("Confira os itens abaixo e clique em Lançar.")
    c1, c2 = st.columns(2)
    hoje = date.today()
    data_sug = hoje + timedelta(days=15) if hoje.day > 20 else hoje
    data_ref = c1.date_input("Vencimento", data_sug)
    
    df_lote = pd.DataFrame(MEUS_GASTOS_FIXOS)
    editado = st.data_editor(df_lote, num_rows="dynamic", use_container_width=True)
    
    if st.button("🚀 Confirmar Lançamento em Massa", type="primary", use_container_width=True):
        rows = []
        comp = data_ref.strftime("%Y-%m")
        cpf_user = st.session_state['cpf_usuario']
        for _, r in editado.iterrows():
            rows.append([str(data_ref), comp, r['Conta'], r['Classificacao'], r['Descricao'], float(r['Valor']), 1, 1, "Gasto", cpf_user])
        sheet.append_rows(rows)
        st.success("✅ Contas fixas lançadas com sucesso!"); st.cache_data.clear()

def tela_lancamento():
    st.markdown(f"### 📝 Registrar")
    with st.container(border=True):
        if st.button("📑 Lançar Contas Fixas (DAS, Netflix...)", use_container_width=True): st.session_state['tela_lote'] = True; st.rerun()
        st.markdown("---")
        
        st.markdown("📋 **Colar Notificação (Inteligente)**")
        texto_paste = st.text_area("Cole aqui: 'Compra aprovada R$ 20,00 Uber'", height=70, label_visibility="collapsed")
        
        val_nlp, banco_nlp, cat_nlp, desc_nlp = 0.0, "Nubank", "Outro", ""
        if texto_paste:
            val_nlp, banco_nlp, cat_nlp, desc_nlp = processar_texto_inteligente(texto_paste)
            if val_nlp > 0: st.caption(f"🤖 Entendi: {banco_nlp} | R$ {val_nlp} | {desc_nlp}")

        st.markdown("---")
        tipo_op = st.radio("Selecione:", ["Gasto", "Receita", "Investimento"], horizontal=True, label_visibility="collapsed")
        if tipo_op == "Gasto": st.error("📉 SAÍDA")
        elif tipo_op == "Receita": st.success("💰 ENTRADA")
        else: st.info("📈 APORTE")

        st.markdown("---")
        with st.form("form_lanca"):
            data = st.date_input("Data", date.today())
            
            if tipo_op == "Gasto":
                c1, c2 = st.columns(2)
                # Inteligencia do NLP
                idx_banco = list(st.session_state['config_contas'].keys()).index(banco_nlp) if banco_nlp in st.session_state['config_contas'] else 0
                idx_cat = list(CONFIG_NATUREZA.keys()).index(cat_nlp) if cat_nlp in CONFIG_NATUREZA else len(CONFIG_NATUREZA)-1
                
                with c1: conta = st.selectbox("💳 Conta", list(st.session_state['config_contas'].keys()), index=idx_banco)
                with c2: classificacao = st.selectbox("🏷️ Tipo", list(CONFIG_NATUREZA.keys()) + ["Outro"], index=idx_cat)
            else:
                conta = "Receita" if tipo_op == "Receita" else "Investimento"
                classificacao = st.selectbox("Detalhe", ["Salário", "Freelance", "Presente", "Ações", "FIIs", "Renda Fixa"])

            desc = st.text_input("Descrição", value=desc_nlp, placeholder="Detalhe...")
            val = st.number_input("Valor (R$)", value=val_nlp, min_value=0.00)
            
            parcelas = 1
            if tipo_op == "Gasto":
                c1, c2 = st.columns(2)
                pa = c1.number_input("Parcela Atual", 1, value=1)
                pt = c2.number_input("Total Parcelas", 1, value=1)
                parcelas = pt - pa + 1
            
            if st.form_submit_button("✅ CONFIRMAR", type="primary", use_container_width=True):
                comp = data.strftime("%Y-%m")
                if tipo_op == "Gasto":
                    dados_conta = st.session_state['config_contas'].get(conta)
                    dia_fecha = dados_conta['Fecha'] if dados_conta else 32
                    if data.day >= dia_fecha:
                        prox_mes = (data.replace(day=1) + timedelta(days=32)).replace(day=1)
                        comp = prox_mes.strftime("%Y-%m")
                        st.toast(f"📅 Fatura fechada! Jogado para {comp}")

                rows = []
                try: y, m = map(int, comp.split('-'))
                except: st.error("Erro data"); st.stop()
                cpf_user = st.session_state['cpf_usuario']

                for i in range(parcelas):
                    mc = m + i
                    yc = y + (mc - 1) // 12
                    mc = (mc - 1) % 12 + 1
                    if tipo_op == "Gasto":
                        rows.append([str(data), f"{yc}-{mc:02d}", conta, classificacao, desc, val, pa+i, pt, "Gasto", cpf_user])
                    elif tipo_op == "Receita": 
                        sheet.append_row([str(data), comp, "Receita", "Cliente", desc, val, 1, 1, "Receita", cpf_user])
                    elif tipo_op == "Investimento": 
                        sheet.append_row([str(data), comp, "Investimento", classificacao, desc, val, 1, 1, "Investimento", cpf_user])

                if tipo_op == "Gasto": sheet.append_rows(rows)
                st.toast("✅ Salvo!"); st.session_state['tela_lancamento'] = False; st.rerun()

    if st.button("🔙 Cancelar", use_container_width=True): st.session_state['tela_lancamento'] = False; st.rerun()

# --- 8. ROTEADOR ---
if 'aba_atual' not in st.session_state: st.session_state['aba_atual'] = 'Principal'
if 'tela_lancamento' not in st.session_state: st.session_state['tela_lancamento'] = False
if 'tela_lote' not in st.session_state: st.session_state['tela_lote'] = False

if st.session_state['tela_lancamento']: tela_lancamento()
elif st.session_state['tela_lote']: tela_lancar_lote()
elif st.session_state['aba_atual'] == 'Principal': aba_principal()
elif st.session_state['aba_atual'] == 'Analitico': aba_analitico()
elif st.session_state['aba_atual'] == 'Sugestao': aba_sugestoes()
elif st.session_state['aba_atual'] == 'Config': aba_configuracoes()
