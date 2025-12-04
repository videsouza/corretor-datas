import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Validador de Eliminação Pro",
    page_icon="fas fa-cubes",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS PERSONALIZADO (A MÁGICA DO DESIGN) ---
# Aqui replicamos o estilo do seu arquivo HTML dentro do Streamlit
st.markdown("""
    <style>
        /* Importar fontes e ícones */
        @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css');

        /* Fundo Geral */
        .stApp {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Segoe UI', sans-serif;
        }

        /* Container Principal (Simulando o .container do HTML) */
        .main-container {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin: 20px auto;
        }

        /* Header Estilizado */
        .header-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .header-box h1 { font-size: 32px; font-weight: 700; margin: 0; padding-bottom: 10px; }
        .header-box p { opacity: 0.9; font-size: 16px; margin: 0; }

        /* Cards (Upload e Resultados) */
        .css-card {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            padding: 25px;
            margin-bottom: 25px;
            border: 1px solid #e2e8f0;
        }
        
        /* Estilização dos Uploaders do Streamlit para parecerem a área pontilhada */
        div[data-testid="stFileUploader"] {
            border: 2px dashed #cbd5e0;
            border-radius: 15px;
            padding: 20px;
            background: #f8fafc;
            text-align: center;
        }
        div[data-testid="stFileUploader"]:hover {
            border-color: #667eea;
            background: #eef2ff;
        }

        /* KPIs Customizados (Cards coloridos) */
        .kpi-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            border-left: 5px solid #667eea;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            text-align: left;
        }
        .kpi-title { font-size: 12px; text-transform: uppercase; color: #64748b; font-weight: 700; }
        .kpi-value { font-size: 28px; font-weight: 800; color: #1e293b; margin-top: 5px; }
        
        /* Botões */
        div.stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            padding: 0.5rem 1rem;
            width: 100%;
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            color: white;
        }

        /* Remover elementos padrão do Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA (BACKEND) ---

def extract_data_from_pdf(pdf_file):
    dados = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            linhas = text.split('\n')
            for linha in linhas:
                match_codigo = re.match(r'^(\d\.\d\.\d{2}\.\d{2}\.\d{2})\s+', linha)
                if match_codigo:
                    codigo = match_codigo.group(1)
                    partes = linha.split()
                    anos_encontrados = []
                    for parte in partes:
                        if re.match(r'^(19|20)\d{2}$', parte):
                            anos_encontrados.append(int(parte))
                    
                    data_limite_ini = None
                    data_limite_fim = None
                    elim_prevista_ini = None
                    elim_prevista_fim = None
                    
                    linha_upper = linha.upper()
                    tem_ate = "ATÉ" in linha_upper
                    
                    if len(anos_encontrados) >= 2:
                        if tem_ate and len(anos_encontrados) >= 4:
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[1]
                            elim_prevista_ini = anos_encontrados[2]
                            elim_prevista_fim = anos_encontrados[3]
                        elif tem_ate and len(anos_encontrados) >= 3:
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[1]
                            elim_prevista_ini = anos_encontrados[2]
                            elim_prevista_fim = anos_encontrados[2]
                        elif not tem_ate and len(anos_encontrados) >= 2:
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[0]
                            elim_prevista_ini = anos_encontrados[1]
                            elim_prevista_fim = anos_encontrados[1]

                    obs_match = re.search(r'(SE -.*|EMEI.*|EMEF.*|IMI.*|NEI.*|CECOI.*|CENTRO.*|SECRETARIA.*)', linha)
                    especificacao = obs_match.group(1).strip() if obs_match else ""

                    if elim_prevista_ini:
                        dados.append({
                            'COD_PDF': codigo,
                            'ESPEC_PDF': especificacao,
                            'LIMITE_INI': data_limite_ini,
                            'LIMITE_FIM': data_limite_fim,
                            'ELIM_PDF_INI': elim_prevista_ini,
                            'ELIM_PDF_FIM': elim_prevista_fim,
                            'LINHA_ORIGINAL': linha
                        })
    return pd.DataFrame(dados)

def calcular_correto(row, regras_df):
    codigo = row['COD_PDF']
    espec = row['ESPEC_PDF']
    regras_filtradas = regras_df[regras_df['COD'].astype(str) == codigo]
    
    if regras_filtradas.empty:
        return "Código não encontrado no Excel", None, None
    
    regra_selecionada = None
    if codigo == '2.0.10.00.01':
        for _, regra in regras_filtradas.iterrows():
            espec_regra = str(regra['ESPEC']).upper()
            if espec_regra in espec.upper() or espec.upper() in espec_regra:
                regra_selecionada = regra
                break
        if regra_selecionada is None:
             regra_selecionada = regras_filtradas.iloc[0]
    else:
        regra_selecionada = regras_filtradas.iloc[0]

    prazo = regra_selecionada['ELIM']
    try:
        anos_adicionar = int(prazo)
        calc_ini = row['LIMITE_INI'] + anos_adicionar
        calc_fim = row['LIMITE_FIM'] + anos_adicionar
        
        status = "OK"
        if calc_ini != row['ELIM_PDF_INI'] or calc_fim != row['ELIM_PDF_FIM']:
            status = "ERRO"
        return status, calc_ini, calc_fim
    except ValueError:
        return f"Informativo: Prazo é '{prazo}'", None, None

# --- LAYOUT VISUAL ---

# Wrapper branco centralizado (simulando .container do HTML)
with st.container():
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    # 1. Header
    st.markdown("""
        <div class="header-box">
            <h1><i class="fas fa-file-shield"></i> Verificador de Datas de Eliminação</h1>
            <p>Auditoria automatizada de editais baseada na Tabela de Temporalidade</p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Área de Upload (Estilo Card)
    st.markdown('<div class="css-card"><h2>📂 Arquivos de Entrada</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**1. Tabela Temporalidade (Excel)**")
        file_excel = st.file_uploader("Arraste o Excel aqui (COD, ESPEC, ELIM)", type=["xlsx", "xls"], key="excel")
    
    with col2:
        st.markdown("**2. Relatório de Eliminação (PDF)**")
        file_pdf = st.file_uploader("Arraste o PDF aqui", type=["pdf"], key="pdf")

    st.markdown('</div>', unsafe_allow_html=True) # Fecha Card Upload

    # 3. Lógica e Resultados
    if file_excel and file_pdf:
        # Processamento (com spinner nativo, mas visual limpo)
        with st.spinner("🔄 Cruzando dados e validando datas..."):
            try:
                # Ler Excel
                df_regras = pd.read_excel(file_excel)
                df_regras.columns = [c.upper() for c in df_regras.columns]
                
                # Ler PDF
                df_pdf = extract_data_from_pdf(file_pdf)
                
                if df_pdf.empty:
                    st.error("❌ Nenhum dado compatível encontrado no PDF.")
                else:
                    # Validar
                    resultados = []
                    erros_count = 0
                    
                    for idx, row in df_pdf.iterrows():
                        status_calc, c_ini, c_fim = calcular_correto(row, df_regras)
                        if status_calc != "OK":
                            erros_count += 1
                            resultados.append({
                                'CÓDIGO': row['COD_PDF'],
                                'ESPECIFICAÇÃO': row['ESPEC_PDF'],
                                'LIMITE': f"{row['LIMITE_INI']} - {row['LIMITE_FIM']}",
                                'NO PDF': f"{row['ELIM_PDF_INI']} - {row['ELIM_PDF_FIM']}",
                                'STATUS': status_calc,
                                'CORRETO': f"{c_ini} - {c_fim}" if c_ini else "N/A"
                            })
                    
                    # 4. Dashboard de Resultados (Visual HTML)
                    st.markdown('<div class="css-card"><h2>📊 Relatório da Análise</h2>', unsafe_allow_html=True)
                    
                    # KPIs em Grid HTML
                    cor_borda = "#ef4444" if erros_count > 0 else "#10b981"
                    texto_erro = "Atenção Requerida" if erros_count > 0 else "Tudo Certo"
                    
                    kpi_html = f"""
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px;">
                        <div class="kpi-card" style="border-left-color: #667eea;">
                            <div class="kpi-title">Total Analisado</div>
                            <div class="kpi-value">{len(df_pdf)}</div>
                        </div>
                        <div class="kpi-card" style="border-left-color: {cor_borda};">
                            <div class="kpi-title">Inconsistências</div>
                            <div class="kpi-value">{erros_count}</div>
                            <div style="font-size: 12px; color: {cor_borda}; font-weight: bold;">{texto_erro}</div>
                        </div>
                        <div class="kpi-card" style="border-left-color: #f59e0b;">
                            <div class="kpi-title">Precisão</div>
                            <div class="kpi-value">{((len(df_pdf)-erros_count)/len(df_pdf)*100):.1f}%</div>
                        </div>
                    </div>
                    """
                    st.markdown(kpi_html, unsafe_allow_html=True)
                    
                    # Tabela e Download
                    if erros_count > 0:
                        df_resultado = pd.DataFrame(resultados)
                        st.dataframe(df_resultado, use_container_width=True)
                        
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            df_resultado.to_excel(writer, index=False)
                        
                        st.download_button(
                            label="📥 BAIXAR RELATÓRIO DE ERROS (EXCEL)",
                            data=buffer,
                            file_name="Datas_Incorretas.xlsx",
                            mime="application/vnd.ms-excel"
                        )
                    else:
                        st.success("✅ Tudo perfeito! O relatório PDF está 100% correto segundo a tabela.")

                    st.markdown('</div>', unsafe_allow_html=True) # Fecha Card Resultados

            except Exception as e:
                st.error(f"Ocorreu um erro no processamento: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True) # Fecha Main Container
