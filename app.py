import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image
import io
import numpy as np
import cv2

# --- Configuração da Página ---
st.set_page_config(page_title="Reconhecimento Facial", layout="wide", initial_sidebar_state="collapsed")

# --- CSS FORÇADO PARA TELA CHEIA MOBILE ---
st.markdown("""
<style>
    /* Remove margens extras do Streamlit no topo para ganhar espaço */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    /* FORÇA O VÍDEO A OCUPAR 100% DA LARGURA DISPONÍVEL */
    div[data-testid="stCameraInput"] {
        width: 100% !important;
    }

    div[data-testid="stCameraInput"] video {
        width: 100% !important;
        height: auto !important; /* Mantém a proporção correta */
        object-fit: cover;
        border-radius: 12px;
    }

    /* MÁSCARA TOTALMENTE RESPONSIVA (Sem tamanho fixo) */
    div[data-testid="stCameraInput"]::after {
        content: ""; 
        position: absolute; 
        top: 50%; 
        left: 50%; 
        transform: translate(-50%, -50%);
        
        /* A máscara ocupará 85% da largura DO VÍDEO, seja ele qual for */
        width: 85%;
        /* A altura se ajusta automaticamente para manter o formato de rosto */
        aspect-ratio: 0.8; 
        
        /* Formato Squircle (Quadrado arredondado) */
        border: 4px dashed rgba(255, 255, 255, 0.8); 
        border-radius: 45%; 
        
        /* Sombra escura ao redor */
        box-shadow: 0 0 0 100vmax rgba(0, 0, 0, 0.7); 
        
        pointer-events: none; 
        z-index: 10;
    }
    
    /* Botão de tirar foto */
    div[data-testid="stCameraInput"] button { 
        z-index: 20; 
        position: relative; 
        border-radius: 50%;
        width: 60px;
        height: 60px;
        border: 3px solid white;
    }
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

# --- Estados da Sessão ---
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = None
if 'foto_atual' not in st.session_state:
    st.session_state['foto_atual'] = None

# --- Funções de Processamento ---

def processar_imagem_aula(image, target_size=(200, 250)):
    img_gray = image.convert('L')
    img_resized = img_gray.resize(target_size)
    img_array = np.array(img_resized, dtype=np.int16)
    return img_array, img_resized

def calcular_diferenca_aula(img_usuario_array, img_banco_array):
    diferenca_abs = np.abs(img_banco_array - img_usuario_array)
    score_diferenca = np.sum(diferenca_abs)
    return score_diferenca

def calcular_similaridade_percentual(diferenca_score):
    # AJUSTE DE SENSIBILIDADE
    # Reduzi de 12.000.000 para 8.000.000. 
    # Isso torna o sistema mais "rigoroso", baixando a nota das fotos diferentes
    # e aumentando a distância entre o que é parecido e o que não é.
    max_diferenca_aceitavel = 8000000.0 
    
    porcentagem = (1 - (diferenca_score / max_diferenca_aceitavel)) * 100
    return max(0.0, min(100.0, porcentagem))

def encontrar_matches(foto_usuario_pil):
    resultados = []
    array_usuario, img_usuario_processada = processar_imagem_aula(foto_usuario_pil)
    
    todos_arquivos = list(fs.find())
    total = len(todos_arquivos)
    
    if total == 0: return [], img_usuario_processada

    progresso = st.progress(0)
    
    for i, grid_out in enumerate(todos_arquivos):
        try:
            bytes_img = grid_out.read()
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
            
        except Exception:
            continue
        
        if i % 5 == 0: progresso.progress((i + 1) / total)
    
    progresso.empty()
    resultados_ordenados = sorted(resultados, key=lambda x: x['porcentagem'], reverse=True)
    return resultados_ordenados, img_usuario_processada

def salvar_no_banco(nome, imagem_pil):
    try:
        buffer = io.BytesIO()
        imagem_pil.save(buffer, format='JPEG', quality=95)
        fs.put(buffer.getvalue(), filename=f"{nome}.jpg")
        st.toast(f"Salvo: {nome}.jpg", icon="💾")
        st.cache_resource.clear()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- Interface ---

# Layout de Coluna única no topo para a câmera (Melhor para mobile)
col_cam = st.container()

with col_cam:
    foto = st.camera_input("Tire a foto", label_visibility="collapsed")
    
    if foto:
        img_original = Image.open(foto)
        
        # Recorte Central Simples
        w, h = img_original.size
        target_ratio = 200/250
        current_ratio = w/h
        if current_ratio > target_ratio:
            new_w = h * target_ratio
            left = (w - new_w)/2
            img_crop = img_original.crop((left, 0, left + new_w, h))
        else:
            img_crop = img_original
            
        with st.spinner("Analisando biometria..."):
            matches, img_proc = encontrar_matches(img_crop)
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc

# Resultados abaixo da câmera
if st.session_state['foto_atual']:
    st.divider()
    
    # Abas para separar Cadastro de Busca
    tab1, tab2 = st.tabs(["📊 Resultados", "💾 Salvar Nova"])
    
    with tab1:
        res = st.session_state['resultados']
        if res:
            # Controles simplificados
            c1, c2 = st.columns([2, 1])
            with c1: ordem = st.selectbox("Ordenar por:", ["Mais Parecidas", "Menos Parecidas"])
            with c2: qtde = st.selectbox("Qtd:", [3, 6, 9], index=0)
            
            lista_final = res[:qtde] if "Mais" in ordem else res[-qtde:][::-1]
            
            cols = st.columns(3) # Sempre 3 por linha, quebra automático no mobile
            for i, item in enumerate(lista_final):
                with cols[i % 3]:
                    st.image(item['imagem'], use_container_width=True)
                    
                    pct = item['porcentagem']
                    
                    # NOVA REGRA DE CORES
                    if pct >= 60: 
                        cor = "green"
                    else: 
                        cor = "red"
                    
                    st.markdown(f"<h4 style='text-align:center; color:{cor}; margin:0;'>{pct:.0f}%</h4>", unsafe_allow_html=True)
                    st.caption(f"{item['filename']}")
        else:
            st.info("Nenhum resultado.")

    with tab2:
        col_img, col_form = st.columns([1, 2])
        with col_img:
            st.image(st.session_state['foto_atual'], caption="Sua Foto", use_container_width=True)
        with col_form:
            with st.form("save"):
                nome = st.text_input("Nome:")
                if st.form_submit_button("Salvar no Banco", use_container_width=True):
                    if nome: salvar_no_banco(nome, st.session_state['foto_atual'])
                    else: st.warning("Digite um nome.")