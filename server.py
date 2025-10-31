import os
import json
import hashlib
import socket
import threading
import traceback
import google.genai as genai
import ctypes  
import sys
import time

HOST = '127.0.0.1'  
PORT = 65432        
DATABASE_FILE = "dados.json"

SERVER_RUNNING = True

C_LIB_LOADED = False
C_FUNCTION = None  

DLL_NAME = 'calculator.dll'
DLL_PATH = os.path.join(os.path.dirname(__file__), DLL_NAME)

try:
    import struct
    py_bits = struct.calcsize("P") * 8
    print(f"[CTYPES] Python arquitetura: {py_bits} bits")

    C_CALCULATOR = ctypes.CDLL(DLL_PATH)

    try:
        C_FUNCTION = C_CALCULATOR._calculate_final_grade
        C_FUNCTION.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
        C_FUNCTION.restype = ctypes.c_double
        C_LIB_LOADED = True
        print(f"[CTYPES] Biblioteca C ({DLL_NAME}) carregada com sucesso e função _calculate_final_grade vinculada.")
    except AttributeError:
        try:
            C_FUNCTION = C_CALCULATOR.calculate_final_grade
            C_FUNCTION.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
            C_FUNCTION.restype = ctypes.c_double
            C_LIB_LOADED = True
            print(f"[CTYPES] Biblioteca C ({DLL_NAME}) carregada com sucesso e função calculate_final_grade vinculada (sem underscore).")
        except AttributeError:
            C_FUNCTION = None
            C_LIB_LOADED = False
            print(f"[AVISO CTYPES] Função esperada não encontrada na DLL '{DLL_NAME}'. Verifique os símbolos exportados (esperado: _calculate_final_grade ou calculate_final_grade).")

except OSError as oe:
    C_LIB_LOADED = False
    C_FUNCTION = None
    print(f"[AVISO CTYPES] Falha ao carregar a biblioteca C (OSError). O código usará a lógica Python. Detalhe: {oe}")
except Exception as e:
    C_LIB_LOADED = False
    C_FUNCTION = None
    print(f"[AVISO CTYPES] Falha ao carregar a biblioteca C. O código usará a lógica Python. Erro: {e}")


def carregar_dados():
    default_data = {"alunos": {}, "professores": {}, "disciplinas": {}, "turmas": {}}

    if os.path.exists(DATABASE_FILE) and os.path.getsize(DATABASE_FILE) > 0:
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as arquivo:
                data = json.load(arquivo)
                return data if data else default_data
        except json.JSONDecodeError:
            print("AVISO NO SERVIDOR: Arquivo JSON corrompido. Inicializando com padrão.")
        except Exception as e:
            print(f"ERRO NO SERVIDOR ao carregar dados: {e}")

    return default_data

def salvar_dados(dados):
    with open(DATABASE_FILE, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=4, ensure_ascii=False)

def hash_senha(senha):
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()

def limpar_tela():
    if os.name == 'nt': 
        os.system('cls')
    else: 
        os.system('clear')

def cadastrar_turma_server(nome_turma):
    dados = carregar_dados()
    nome_turma = nome_turma.upper()
    if nome_turma in dados["turmas"]:
        return {"success": False, "message": "Essa turma já está cadastrada!"}

    dados["turmas"][nome_turma] = {"disciplinas": {}, "alunos": {}, "presenca": {}}
    salvar_dados(dados)
    return {"success": True, "message": f"Turma '{nome_turma}' cadastrada com sucesso!"}

def cadastrar_professor_server(cpf, nome, senha):
    dados = carregar_dados()
    if cpf in dados["professores"]:
        return {"success": False, "message": "Professor já cadastrado!"}

    dados["professores"][cpf] = {"nome": nome, "senha": hash_senha(senha)}
    salvar_dados(dados)
    return {"success": True, "message": f"Professor '{nome}' cadastrado com sucesso!"}

def get_cadastro_info(entity):
    dados = carregar_dados()
    if entity == "turmas":
        return list(dados["turmas"].keys())
    elif entity == "professores":
        return [{k: v['nome']} for k, v in dados["professores"].items()]
    return []

def cadastrar_disciplina_server(nome_disc, turma_escolhida, cpf_prof_escolhido):
    dados = carregar_dados()
    nome_disc = nome_disc.upper()

    chave_disciplina = f"{nome_disc}-{turma_escolhida}"

    if chave_disciplina in dados["disciplinas"]:
        return {"success": False, "message": f"A disciplina '{nome_disc}' já está cadastrada na turma '{turma_escolhida}'!"}

    if turma_escolhida not in dados["turmas"]:
        return {"success": False, "message": "Turma não encontrada!"}

    if cpf_prof_escolhido not in dados["professores"]:
        return {"success": False, "message": "Professor não encontrado!"}

    info_prof = dados["professores"][cpf_prof_escolhido]

    dados["disciplinas"][chave_disciplina] = {
        "professor": {"cpf": cpf_prof_escolhido, "nome": info_prof["nome"]},
        "turma": turma_escolhida,
        "nome_original": nome_disc,
        "atividades": {},
    }

    dados["turmas"][turma_escolhida]["disciplinas"][nome_disc] = {
        "professor": {"cpf": cpf_prof_escolhido, "nome": info_prof["nome"]},
        "atividades": {},
        "aulas": {} 
    }

    salvar_dados(dados)
    return {"success": True, "message": f"Disciplina '{nome_disc}' cadastrada na turma '{turma_escolhida}' com o professor '{info_prof['nome']}'."}

def cadastrar_aluno_server(ra, nome, senha, turma_escolhida):
    dados = carregar_dados()
    ra = ra.upper()
    nome = nome.upper()

    if ra in dados["alunos"]:
        return {"success": False, "message": "Aluno já cadastrado!"}
    if turma_escolhida not in dados["turmas"]:
        return {"success": False, "message": "Turma não encontrada!"}

    aluno_data = {
        "nome": nome,
        "senha": hash_senha(senha),
        "turma": turma_escolhida,
        "faltas": 0,
        "notas": {},
        "atividades_enviadas": {}
    }

    dados["alunos"][ra] = aluno_data
    dados["turmas"][turma_escolhida]["alunos"][ra] = {k: aluno_data[k] for k in ["nome", "faltas", "notas", "atividades_enviadas"]}

    salvar_dados(dados)
    return {"success": True, "message": f"Aluno '{nome}' cadastrado na turma '{turma_escolhida}'."}

def login_administrador_server(usuario, senha):
    if usuario == "admin" and senha == "admin123":
        return {"role": "admin"}
    else:
        return {"role": None, "message": "Acesso negado!"}

def login_professor_server(cpf, senha):
    dados = carregar_dados()
    if cpf not in dados["professores"]:
        return {"role": None, "message": "CPF não encontrado! Solicite seu cadastro ao Admin."}
    if dados["professores"][cpf]["senha"] != hash_senha(senha):
        return {"role": None, "message": "Senha incorreta!"}

    disciplinas_do_prof = {}

    for chave_disc, info in dados["disciplinas"].items():
        if isinstance(info, dict) and "professor" in info and info["professor"].get("cpf") == cpf:
            disc_nome = info.get("nome_original", chave_disc.split('-')[0])
            disciplinas_do_prof[disc_nome] = info["turma"]

    return {"role": "professor", "cpf": cpf, "nome": dados["professores"][cpf]["nome"], "disciplinas": disciplinas_do_prof}

def login_aluno_server(ra, senha):
    dados = carregar_dados()
    ra = ra.upper()

    if ra not in dados["alunos"]:
        return {"role": None, "message": "RA não encontrado! Solicite seu cadastro ao Admin."}
    if dados["alunos"][ra]["senha"] != hash_senha(senha):
        return {"role": None, "message": "Senha incorreta!"}

    aluno = dados["alunos"][ra]

    notas_formatadas = {}
    for disc, notas in aluno['notas'].items():
        np1 = notas.get("NP1", "PENDENTE")
        np2 = notas.get("NP2", "PENDENTE")
        media_ativ = notas.get("ATIVIDADES_MEDIA", "PENDENTE")
        final = notas.get("NOTA_FINAL", "N/A")
        notas_formatadas[disc] = {"NP1": np1, "NP2": np2, "Media_Ativ": media_ativ, "Final": final}

    return {
        "role": "aluno",
        "ra": ra,
        "nome": aluno["nome"],
        "turma": aluno["turma"],
        "faltas": aluno.get('faltas', 0),
        "notas": notas_formatadas
    }

def get_aluno_data_server(ra):
    dados = carregar_dados()
    aluno = dados["alunos"].get(ra.upper())

    if not aluno:
        return {"success": False, "message": "Aluno não encontrado."}

    notas_formatadas = {}
    for disc, notas in aluno['notas'].items():
        np1 = notas.get("NP1", "PENDENTE")
        np2 = notas.get("NP2", "PENDENTE")
        media_ativ = notas.get("ATIVIDADES_MEDIA", "PENDENTE")
        final = notas.get("NOTA_FINAL", "N/A")
        notas_formatadas[disc] = {"NP1": np1, "NP2": np2, "Media_Ativ": media_ativ, "Final": final}

    return {
        "success": True,
        "ra": ra,
        "nome": aluno["nome"],
        "turma": aluno["turma"],
        "faltas": aluno.get('faltas', 0),
        "notas": notas_formatadas
    }

def lista_chamada_server(turma, presenca_list):
    dados = carregar_dados()

    for ra, presente in presenca_list.items():
        if not presente:
            dados["turmas"][turma]["alunos"][ra]["faltas"] = dados["turmas"][turma]["alunos"][ra].get("faltas", 0) + 1
            dados["alunos"][ra]["faltas"] = dados["alunos"][ra].get("faltas", 0) + 1

    salvar_dados(dados)
    return {"success": True, "message": "Chamada registrada!"}

def get_lista_alunos_turma(turma):
    dados = carregar_dados()
    return dados["turmas"].get(turma, {}).get("alunos", {})

def gerar_topicos_ia_server(disciplina, tema):
    try:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            return {"success": False, "content": "[ERRO DE API] A chave GEMINI_API_KEY não está definida no servidor."}

        client = genai.Client(api_key=api_key)

        prompt = f"Gere 5 tópicos de aula curtos e didáticos sobre o tema '{tema}' para a disciplina de {disciplina}. Liste apenas os 5 tópicos numerados."

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return {"success": True, "content": response.text}

    except Exception as e:
        return {
            "success": False,
            "content": f"[ERRO NA CONEXÃO DA API] A IA não pôde ser contatada. Detalhe do erro: {e}"
        }

def enviar_atividade_server(disciplina, turma, nome_atividade, link_atividade):
    dados = carregar_dados()

    num_atividades = len(dados["turmas"][turma]["disciplinas"][disciplina].get("atividades", {}))
    if num_atividades >= 10:
        return {"success": False, "message": "Limite de 10 atividades por disciplina atingido (modelo fixo)."}

    atividade_data = {
        "link": link_atividade,
        "respostas": {},
        "notas": {}
    }

    dados["turmas"][turma]["disciplinas"][disciplina]["atividades"][nome_atividade] = atividade_data

    salvar_dados(dados)
    return {"success": True, "message": f"Atividade '{nome_atividade}' enviada."}

def lancar_np_grades_server(disciplina, turma, tipo_nota, lancamentos):
    dados = carregar_dados()

    for ra, nota in lancamentos.items():
        try:
            nota_float = float(nota)
            if 0.0 <= nota_float <= 10.0:
                if disciplina not in dados["alunos"][ra]["notas"]:
                    dados["alunos"][ra]["notas"][disciplina] = {}
                if disciplina not in dados["turmas"][turma]["alunos"][ra]["notas"]:
                    dados["turmas"][turma]["alunos"][ra]["notas"][disciplina] = {}

                dados["alunos"][ra]["notas"][disciplina][tipo_nota] = nota_float
                dados["turmas"][turma]["alunos"][ra]["notas"][disciplina][tipo_nota] = nota_float
        except ValueError:
            pass

    salvar_dados(dados)
    return {"success": True, "message": f"Lançamento de {tipo_nota} concluído!"}

def get_atividades_disciplina(disciplina, turma):
    dados = carregar_dados()
    return dados["turmas"][turma]["disciplinas"].get(disciplina, {}).get("atividades", {})

def get_entregas_atividade(disciplina, turma, nome_atividade):
    dados = carregar_dados()

    atividades = dados["turmas"][turma]["disciplinas"].get(disciplina, {}).get("atividades", {})
    atividade_data = atividades.get(nome_atividade, {})

    respostas = atividade_data.get("respostas", {})
    notas = atividade_data.get("notas", {})
    alunos_turma = dados["turmas"][turma]["alunos"]

    entregas = []
    for ra, link in respostas.items():
        if ra in alunos_turma:
            entregas.append({
                "ra": ra,
                "nome": alunos_turma[ra]["nome"],
                "link": link,
                "nota_atual": notas.get(ra, "PENDENTE")
            })

    return entregas

def atribuir_nota_atividade_server(disciplina, turma, nome_atividade, ra, nota_float):
    dados = carregar_dados()

    dados["turmas"][turma]["disciplinas"][disciplina]["atividades"][nome_atividade]["notas"][ra] = nota_float

    salvar_dados(dados)
    return {"success": True, "message": f"Nota {nota_float} salva para o aluno RA {ra}."}

def calcular_nota_final(ra, disciplina, dados):
    PESO_NP1 = 0.35
    PESO_NP2 = 0.35
    PESO_ATIVIDADES = 0.30

    aluno_turma = dados["alunos"][ra]["turma"]

    if disciplina not in dados["turmas"].get(aluno_turma, {}).get("disciplinas", {}):
        return

    atividades_disc = dados["turmas"][aluno_turma]["disciplinas"][disciplina].get("atividades", {})
    num_atividades_cadastradas = len(atividades_disc)
    soma_notas_atividades = 0.0

    if num_atividades_cadastradas > 0:
        for nome_ativ, info_ativ in atividades_disc.items():
            nota = info_ativ.get("notas", {}).get(ra)
            if nota is not None:
                soma_notas_atividades += nota

        media_atividades = soma_notas_atividades / num_atividades_cadastradas
    else:
        media_atividades = 0.0

    notas_aluno = dados["alunos"][ra]["notas"].get(disciplina, {})
    np1 = notas_aluno.get("NP1", 0.0)
    np2 = notas_aluno.get("NP2", 0.0)

    global C_FUNCTION  
    global C_LIB_LOADED

    if C_LIB_LOADED and C_FUNCTION is not None:
        try:
            nota_final = float(C_FUNCTION(np1, np2, media_atividades))
        except Exception as e:
            print(f"[ERRO CTYPES] Falha na chamada C em tempo de execução. Usando Python. Erro: {e}")
            nota_final = (np1 * PESO_NP1) + (np2 * PESO_NP2) + (media_atividades * PESO_ATIVIDADES)
    else:
        nota_final = (np1 * PESO_NP1) + (np2 * PESO_NP2) + (media_atividades * PESO_ATIVIDADES)

    if disciplina not in dados["alunos"][ra]["notas"]:
        dados["alunos"][ra]["notas"][disciplina] = {}

    dados["alunos"][ra]["notas"][disciplina]["ATIVIDADES_MEDIA"] = round(media_atividades, 2)
    dados["alunos"][ra]["notas"][disciplina]["NOTA_FINAL"] = round(nota_final, 2)

    if aluno_turma in dados["turmas"] and ra in dados["turmas"][aluno_turma]["alunos"]:
        if disciplina not in dados["turmas"][aluno_turma]["alunos"][ra]["notas"]:
            dados["turmas"][aluno_turma]["alunos"][ra]["notas"][disciplina] = {}

        dados["turmas"][aluno_turma]["alunos"][ra]["notas"][disciplina]["ATIVIDADES_MEDIA"] = round(media_atividades, 2)
        dados["turmas"][aluno_turma]["alunos"][ra]["notas"][disciplina]["NOTA_FINAL"] = round(nota_final, 2)

def calcular_nota_final_turma_server(disciplina, turma):
    dados = carregar_dados()
    alunos_turma = dados["turmas"][turma]["alunos"].keys()

    print(f"\n--- Calculando Notas Finais para {disciplina} (Turma {turma}) ---")

    for ra in alunos_turma:
        calcular_nota_final(ra, disciplina, dados)

    salvar_dados(dados)
    return {"success": True, "message": "Cálculo das notas finais concluído."}


def ver_notas_faltas_turma_server(disciplina, turma):
    dados = carregar_dados()
    alunos = dados["turmas"][turma]["alunos"]

    relatorio = []
    for ra, info in alunos.items():
        notas = info["notas"].get(disciplina, {})
        relatorio.append({
            "nome": info['nome'],
            "ra": ra,
            "np1": notas.get("NP1", "S/D"),
            "np2": notas.get("NP2", "S/D"),
            "media_ativ": notas.get("ATIVIDADES_MEDIA", "S/D"),
            "final": notas.get("NOTA_FINAL", "S/D"),
            "faltas": info.get("faltas", 0)
        })

    return relatorio

def get_atividades_aluno_turma(ra):
    dados = carregar_dados()
    aluno = dados["alunos"].get(ra.upper())
    if not aluno:
        return {"success": False, "message": "Aluno não encontrado."}

    turma = aluno["turma"]
    disciplinas = dados["turmas"][turma]["disciplinas"]

    atividades_listadas = []
    for disc, info_disc in disciplinas.items():
        if info_disc.get("atividades"):
            for nome_atividade, info in info_disc["atividades"].items():
                atividades_listadas.append({
                    "disciplina": disc,
                    "nome": nome_atividade,
                    "link": info.get('link', 'Link Indisponível'),
                    "enviada": nome_atividade in aluno["atividades_enviadas"]
                })

    return {"success": True, "atividades": atividades_listadas, "turma": turma, "disciplinas_turma": list(disciplinas.keys())}

def enviar_atividade_aluno_server(ra, disc_sel, nome_atividade, resposta_link):
    dados = carregar_dados()
    aluno = dados["alunos"].get(ra.upper())
    if not aluno:
        return {"success": False, "message": "Aluno não encontrado."}

    turma = aluno["turma"]

    if disc_sel not in dados["turmas"][turma]["disciplinas"]:
        return {"success": False, "message": "Disciplina não está na sua turma."}

    if nome_atividade not in dados["turmas"][turma]["disciplinas"][disc_sel]["atividades"]:
        return {"success": False, "message": "Atividade não encontrada na disciplina."}

    dados["turmas"][turma]["disciplinas"][disc_sel]["atividades"][nome_atividade]["respostas"][ra] = resposta_link
    dados["alunos"][ra]["atividades_enviadas"][nome_atividade] = {"disciplina": disc_sel, "resposta": resposta_link}

    salvar_dados(dados)
    return {"success": True, "message": f"Atividade '{nome_atividade}' enviada com sucesso! O professor já pode verificar o link."}
    
def registrar_aula_server(disciplina, turma, data, descricao):
    dados = carregar_dados()
    try:
        if turma not in dados["turmas"] or disciplina not in dados["turmas"][turma]["disciplinas"]:
            return {"success": False, "message": "Turma ou disciplina não encontrada."}
            
        aulas_ref = dados["turmas"][turma]["disciplinas"][disciplina].setdefault("aulas", {})
        
        if data in aulas_ref:
            return {"success": False, "message": f"Já existe uma aula registrada para a data {data}."}
            
        aulas_ref[data] = {"descricao": descricao}
        
        salvar_dados(dados)
        return {"success": True, "message": f"Aula de {disciplina} em {data} registrada com sucesso!"}
        
    except Exception as e:
        return {"success": False, "message": f"Erro ao registrar aula: {e}"}

def listar_aulas_server(disciplina, turma):
    dados = carregar_dados()
    try:
        if turma not in dados["turmas"] or disciplina not in dados["turmas"][turma]["disciplinas"]:
            return {"success": False, "message": "Turma ou disciplina não encontrada."}
            
        aulas = dados["turmas"][turma]["disciplinas"][disciplina].get("aulas", {})
        
        aulas_listadas = [{"data": data, "descricao": info["descricao"]} for data, info in aulas.items()]
        
        aulas_listadas.sort(key=lambda x: x['data'])
        
        return {"success": True, "aulas": aulas_listadas}
        
    except Exception as e:
        return {"success": False, "message": f"Erro ao listar aulas: {e}"}


SERVER_ACTIONS = {
    "login_administrador": login_administrador_server,
    "login_professor": login_professor_server,
    "login_aluno": login_aluno_server,
    "get_aluno_data": get_aluno_data_server,
    "cadastrar_turma": cadastrar_turma_server,
    "cadastrar_professor": cadastrar_professor_server,
    "get_cadastro_info": get_cadastro_info,
    "cadastrar_disciplina": cadastrar_disciplina_server,
    "cadastrar_aluno": cadastrar_aluno_server,
    "get_lista_alunos_turma": get_lista_alunos_turma,
    "lista_chamada": lista_chamada_server,
    "gerar_topicos_ia": gerar_topicos_ia_server,
    "enviar_atividade": enviar_atividade_server,
    "lancar_np_grades": lancar_np_grades_server,
    "get_atividades_disciplina": get_atividades_disciplina,
    "get_entregas_atividade": get_entregas_atividade,
    "atribuir_nota_atividade": atribuir_nota_atividade_server,
    "calcular_nota_final_turma": calcular_nota_final_turma_server,
    "ver_notas_faltas_turma": ver_notas_faltas_turma_server,
    "get_atividades_aluno_turma": get_atividades_aluno_turma,
    "enviar_atividade_aluno": enviar_atividade_aluno_server,
    "registrar_aula": registrar_aula_server, 
    "listar_aulas": listar_aulas_server,
}

def handle_client(conn, addr):
    print(f"[CONEXÃO] Conectado a {addr}")

    while True:
        try:
            tamanho_bytes = conn.recv(4)
            if not tamanho_bytes:
                break

            tamanho = int.from_bytes(tamanho_bytes, 'big')

            data = b''
            bytes_recv = 0
            while bytes_recv < tamanho:
                chunk = conn.recv(min(tamanho - bytes_recv, 4096))
                if not chunk:
                    break
                data += chunk
                bytes_recv += len(chunk)

            if not data:
                break

            request = json.loads(data.decode('utf-8'))
            action = request.get('action')
            params = request.get('params', [])

            print(f"[REQUISIÇÃO] {addr}: {action} com {len(params)} parâmetros.")

            if action in SERVER_ACTIONS:
                try:
                    result = SERVER_ACTIONS[action](*params)
                except TypeError as te:
                    result = {"error": f"Parâmetros inválidos para a ação '{action}': {te}"}
                except Exception as e:
                    result = {"error": f"Erro ao executar ação '{action}': {e}"}
            else:
                result = {"error": "Ação desconhecida", "action_received": action}

            response_data = json.dumps(result, ensure_ascii=False).encode('utf-8')
            response_size = len(response_data).to_bytes(4, 'big')

            conn.sendall(response_size + response_data)

        except ConnectionResetError:
            print(f"[DESCONEXÃO] Cliente {addr} desconectou abruptamente.")
            break
        except json.JSONDecodeError:
            print(f"[ERRO] Dados JSON inválidos recebidos de {addr}")
        except Exception as e:
            print(f"[ERRO DE SERVIDOR] Ocorreu um erro: {e}")
            traceback.print_exc()
            try:
                error_msg = json.dumps({"error": str(e), "traceback": traceback.format_exc()}, ensure_ascii=False).encode('utf-8')
                error_size = len(error_msg).to_bytes(4, 'big')
                conn.sendall(error_size + error_msg)
            except:
                pass
            break

    print(f"[FECHAMENTO] Conexão com {addr} encerrada.")
    conn.close()


def start_server():
    global SERVER_RUNNING
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((HOST, PORT))
    server.listen()
    print(f"*** Servidor Educacional Rodando em {HOST}:{PORT} ***")
    print(">>> Para encerrar o servidor, pressione ENTER na linha de comando e digite 'q' ou 'quit'.")

    while SERVER_RUNNING:
        try:
            server.settimeout(0.5)
            conn, addr = server.accept()
            server.settimeout(None)

            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()
            print(f"[ATIVO] Total de conexões ativas: {threading.active_count() - 1}")

        except socket.timeout:
            continue
        except Exception as e:
            if SERVER_RUNNING:
                print(f"[ERRO DE ACEITE] Ocorreu um erro: {e}")
            break

    print("*** Encerrando o servidor de sockets... ***")
    server.close()


if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server)
    server_thread.start()

    time.sleep(1)  

    print("\n--- Servidor Iniciado. Monitoramento Ativo ---")

    while SERVER_RUNNING:
        command = input("Digite 'q' ou 'quit' para encerrar: ").strip().lower()

        if command in ['q', 'quit', 'exit']:
            SERVER_RUNNING = False

            try:
                shutdown_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                shutdown_sock.connect((HOST, PORT))
                shutdown_sock.close()
            except ConnectionRefusedError:
                pass
            except Exception as e:
                print(f"Erro ao tentar fechar o socket de aceitação: {e}")

    server_thread.join()
    print("Programa servidor encerrado.")
    
    