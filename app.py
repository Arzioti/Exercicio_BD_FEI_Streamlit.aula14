import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image
import io
import numpy as np
import cv2

# --- Configuração da Página (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
st.set_page_config(page_title="Reconhecimento Facial", layout="wide", initial_sidebar_state="collapsed")

# --- CSS SUPREMO PARA MOBILE (CORRIGIDO V9 - CENTRO PERFEITO + RESULTADOS VISUAIS) ---
st.markdown("""
<style>
    /* 1. RESET TOTAL DA PÁGINA */
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    header, footer, #MainMenu { display: none !important; }
    
    .stApp {
        background-color: black;
    }

    /* 2. ESTILOS DO MODO CÂMERA (FIXO E GIGANTE) */
    
    div[data-testid="stCameraInput"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 10 !important;
        background-color: black !important;
    }

    div[data-testid="stCameraInput"] > div {
        width: 100% !important;
        height: 100% !important;
        aspect-ratio: unset !important;
    }

    div[data-testid="stCameraInput"] video {
        width: 100% !important;
        height: 100% !important;
        min-height: 100vh !important;
        min-width: 100vw !important;
        object-fit: cover !important; /* Zoom para preencher */
    }

    /* MÁSCARA GUIA (AGORA EXATAMENTE NO CENTRO 50%) */
    div[data-testid="stCameraInput"]::after {
        content: ""; 
        position: absolute; 
        top: 50%; /* Centralizado verticalmente */
        left: 50%; /* Centralizado horizontalmente */
        transform: translate(-50%, -50%);
        width: 60vw; /* Um pouco menor para forçar o usuário a se aproximar */
        height: 40vh; 
        border: 4px dashed rgba(255, 255, 255, 0.7); 
        border-radius: 50%; 
        box-shadow: 0 0 0 100vmax rgba(0, 0, 0, 0.7); /* Sombra mais escura */
        pointer-events: none; 
        z-index: 20; 
    }

    /* Botão de Captura */
    div[data-testid="stCameraInput"] button { 
        position: absolute !important; 
        bottom: 8vh !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 30 !important; 
        width: 80px !important; 
        height: 80px !important;
        border-radius: 50% !important;
        background-color: #ff4444 !important;
        border: 4px solid white !important;
        color: transparent !important;
    }
    
    /* 3. ESTILOS DO MODO RESULTADO */
    
    .resultados-wrapper {
        background-color: #0e1117;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 20px;
    }
    
    /* Estilo para a imagem analisada (Sua Foto) */
    .img-analisada {
        border: 2px solid #00ff00;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 0 20px rgba(0, 255, 0, 0.2);
    }
    
    .titulo-secao {
        color: white;
        font-size: 1.2rem;
        margin: 10px 0;
        text-align: center;
        width: 100%;
        border-bottom: 1px solid #333;
        padding-bottom: 5px;
    }

    /* Esconde textos pequenos */
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
    # === TELA 1: CÂMERA ===
    
    foto = st.camera_input("Tire a foto", label_visibility="collapsed", key=f"cam_{st.session_state.camera_key}")
    
    if foto:
        st.markdown("""<style>div[data-testid="stCameraInput"] { display: none !important; }</style>""", unsafe_allow_html=True)
        
        with st.status("🔍 Processando biometria...", expanded=True) as status:
            img_original = Image.open(foto)
            
            # Crop Inteligente - CENTRO EXATO (50%)
            # Isso garante que o que estava na máscara (que está no centro) seja capturado
            w, h = img_original.size
            target_ratio = 200/250
            current_ratio = w/h
            
            if current_ratio > target_ratio:
                new_w = h * target_ratio
                left = (w - new_w)/2
                img_crop = img_original.crop((left, 0, left + new_w, h))
            else:
                new_h = w / target_ratio
                top = (h - new_h)/2
                img_crop = img_original.crop((0, top, w, top + new_h))
            
            matches, img_proc = encontrar_matches(img_crop)
            
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc # Esta é a imagem P&B Redimensionada
            
            status.update(label="Pronto!", state="complete", expanded=False)
            
        st.rerun()

else:
    # === TELA 2: RESULTADOS (VISUALIZAÇÃO LIMPA) ===
    
    st.markdown("""
        <style>
            div[data-testid="stCameraInput"] { display: none !important; }
            .stApp { background-color: #0e1117 !important; }
        </style>
    """, unsafe_allow_html=True)

    # 1. MOSTRA A FOTO QUE FOI ANALISADA (EM CIMA, GRANDE)
    st.markdown("<h3 style='text-align: center; color: white;'>Biometria Capturada</h3>", unsafe_allow_html=True)
    
    # Coluna centralizada para a foto
    c_img1, c_img2, c_img3 = st.columns([1, 2, 1])
    with c_img2:
        # Mostra a imagem processada (P&B, 200x250)
        st.image(st.session_state['foto_atual'], caption="Proporção Análise (200x250)", use_container_width=True)
    
    st.divider()
    
    # 2. MATCHES ENCONTRADOS
    st.markdown("<h4 style='color: white;'>🔍 Similares no Banco</h4>", unsafe_allow_html=True)
    
    res = st.session_state['resultados']
    if res:
        # Carrossel ou Grid de resultados
        cols = st.columns(3)
        for i, item in enumerate(res[:3]): # Mostra top 3 direto
            with cols[i % 3]:
                st.image(item['imagem'], use_container_width=True)
                pct = item['porcentagem']
                cor = "#00ff00" if pct >= 60 else "#ff4444"
                st.markdown(f"<div style='text-align:center; color:{cor}; font-weight:bold;'>{pct:.0f}%</div>", unsafe_allow_html=True)
    else:
        st.info("Nenhuma imagem no banco.")

    st.divider()

    # 3. OPÇÕES (SALVAR / TENTAR DE NOVO)
    c_btn1, c_btn2 = st.columns(2)
    
    with c_btn1:
        if st.button("🔄 Nova Foto", use_container_width=True):
            resetar_app()
            
    with c_btn2:
        # Popover para salvar (para não ocupar espaço na tela principal)
        with st.popover("💾 Salvar Esta", use_container_width=True):
            nome_input = st.text_input("Nome:")
            if st.button("Confirmar Salvar"):
                if nome_input:
                    salvar_no_banco(nome_input, st.session_state['foto_atual'])
                else:
                    st.warning("Digite um nome.")