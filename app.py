import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# Configuração da página
st.set_page_config(page_title="Verificador de Eliminação", layout="wide")

st.title("🕵️ Verificador de Datas de Eliminação")
st.markdown("""
Esta ferramenta cruza dados de um Relatório PDF com uma Tabela de Temporalidade (Excel) 
para validar se as datas de eliminação foram calculadas corretamente.
""")

# --- FUNÇÕES DE LÓGICA ---

def extract_data_from_pdf(pdf_file):
    """Extrai dados do PDF usando a lógica de regex fornecida."""
    dados = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            linhas = text.split('\n')
            
            for linha in linhas:
                # Regex para capturar Código
                match_codigo = re.match(r'^(\d\.\d\.\d{2}\.\d{2}\.\d{2})\s+', linha)
                
                if match_codigo:
                    codigo = match_codigo.group(1)
                    partes = linha.split()
                    
                    # Encontrar anos (19xx ou 20xx)
                    anos_encontrados = []
                    for parte in partes:
                        if re.match(r'^(19|20)\d{2}$', parte):
                            anos_encontrados.append(int(parte))
                    
                    data_limite_ini = None
                    data_limite_fim = None
                    elim_prevista_ini = None
                    elim_prevista_fim = None
                    
                    # Lógica de extração de intervalos baseada na presença de "ATÉ"
                    # Simplificada para robustez: assume-se pares lógicos
                    linha_upper = linha.upper()
                    tem_ate = "ATÉ" in linha_upper
                    
                    if len(anos_encontrados) >= 2:
                        if tem_ate and len(anos_encontrados) >= 4:
                            # 2010 ATÉ 2012 ... 2015 ATÉ 2017
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[1]
                            elim_prevista_ini = anos_encontrados[2]
                            elim_prevista_fim = anos_encontrados[3]
                        elif tem_ate and len(anos_encontrados) >= 3:
                             # Caso raro ou erro de leitura, tenta pegar o que der
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[1]
                            elim_prevista_ini = anos_encontrados[2]
                            elim_prevista_fim = anos_encontrados[2]
                        elif not tem_ate and len(anos_encontrados) >= 2:
                            # 2010 ... 2015 (Datas únicas)
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[0]
                            elim_prevista_ini = anos_encontrados[1]
                            elim_prevista_fim = anos_encontrados[1]

                    # Captura da Especificação (importante para o código 2.0.10.00.01)
                    # Pega tudo que vem depois do código e antes dos anos, ou no final
                    # Essa regex tenta capturar texto descritivo
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
    """Calcula a data correta baseada no Excel de regras."""
    codigo = row['COD_PDF']
    espec = row['ESPEC_PDF']
    
    # Filtrar regra pelo código
    regras_filtradas = regras_df[regras_df['COD'].astype(str) == codigo]
    
    if regras_filtradas.empty:
        return "Código não encontrado na Tabela Excel", None, None
    
    regra_selecionada = None
    
    # Lógica Especial para 2.0.10.00.01
    if codigo == '2.0.10.00.01':
        # Tenta encontrar correspondência parcial na especificação
        # Ex: Se Excel diz "Histórico Escolar" e PDF diz "EMEF x - Histórico Escolar"
        for _, regra in regras_filtradas.iterrows():
            espec_regra = str(regra['ESPEC']).upper()
            if espec_regra in espec.upper() or espec.upper() in espec_regra:
                regra_selecionada = regra
                break
        # Se não achou match exato de texto, pega o primeiro ou avisa (aqui pegamos o primeiro por fallback)
        if regra_selecionada is None:
             regra_selecionada = regras_filtradas.iloc[0]
             status_msg = "⚠ Código 2.0.10.00.01: Usada regra padrão (verificar especificação)"
    else:
        # Pega a primeira ocorrência (assumindo códigos únicos exceto o caso acima)
        regra_selecionada = regras_filtradas.iloc[0]

    prazo = regra_selecionada['ELIM']
    
    # Verifica se o prazo é numérico
    try:
        anos_adicionar = int(prazo)
        
        # Cálculo
        calc_ini = row['LIMITE_INI'] + anos_adicionar
        calc_fim = row['LIMITE_FIM'] + anos_adicionar
        
        status = "OK"
        if calc_ini != row['ELIM_PDF_INI'] or calc_fim != row['ELIM_PDF_FIM']:
            status = "ERRO"
            
        return status, calc_ini, calc_fim
        
    except ValueError:
        # Prazo não é número (ex: "PERMANENTE", "GUARDA", etc)
        # Se for texto, a data de eliminação no PDF deveria ser igual ou refletir esse texto?
        # A regra diz: "informe isto para o usuário".
        return f"Informativo: Prazo é '{prazo}'", None, None

# --- INTERFACE ---

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Tabela de Regras (Excel)")
    file_excel = st.file_uploader("Upload Excel (Colunas: COD, ESPEC, ELIM)", type=["xlsx", "xls"])

with col2:
    st.subheader("2. Relatório (PDF)")
    file_pdf = st.file_uploader("Upload Relatório de Eliminação", type=["pdf"])

if file_excel and file_pdf:
    st.info("Processando arquivos...")
    
    # 1. Carregar Excel
    try:
        df_regras = pd.read_excel(file_excel)
        # Normalizar colunas
        cols_upper = [c.upper() for c in df_regras.columns]
        df_regras.columns = cols_upper
        
        # Verificar se as colunas existem
        if not all(col in df_regras.columns for col in ['COD', 'ESPEC', 'ELIM']):
            st.error("O Excel precisa ter as colunas: COD, ESPEC, ELIM")
            st.stop()
            
    except Exception as e:
        st.error(f"Erro ao ler Excel: {e}")
        st.stop()

    # 2. Processar PDF
    try:
        df_pdf = extract_data_from_pdf(file_pdf)
        if df_pdf.empty:
            st.warning("Nenhum dado encontrado no PDF com o padrão esperado.")
            st.stop()
        else:
            st.success(f"{len(df_pdf)} registros extraídos do PDF.")
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        st.stop()

    # 3. Validação
    resultados = []
    
    progress_bar = st.progress(0)
    total_rows = len(df_pdf)
    
    for idx, row in df_pdf.iterrows():
        status, correto_ini, correto_fim = calcular_correto(row, df_regras)
        
        # Adicionar ao relatório final apenas erros ou informativos
        if status != "OK":
            resultados.append({
                'CÓDIGO': row['COD_PDF'],
                'ESPECIFICAÇÃO (PDF)': row['ESPEC_PDF'],
                'LIMITE INICIAL': row['LIMITE_INI'],
                'LIMITE FINAL': row['LIMITE_FIM'],
                'ELIMINAÇÃO NO PDF': f"{row['ELIM_PDF_INI']} a {row['ELIM_PDF_FIM']}",
                'STATUS': status,
                'DATA CORRETA ESPERADA': f"{correto_ini} a {correto_fim}" if correto_ini else "N/A"
            })
        
        progress_bar.progress((idx + 1) / total_rows)

    # 4. Exibição dos Resultados
    st.divider()
    st.subheader("Resultados da Análise")
    
    if resultados:
        df_resultado = pd.DataFrame(resultados)
        
        # Estilizar tabela
        st.dataframe(df_resultado, use_container_width=True)
        
        # Botão de download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_resultado.to_excel(writer, index=False, sheet_name='Erros_Encontrados')
            
        st.download_button(
            label="📥 Baixar Relatório de Erros (Excel)",
            data=buffer,
            file_name="Relatorio_Correcao_Datas.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.success("✅ Parabéns! Nenhuma inconsistência encontrada. Todas as datas estão corretas.")