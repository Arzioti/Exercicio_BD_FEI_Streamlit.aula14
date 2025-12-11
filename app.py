import os
import gridfs
from pymongo import MongoClient
from PIL import Image
import io

# --- CONFIGURAÇÃO ---
# Coloque aqui o caminho da pasta onde estão as imagens descompactadas
# Exemplo Windows: r"C:\Users\Antonio\Downloads\frontalimages_manuallyaligned_part1"
# Exemplo Linux/Mac: "/home/user/downloads/fei_database"
# Se deixar como ".", ele vai procurar na mesma pasta do arquivo.
PASTA_IMAGENS = "." 

# Conexão com o MongoDB Atlas
# (Sua string de conexão já está configurada aqui)
uri = "mongodb+srv://antoniocjunior61_db_user:MP86bA8RrKUcVwc0@cluster0.xnstoor.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(uri)
    db = client['midias']
    fs = gridfs.GridFS(db)
    # Teste de conexão
    client.admin.command('ping')
    print("Conectado ao MongoDB com sucesso!")
except Exception as e:
    print(f"Erro ao conectar: {e}")
    exit()

# --- LIMPEZA (OPCIONAL) ---
# Descomente as linhas abaixo se quiser apagar tudo antes de subir de novo
# print("Limpando banco antigo...")
# for f in fs.find():
#     fs.delete(f._id)
# print("Banco limpo.")

# --- UPLOAD ---
# Verifica se a pasta existe
if not os.path.exists(PASTA_IMAGENS):
    print(f"ERRO: A pasta '{PASTA_IMAGENS}' não foi encontrada.")
    exit()

# Listar os arquivos .jpg na pasta especificada
imagens = [f for f in os.listdir(PASTA_IMAGENS) if f.lower().endswith('.jpg')]

print(f"Total de imagens encontradas na pasta: {len(imagens)}")

if len(imagens) == 0:
    print("Nenhuma imagem .jpg encontrada. Verifique o caminho da pasta.")
else:
    print("Iniciando upload...")
    
    count = 0
    for nome_arquivo in imagens:
        # Cria o caminho completo (Pasta + Nome do Arquivo)
        caminho_completo = os.path.join(PASTA_IMAGENS, nome_arquivo)
        
        try:
            with open(caminho_completo, 'rb') as f:
                # O filename no banco será apenas o nome do arquivo (ex: 1a.jpg), não o caminho todo
                file_id = fs.put(f, filename=nome_arquivo)
                count += 1
                if count % 10 == 0:
                    print(f"Enviado {count}/{len(imagens)}: {nome_arquivo}")
        except Exception as e:
            print(f"Erro ao enviar {nome_arquivo}: {e}")

    print(f"\nSucesso! {count} imagens foram enviadas para o MongoDB.")