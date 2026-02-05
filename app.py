import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
import os
from datetime import date, datetime, timedelta

# --- 1. CONFIGURAÇÃO GERAL ---
st.set_page_config(page_title="Sistema V16 (Secure)", layout="wide", page_icon="🔐")

# --- SENHA DE ACESSO (MODIFIQUE AQUI) ---
SENHA_ACESSO = "engenharia123" 

# --- 2. PARÂMETROS ---
METAS_GASTOS = {
    "Nubank": 2500.00,
    "Itaú": 1000.00,
    "Inter": 800.00,
    "C6": 500.00,
    "Custos Fixos": 2000.00
}

META_INVESTIMENTO_MENSAL = 2000.00 
DIAS_VENCIMENTO = {"Nubank": 26, "Itaú": 6, "Inter": 7, "C6": 2, "Porto Seguro": 5}

# MAPA DE INTELIGÊNCIA (PALAVRA CHAVE -> PREENCHIMENTO AUTOMÁTICO)
MAPA_AUTO = {
    "uber": {"Cat": "Nubank", "Estab": "Uber"},
    "ifood": {"Cat": "Nubank", "Estab": "Ifood"},
    "posto": {"Cat": "Itaú", "Estab": "Posto Ipiranga"},
    "shell": {"Cat": "Itaú", "Estab": "Posto Shell"},
    "amazon": {"Cat": "Inter", "Estab": "Amazon"},
    "netflix": {"Cat": "Nubank", "Estab": "Netflix"},
    "spotify": {"Cat": "Nubank", "Estab": "Spotify"},
    "das": {"Cat": "Custos Fixos", "Estab": "Governo"},
}

PRESET_FIXOS = [
    {"Categoria": "Custos Fixos", "Estabelecimento": "Governo", "Descricao": "DAS (Imposto)", "Valor": 432.00, "Tipo": "Gasto"},
    {"Categoria": "Custos Fixos", "Estabelecimento": "Contabilidade", "Descricao": "Contador", "Valor": 300.00, "Tipo": "Gasto"},
    {"Categoria": "Custos Fixos", "Estabelecimento": "Próprio", "Descricao": "Pro-labore", "Valor": 166.98, "Tipo": "Gasto"},
]

PRESET_ASSINATURAS = [
    {"Categoria": "Nubank", "Estabelecimento": "Unimed", "Descricao": "Plano de Saúde", "Valor": 158.38, "Tipo": "Gasto"},
    {"Categoria": "Nubank", "Estabelecimento": "Netflix", "Descricao": "Netflix", "Valor": 55.90, "Tipo": "Gasto"},
    {"Categoria": "Nubank", "Estabelecimento": "Google", "Descricao": "Youtube Premium", "Valor": 16.90, "Tipo": "Gasto"},
    {"Categoria": "Nubank", "Estabelecimento": "Vida", "Descricao": "Seguro", "Valor": 28.72, "Tipo": "Gasto"},
]

# --- 3. CONEXÃO E LOGIN ---
def check_password():
    """Retorna True se a senha estiver correta"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    # Tela de Login
    st.title("🔒 Acesso Restrito")
    senha = st.text_input("Digite a senha de acesso:", type="password")
    if st.button("Entrar"):
        if senha == SENHA_ACESSO:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False

@st.cache_resource
def conectar_gsheets():
    try:
        if os.path.exists("credentials.json"):
            gc = gspread.service_account(filename="credentials.json")
        elif "gcp_service_account" in st.secrets:
            gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        else:
            st.error("❌ ERRO: Arquivo 'credentials.json' não encontrado.")
            st.stop()
        return gc.open("Financas_Master").sheet1
    except Exception as e:
        st.error(f"Erro Conexão: {e}")
        st.stop()

def tratar_valores_br(valor):
    if isinstance(valor, str):
        if not valor.strip(): return 0.0
        limpo = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        try: return float(limpo)
        except: return 0.0
    return float(valor)

# BLOQUEIO DE SEGURANÇA
if not check_password():
    st.stop()

# Se passou da senha, carrega o resto
sheet = conectar_gsheets()

# --- 4. FUNÇÕES VISUAIS ---
def plot_ranking_bancos(df):
    if df.empty: return
    df_rank = df.groupby("Categoria")["Valor"].sum().reset_index().sort_values("Valor", ascending=True)
    fig = px.bar(df_rank, x="Valor", y="Categoria", orientation='h', text="Valor", 
                 title="🏆 Ranking de Gastos", color="Valor", color_continuous_scale="Reds")
    fig.update_traces(texttemplate='R$ %{text:,.2f}')
    fig.update_layout(yaxis_title=None, xaxis_title=None, coloraxis_showscale=False, height=350)
    st.plotly_chart(fig, use_container_width=True)

def plot_carteira_invest(df):
    if df.empty: 
        st.info("Nenhum investimento registrado.")
        return
    df_rank = df.groupby("Descricao")["Valor"].sum().reset_index()
    fig = px.pie(df_rank, values='Valor', names='Descricao', title="Carteira do Mês", hole=0.4)
    st.plotly_chart(fig, use_container_width=True)

def plot_evolucao_anual(df):
    # Agrupa por Competência e Tipo
    if df.empty: return
    df_evo = df.groupby(["Competencia", "Tipo"])["Valor"].sum().reset_index()
    fig = px.line(df_evo, x="Competencia", y="Valor", color="Tipo", markers=True, 
                  title="📈 Evolução Anual: Gasto vs Investimento vs Receita")
    st.plotly_chart(fig, use_container_width=True)

# --- 5. PÁGINAS ---

def pagina_dashboard():
    st.title("📊 Painel Financeiro")
    
    dados = sheet.get_all_records()
    df = pd.DataFrame(dados)
    if df.empty: st.warning("Sem dados."); return

    for col in ['Valor', 'Parcela_Atual', 'Total_Parcelas']:
        if col in df.columns: df[col] = df[col].apply(tratar_valores_br)

    # Alertas
    hoje = date.today().day
    with st.container():
        for c, d in DIAS_VENCIMENTO.items():
            if 0 <= d - hoje <= 5: st.error(f"⚠️ Fatura **{c}** vence dia {d}!")

    # Filtros
    meses = sorted(df['Competencia'].astype(str).unique(), reverse=True)
    mes_atual = st.sidebar.selectbox("📅 Mês de Referência", meses)
    
    df_mes = df[df['Competencia'] == mes_atual]
    df_rec = df_mes[df_mes['Categoria'] == 'Receita']
    
    if 'Tipo' in df_mes.columns:
        df_invest = df_mes[df_mes['Tipo'] == 'Investimento']
        df_gastos = df_mes[(df_mes['Tipo'] == 'Gasto') & (df_mes['Categoria'] != 'Receita')]
    else:
        df_invest = pd.DataFrame(); df_gastos = df_mes[df_mes['Categoria'] != 'Receita']

    # KPIs
    total_rec = df_rec['Valor'].sum()
    total_gasto = df_gastos['Valor'].sum()
    total_invest = df_invest['Valor'].sum()
    saldo = total_rec - total_gasto - total_invest

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Entradas", f"R$ {total_rec:,.2f}")
    k2.metric("Despesas", f"R$ {total_gasto:,.2f}", delta=-total_gasto)
    k3.metric("Aportes", f"R$ {total_invest:,.2f}", delta=f"Meta: {(total_invest/META_INVESTIMENTO_MENSAL)*100:.0f}%")
    k4.metric("Sobra de Caixa", f"R$ {saldo:,.2f}", delta_color="normal" if saldo > 0 else "inverse")

    st.markdown("---")
    
    # NOVAS ABAS
    t1, t2, t3, t4 = st.tabs(["📉 Análise Mensal", "📈 Investimentos", "🎯 Metas", "📅 Visão Anual"])
    
    with t1:
        c1, c2 = st.columns([2, 1])
        with c1: plot_ranking_bancos(df_gastos)
        with c2: 
            st.subheader("Top Despesas")
            if not df_gastos.empty: st.dataframe(df_gastos.groupby("Estabelecimento")["Valor"].sum().sort_values(ascending=False).head(5))
    with t2:
        c1, c2 = st.columns([1, 1])
        with c1: plot_carteira_invest(df_invest)
        with c2: st.dataframe(df_invest[['Data', 'Descricao', 'Valor']], use_container_width=True, hide_index=True)
    with t3:
        st.subheader("Budget vs Realizado")
        cols = st.columns(3)
        i = 0
        gastos_cat = df_gastos.groupby("Categoria")["Valor"].sum()
        for cat, meta in METAS_GASTOS.items():
            val = gastos_cat.get(cat, 0)
            pct = val/meta if meta > 0 else 0
            cor = "red" if pct > 1 else "green"
            with cols[i%3]:
                st.write(f"**{cat}**")
                st.progress(min(pct, 1.0))
                st.caption(f":{cor}[{pct*100:.0f}% de R$ {meta}]")
            i+=1
    with t4: # NOVA ABA DE VISÃO ANUAL
        st.subheader("Histórico do Ano")
        plot_evolucao_anual(df) # Passa o dataframe completo, não só o do mês

def pagina_lancar_despesas():
    st.header("💳 Lançar Nova Despesa")
    
    # Campo de busca inteligente
    search = st.text_input("🔎 Digite para preencher automático (Ex: Uber, Ifood, Amazon):")
    
    # Valores padrão
    def_cat_idx = 0
    def_estab = ""
    
    # Lógica de Autocomplete
    if search:
        for key, val in MAPA_AUTO.items():
            if key in search.lower():
                # Encontra o indice da categoria na lista
                lista_cats = list(METAS_GASTOS.keys()) + ["Outro"]
                if val["Cat"] in lista_cats:
                    def_cat_idx = lista_cats.index(val["Cat"])
                def_estab = val["Estab"]
                st.toast(f"✨ Autopreenchido: {val['Cat']} - {val['Estab']}", icon="🤖")
                break
    
    with st.form("despesa"):
        data = st.date_input("Data Compra", date.today())
        comp_padrao = (data + timedelta(days=15)).strftime("%Y-%m") if data.day > 20 else data.strftime("%Y-%m")
        
        c1, c2 = st.columns(2)
        competencia = c1.text_input("Mês Fatura", value=comp_padrao)
        cat = c2.selectbox("Cartão/Banco", list(METAS_GASTOS.keys()) + ["Outro"], index=def_cat_idx)
        
        estab = st.text_input("Estabelecimento", value=def_estab)
        desc = st.text_input("Descrição", value=search if search else "")
        val = st.number_input("Valor (R$)", min_value=0.01)
        
        pa, pt = st.columns(2)
        p_atual = pa.number_input("Parcela Atual", 1)
        p_total = pt.number_input("Total Parcelas", 1)
        rep = st.checkbox("Replicar?", True)
        
        if st.form_submit_button("💾 Salvar"):
            qtd = (p_total - p_atual + 1) if rep else 1
            rows = []
            try: y, m = map(int, competencia.split('-'))
            except: st.error("Erro data"); st.stop()
            for i in range(qtd):
                mc = m + i
                yc = y + (mc - 1) // 12
                mc = (mc - 1) % 12 + 1
                rows.append([str(data), f"{yc}-{mc:02d}", cat, estab, desc, val, p_atual+i, p_total, "Gasto"])
            sheet.append_rows(rows)
            st.success("Lançado!")
            st.cache_data.clear()

def pagina_lancar_investimento():
    st.header("📈 Lançar Investimento")
    with st.form("invest"):
        data = st.date_input("Data", date.today())
        comp = data.strftime("%Y-%m")
        c1, c2 = st.columns(2)
        tipo_ativo = c1.selectbox("Tipo", ["Ações", "FIIs", "Renda Fixa", "Cripto", "Reserva"])
        corretora = c2.text_input("Corretora", "NuInvest")
        ativo = st.text_input("Descrição", placeholder="Ex: MXRF11")
        valor = st.number_input("Valor (R$)", min_value=0.01)
        if st.form_submit_button("Salvar"):
            sheet.append_row([str(data), comp, tipo_ativo, corretora, ativo, valor, 1, 1, "Investimento"])
            st.success("Salvo!")
            st.cache_data.clear()

def pagina_lancar_lote():
    st.header("📝 Lançamento em Lote")
    tipo = st.selectbox("Pacote", ["Custos Fixos", "Assinaturas"])
    df_base = pd.DataFrame(PRESET_FIXOS if tipo == "Custos Fixos" else PRESET_ASSINATURAS)
    editado = st.data_editor(df_base, num_rows="dynamic", use_container_width=True)
    if st.button("🚀 Lançar Tudo"):
        rows = []
        comp = date.today().strftime("%Y-%m")
        for _, r in editado.iterrows():
            rows.append([str(date.today()), comp, r['Categoria'], r['Estabelecimento'], r['Descricao'], float(r['Valor']), 1, 1, r.get('Tipo', 'Gasto')])
        sheet.append_rows(rows)
        st.success("Sucesso!")
        st.cache_data.clear()

def pagina_lancar_receita():
    st.header("💰 Lançar Receita")
    with st.form("rec"):
        val = st.number_input("Valor")
        desc = st.text_input("Descrição", "Salário")
        if st.form_submit_button("Salvar"):
            sheet.append_row([str(date.today()), date.today().strftime("%Y-%m"), "Receita", "Cliente", desc, val, 1, 1, "Receita"])
            st.success("Salvo!")
            st.cache_data.clear()

def pagina_gestor():
    st.title("🛠️ Banco de Dados")
    df = pd.DataFrame(sheet.get_all_records())
    edit = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("Salvar Alterações"):
        sheet.clear(); sheet.append_row(edit.columns.tolist()); sheet.append_rows(edit.astype(str).values.tolist())
        st.success("Salvo!")

# --- MENU ---
st.sidebar.title("App V16 (Secure)")
if st.sidebar.button("🔒 Sair / Logout"):
    st.session_state.password_correct = False
    st.rerun()

menu = st.sidebar.radio("Navegação", ["Dashboard", "Lançar Despesa", "Lançar Investimento", "Lançar Lotes", "Lançar Receita", "Banco de Dados"])

if menu == "Dashboard": pagina_dashboard()
elif menu == "Lançar Despesa": pagina_lancar_despesas()
elif menu == "Lançar Investimento": pagina_lancar_investimento()
elif menu == "Lançar Lotes": pagina_lancar_lote()
elif menu == "Lançar Receita": pagina_lancar_receita()
elif menu == "Banco de Dados": pagina_gestor()