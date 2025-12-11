import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image, ImageOps
import io
import numpy as np
import cv2

# --- Configuração da Página (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
st.set_page_config(page_title="Reconhecimento Facial", layout="wide", initial_sidebar_state="collapsed")

# --- CSS SUPREMO PARA MOBILE (CORRIGIDO V11 - ANTI-RESIZE STREAMLIT) ---
st.markdown("""
<style>
    /* 1. RESET E ESTRUTURA BASE */
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
        overflow: hidden !important; /* Evita barras de rolagem na tela da câmera */
    }
    
    header, footer, #MainMenu { display: none !important; }
    
    .stApp {
        background-color: black;
    }

    /* 2. CÂMERA FULL SCREEN (CORREÇÃO DO BUG 3/4) */
    
    /* Container Raiz da Câmera: Fixado para ocupar tudo */
    div[data-testid="stCameraInput"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 10 !important;
        background-color: black !important;
    }

    /* Container Interno (Onde o Streamlit tenta mexer na altura) */
    div[data-testid="stCameraInput"] > div {
        height: 100vh !important; /* Força 100% da altura da viewport */
        width: 100vw !important;
        padding-bottom: 0 !important; /* Remove o padding que cria a barra preta */
        aspect-ratio: unset !important; /* Ignora proporção 4:3 */
    }

    /* O Vídeo em si */
    div[data-testid="stCameraInput"] video {
        width: 100% !important;
        height: 100% !important;
        object-fit: cover !important; /* Preenche sem distorcer */
        object-position: center !important; /* Centraliza */
    }

    /* 3. MÁSCARA GUIA (AJUSTADA) */
    div[data-testid="stCameraInput"]::after {
        content: ""; 
        position: absolute; 
        top: 50%; 
        left: 50%; 
        transform: translate(-50%, -50%);
        width: 250px; /* Tamanho fixo em px para ser consistente em qualquer tela */
        height: 330px; 
        border: 3px dashed rgba(255, 255, 255, 0.8); 
        border-radius: 50%; 
        box-shadow: 0 0 0 999vmax rgba(0, 0, 0, 0.7); /* Escurece bastante o fundo */
        pointer-events: none; 
        z-index: 20; 
    }

    /* 4. BOTÃO DE CAPTURA (ALINHADO EM BAIXO) */
    div[data-testid="stCameraInput"] button { 
        position: absolute !important; 
        bottom: 40px !important; /* Fixo em pixels da base */
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 30 !important; 
        width: 70px !important; 
        height: 70px !important;
        border-radius: 50% !important;
        background-color: #ff4444 !important;
        border: 4px solid white !important;
        color: transparent !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
    
    /* 5. MODO RESULTADO (ESTILO LIMPO) */
    .resultados-wrapper {
        background-color: #0e1117;
        min-height: 100vh;
        padding: 20px;
        padding-top: 40px;
        display: flex;
        flex-direction: column;
        align-items: center;
        overflow-y: auto !important; /* Permite rolar nos resultados */
    }
    
    /* Customização dos Radio Buttons e Selectbox para fundo escuro */
    .stRadio label, .stSelectbox label {
        color: white !important;
    }
    
    /* Esconde textos auxiliares */
    small { display: none !important; }
    
</style>
""", unsafe_allow_html=True)

# --- Conexão MongoDB ---
URI = "mongodb+srv://antoniocjunior61_db_user:MP86bA8RrKUcVwc0@cluster0.xnstoor.mongodb.net/?appName=Cluster0"

@st.cache_resource
def init_connection():
    try:
        client = MongoClient(URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        return client
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

client = init_connection()

if client:
    db = client['midias']
    fs = gridfs.GridFS(db)
else:
    st.stop()

# --- Gerenciamento de Estado ---

if 'camera_key' not in st.session_state:
    st.session_state.camera_key = 0
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = None
if 'foto_atual' not in st.session_state:
    st.session_state['foto_atual'] = None

def resetar_app():
    """Limpa os resultados e reinicia a câmera"""
    st.session_state['resultados'] = None
    st.session_state['foto_atual'] = None
    st.session_state.camera_key += 1
    st.rerun()

# --- Funções de Processamento ---

def processar_imagem_aula(image, target_size=(200, 250)):
    # Converte para Cinza (L)
    img_gray = image.convert('L')
    # Redimensiona para o padrão do banco (200x250)
    img_resized = img_gray.resize(target_size)
    img_array = np.array(img_resized, dtype=np.int16)
    return img_array, img_resized

def calcular_diferenca_aula(img_usuario_array, img_banco_array):
    diferenca_abs = np.abs(img_banco_array - img_usuario_array)
    score_diferenca = np.sum(diferenca_abs)
    return score_diferenca

def calcular_similaridade_percentual(diferenca_score):
    max_diferenca_aceitavel = 8000000.0 
    porcentagem = (1 - (diferenca_score / max_diferenca_aceitavel)) * 100
    return max(0.0, min(100.0, porcentagem))

def encontrar_matches(foto_usuario_pil):
    resultados = []
    array_usuario, img_usuario_processada = processar_imagem_aula(foto_usuario_pil)
    
    try:
        todos_arquivos = list(fs.find())
        if not todos_arquivos:
            return [], img_usuario_processada
    except:
        return [], img_usuario_processada
    
    for grid_out in todos_arquivos:
        try:
            bytes_img = grid_out.read()
            if not bytes_img: continue
            img_banco_pil = Image.open(io.BytesIO(bytes_img))
            array_banco, img_banco_processada = processar_imagem_aula(img_banco_pil)
            diferenca = calcular_diferenca_aula(array_usuario, array_banco)
            porcentagem = calcular_similaridade_percentual(diferenca)
            resultados.append({
                'filename': grid_out.filename,
                'diferenca': diferenca,
                'porcentagem': porcentagem,
                'imagem': img_banco_processada
            })
        except:
            continue
            
    resultados_ordenados = sorted(resultados, key=lambda x: x['porcentagem'], reverse=True)
    return resultados_ordenados, img_usuario_processada

def salvar_no_banco(nome, imagem_pil):
    try:
        buffer = io.BytesIO()
        imagem_pil.save(buffer, format='JPEG', quality=95)
        fs.put(buffer.getvalue(), filename=f"{nome}.jpg")
        st.toast(f"Salvo: {nome}.jpg", icon="💾")
        import time
        time.sleep(1.5)
        resetar_app()
    except Exception as e:
        st.error(f"Erro: {e}")

# --- LÓGICA PRINCIPAL ---

if st.session_state['foto_atual'] is None:
    # === TELA 1: CÂMERA (FIXA E IMUTÁVEL) ===
    
    foto = st.camera_input("Tire a foto", label_visibility="collapsed", key=f"cam_{st.session_state.camera_key}")
    
    if foto:
        st.markdown("""<style>div[data-testid="stCameraInput"] { display: none !important; }</style>""", unsafe_allow_html=True)
        
        with st.status("🔍 Processando...", expanded=True) as status:
            img_original = Image.open(foto)
            img_original = ImageOps.exif_transpose(img_original)
            
            # Crop Fixo no Centro (Alinhado com a Máscara Visual)
            w, h = img_original.size
            
            # Força o crop no centro geométrico da imagem, 
            # pois o CSS forçou o vídeo a ficar no centro geométrico da tela.
            center_x, center_y = w/2, h/2
            
            # Define tamanho do crop proporcional ao alvo (200x250 -> 0.8)
            # Vamos pegar uma área que represente bem o rosto (aprox 60% da largura menor)
            crop_h = min(h, w / 0.8) * 0.7 
            crop_w = crop_h * 0.8
            
            left = center_x - (crop_w / 2)
            top = center_y - (crop_h / 2)
            right = center_x + (crop_w / 2)
            bottom = center_y + (crop_h / 2)
            
            img_crop = img_original.crop((left, top, right, bottom))
            
            matches, img_proc = encontrar_matches(img_crop)
            
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc 
            
            status.update(label="Pronto!", state="complete", expanded=False)
            
        st.rerun()

else:
    # === TELA 2: RESULTADOS (SCROLL LIBERADO) ===
    
    # Garante que a rolagem funcione aqui, sobrescrevendo o hidden do modo câmera
    st.markdown("""
        <style>
            .block-container { overflow: auto !important; }
            div[data-testid="stCameraInput"] { display: none !important; }
            .stApp { background-color: #0e1117 !important; }
        </style>
    """, unsafe_allow_html=True)

    # Wrapper para centralizar o conteúdo
    st.markdown("<div class='resultados-wrapper'>", unsafe_allow_html=True)
    
    st.markdown("<h3 style='color: white; margin-bottom: 20px; text-align: center;'>Resultado da Análise</h3>", unsafe_allow_html=True)
    
    # Imagem Capturada no Topo
    st.image(st.session_state['foto_atual'], caption="Sua Foto (Processada)", width=180)
    
    st.divider()
    
    # Matches
    res = st.session_state['resultados']
    if res:
        # --- FILTROS ADICIONADOS AQUI ---
        c_filtros1, c_filtros2 = st.columns([1, 1])
        with c_filtros1:
            qtde = st.selectbox("Quantidade:", [3, 6, 9, 12], index=0)
        with c_filtros2:
            ordem = st.radio("Mostrar:", ["Mais Parecidas", "Menos Parecidas"], horizontal=True)
        
        # Aplica o filtro
        if "Mais" in ordem:
            lista_final = res[:qtde]
        else:
            lista_final = res[-qtde:][::-1]
        
        # Mostra o Grid
        cols = st.columns(3)
        for i, item in enumerate(lista_final):
            with cols[i % 3]:
                st.image(item['imagem'], use_container_width=True)
                pct = item['porcentagem']
                cor = "#00ff00" if pct >= 60 else "#ff4444"
                st.markdown(f"<div style='text-align:center; color:{cor}; font-weight:bold; font-size: 1.2rem;'>{pct:.0f}%</div>", unsafe_allow_html=True)
                st.caption(f"{item['filename']}")
    else:
        st.info("Banco de dados vazio.")

    st.divider()

    # Botões de Ação
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Tentar Novamente", use_container_width=True, type="primary"):
            resetar_app()
    with c2:
        with st.popover("💾 Salvar Foto", use_container_width=True):
            nome = st.text_input("Nome da Pessoa:")
            if st.button("Confirmar Salvar"):
                if nome:
                    salvar_no_banco(nome, st.session_state['foto_atual'])
                else:
                    st.warning("Preencha o nome")
                    
    st.markdown("</div>", unsafe_allow_html=True)