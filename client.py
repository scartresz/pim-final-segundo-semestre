import os
import json
import socket
import webbrowser 
import time

HOST = '127.0.0.1' 
PORT = 65432       

SESSAO_USUARIO = None
SESSAO_CONEXAO = None 

def connect_to_server():
    global SESSAO_CONEXAO
    try:
        if SESSAO_CONEXAO:
             SESSAO_CONEXAO.close()
             SESSAO_CONEXAO = None
             
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        SESSAO_CONEXAO = sock
        return True
    except ConnectionRefusedError:
        print(f"\n[ERRO DE CONEXÃO] Não foi possível conectar ao Servidor em {HOST}:{PORT}.")
        print("Certifique-se de que o 'server.py' esteja rodando antes do cliente.")
        return False
    except Exception as e:
        print(f"\n[ERRO DE CONEXÃO] Ocorreu um erro desconhecido: {e}")
        return False

def send_request(action, params):
    global SESSAO_CONEXAO
    
    if not SESSAO_CONEXAO:
        print("[AVISO] Conexão perdida. Tentando reconectar...")
        if not connect_to_server():
            return {"error": "Conexão falhou após tentativa de reconexão."}
            
    request = {"action": action, "params": params}
    
    try:
        request_data = json.dumps(request, ensure_ascii=False).encode('utf-8')
        request_size = len(request_data).to_bytes(4, 'big')
        
        SESSAO_CONEXAO.sendall(request_size + request_data)

        tamanho_bytes = SESSAO_CONEXAO.recv(4)
        if not tamanho_bytes:
            raise ConnectionResetError("Conexão fechada pelo Servidor.")
            
        tamanho = int.from_bytes(tamanho_bytes, 'big')
        
        data = b''
        bytes_recv = 0
        while bytes_recv < tamanho:
            chunk = SESSAO_CONEXAO.recv(min(tamanho - bytes_recv, 4096))
            if not chunk:
                raise ConnectionResetError("Conexão fechada pelo Servidor durante a recepção.")
            data += chunk
            bytes_recv += len(chunk)

        return json.loads(data.decode('utf-8'))

    except ConnectionResetError as e:
        print(f"[ERRO DE COMUNICAÇÃO] O servidor fechou a conexão: {e}")
        SESSAO_CONEXAO = None
        return {"error": "Conexão perdida com o Servidor."}
    except Exception as e:
        print(f"[ERRO FATAL] Falha na comunicação: {e}")
        return {"error": f"Erro de comunicação: {e}"}

def limpar_tela():
    if os.name == 'nt': 
        os.system('cls')
    else: 
        os.system('clear')

def cadastrar_turma():
    nome_turma = input("Digite o nome da turma (ex: 3A, 3B, 2A...): ").upper()
    response = send_request("cadastrar_turma", [nome_turma])
    print(response.get("message", "Erro desconhecido."))

def cadastrar_professor():
    cpf = input("Digite o CPF do professor: ")
    nome = input("Digite o nome completo do professor: ")
    senha = input("Digite a senha: ")
    response = send_request("cadastrar_professor", [cpf, nome, senha])
    print(response.get("message", "Erro desconhecido."))

def cadastrar_disciplina():
    nome_disc = input("Digite o nome da disciplina: ").upper()
    
    response_turmas = send_request("get_cadastro_info", ["turmas"])
    turmas = response_turmas if isinstance(response_turmas, list) else []
    if not turmas:
        print("Não há turmas cadastradas!")
        return
        
    while True:
        print("\nTurmas disponíveis:")
        for i, t in enumerate(turmas, 1):
            print(f"{i}. {t}")
        escolha_turma = input("Escolha o número da turma: ")
        if escolha_turma.isdigit() and 1 <= int(escolha_turma) <= len(turmas):
            turma_escolhida = turmas[int(escolha_turma)-1]
            break
        else:
            print("Opção inválida! Tente novamente.")

    response_profs = send_request("get_cadastro_info", ["professores"])
    professores_list = response_profs if isinstance(response_profs, list) else []
    if not professores_list:
        print("Não há professores cadastrados!")
        return

    while True:
        print("\nProfessores disponíveis:")
        profs_com_cpf = []
        for i, prof_dict in enumerate(professores_list, 1):
            cpf = list(prof_dict.keys())[0]
            nome = prof_dict[cpf]
            profs_com_cpf.append((cpf, nome))
            print(f"{i}. {nome} (CPF: {cpf})")
        
        escolha_prof = input("Escolha o número do professor: ")
        
        if escolha_prof.isdigit() and 1 <= int(escolha_prof) <= len(profs_com_cpf):
            cpf_prof_escolhido, _ = profs_com_cpf[int(escolha_prof)-1]
            break
        else:
            print("Opção inválida! Tente novamente.")
            
    response = send_request("cadastrar_disciplina", [nome_disc, turma_escolhida, cpf_prof_escolhido])
    print(response.get("message", "Erro desconhecido."))

def cadastrar_aluno():
    ra = input("Digite o RA do aluno: ").upper()
    nome = input("Digite o nome do aluno: ").upper()
    senha = input("Digite a senha: ")

    response_turmas = send_request("get_cadastro_info", ["turmas"])
    turmas = response_turmas if isinstance(response_turmas, list) else []
    if not turmas:
        print("Não há turmas cadastradas!")
        return
        
    while True:
        print("\nTurmas disponíveis:")
        for i, t in enumerate(turmas, 1):
            print(f"{i}. {t}")
        escolha = input("Escolha o número da turma: ")
        
        if escolha.isdigit() and 1 <= int(escolha) <= len(turmas):
            turma_escolhida = turmas[int(escolha)-1]
            break
        else:
            print("Opção inválida! Tente novamente.")
            
    response = send_request("cadastrar_aluno", [ra, nome, senha, turma_escolhida])
    print(response.get("message", "Erro desconhecido."))


def login_administrador():
    global SESSAO_USUARIO
    usuario = input("Usuário: ")
    senha = input("Senha: ")
    
    response = send_request("login_administrador", [usuario, senha])
    if response and response.get("role") == "admin":
        SESSAO_USUARIO = response
        limpar_tela()
        menu_administrador()
        return True
    else:
        print(response.get("message", "Falha no login."))
        return False

def login_professor():
    global SESSAO_USUARIO
    cpf = input("CPF: ")
    senha = input("Senha: ")
    
    response = send_request("login_professor", [cpf, senha])
    if response and response.get("role") == "professor":
        SESSAO_USUARIO = response
        limpar_tela()
        menu_professor(response["cpf"], response["nome"], response["disciplinas"])
        return True
    else:
        print(response.get("message", "Falha no login."))
        return False

def login_aluno():
    global SESSAO_USUARIO
    ra = input("RA: ").upper()
    senha = input("Senha: ")
    
    response = send_request("login_aluno", [ra, senha])
    if response and response.get("role") == "aluno":
        SESSAO_USUARIO = response
        limpar_tela()
        menu_aluno(response)
        return True
    else:
        print(response.get("message", "Falha no login."))
        return False

def menu_administrador():
    while True:
        print("MENU ADMINISTRADOR")
        print("1. Cadastrar Turma")
        print("2. Cadastrar Professor")
        print("3. Cadastrar Disciplina")
        print("4. Cadastrar Aluno")
        print("5. Voltar")
        opcao = input("Escolha uma opção: ")
        limpar_tela()
        if opcao == "1":
            cadastrar_turma()
        elif opcao == "2":
            cadastrar_professor()
        elif opcao == "3":
            cadastrar_disciplina()
        elif opcao == "4":
            cadastrar_aluno()
        elif opcao == "5":
            break
        else:
            print("Opção inválida!")

def menu_professor(cpf, nome, disciplinas):
    while True:
        print(f"MENU PROFESSOR - {nome}")
        
        disc_list = list(disciplinas.items())
        
        for i, (disc, turma) in enumerate(disc_list, 1):
            print(f"{i}. {disc} (Turma: {turma})")
            
        print(f"{len(disc_list)+1}. Voltar")
        escolha = input("Escolha uma disciplina: ")
        
        if not escolha.isdigit():
            limpar_tela()
            print("Opção inválida!")
            continue
            
        escolha_int = int(escolha)
        
        if escolha_int == len(disc_list)+1:
            limpar_tela()
            break
            
        if 1 <= escolha_int <= len(disc_list):
            disc_selecionada = disc_list[escolha_int-1][0]
            turma = disc_list[escolha_int-1][1]
            limpar_tela()
            menu_disciplina_professor(disc_selecionada, turma)
        else:
            limpar_tela()
            print("Opção inválida!")

def menu_disciplina_professor(disciplina, turma):
    while True:
        print(f"\nDisciplina: {disciplina} | Turma: {turma}")
        
        print("\n--- I. Planejamento de Aula e Conteúdo ---")
        print("1. Registrar Aula") 
        print("2. Gerar Tópicos de Aula (IA)") 
        print("3. Registrar atividade") 
        
        print("\n--- II. Acompanhamento e Presença ---")
        print("4. Listar Aulas") 
        print("5. Lista de chamada")
        
        print("\n--- III. Notas e Avaliação ---")
        print("6. Corrigir e Atribuir Nota de Atividade") 
        print("7. Lançar NP1/NP2")
        print("8. Calcular e Atualizar Nota Final do Semestre") 
        print("9. Ver notas e faltas da turma")
        
        print("\n10. Voltar")
        
        opcao = input("Escolha uma opção: ")
        limpar_tela()
        
        if opcao == "1":
            registrar_aula(disciplina, turma) 
        elif opcao == "2":
            gerar_topicos_ia(disciplina) 
        elif opcao == "3":
            enviar_atividade(disciplina, turma)
        
        elif opcao == "4":
            listar_aulas(disciplina, turma)
        elif opcao == "5":
            lista_chamada(turma)
            
        elif opcao == "6":
            corrigir_e_atribuir_nota_atividade(disciplina, turma)
        elif opcao == "7":
            lancar_np_grades(disciplina, turma)
        elif opcao == "8":
            calcular_nota_final_turma(disciplina, turma)
        elif opcao == "9":
            ver_notas_faltas_turma(disciplina, turma)
            
        elif opcao == "10":
            break
        else:
            print("Opção inválida!")
            
def menu_aluno(aluno_data):
    ra = aluno_data["ra"]
    nome = aluno_data["nome"] 

    while True:
        response_data = send_request("get_aluno_data", [ra]) 

        if response_data.get("success"):
            aluno_data = response_data
            turma = aluno_data["turma"] 
        else:
            print("Erro ao atualizar dados do aluno. Voltando ao Menu Principal.")
            break

        print(f"MENU ALUNO - {aluno_data['nome']} (Turma: {turma})")
        print("1. Ver notas e faltas")
        print("2. Ver atividades")
        print("3. Enviar atividade")
        print("4. Listar Aulas") 
        print("5. Voltar")
        opcao = input("Escolha uma opção: ")
        limpar_tela()
        
        if opcao == "1":
            print("\n--- SUAS NOTAS ---")
            for disc, notas in aluno_data['notas'].items():
                print(f"\nDisciplina: {disc}")
                print(f"  NP1: {notas['NP1']} | NP2: {notas['NP2']} | Média Ativ: {notas['Media_Ativ']}")
                print(f"  NOTA FINAL: {notas['Final']}")
                
            print(f"\nFaltas Totais: {aluno_data['faltas']}")
            input("\nPressione ENTER para voltar ao menu.")
            limpar_tela()
            
        elif opcao == "2":
            ver_atividades(ra)
            
        elif opcao == "3":
            enviar_atividade_aluno(ra)

        elif opcao == "4":
            response_ativ_aluno = send_request("get_atividades_aluno_turma", [ra])
            if response_ativ_aluno.get("success"):
                turma = response_ativ_aluno["turma"]
                disciplinas = response_ativ_aluno["disciplinas_turma"]
                
                print("\nDisciplinas disponíveis para listar aulas:")
                if not disciplinas:
                    print("Nenhuma disciplina cadastrada para sua turma.")
                    input("\nPressione ENTER para voltar ao menu.")
                    limpar_tela()
                    continue

                for i, disc in enumerate(disciplinas, 1):
                    print(f"{i}. {disc}")
                
                escolha = input("Escolha o número da disciplina: ")
                if escolha.isdigit() and 1 <= int(escolha) <= len(disciplinas):
                    disc_sel = disciplinas[int(escolha)-1]
                    limpar_tela()
                    listar_aulas(disc_sel, turma)
                else:
                    limpar_tela()
                    print("Opção inválida!")
            else:
                limpar_tela()
                print("Erro ao buscar informações da turma.")
            
        elif opcao == "5":
            break
            
        else:
            print("Opção inválida!")

def lista_chamada(turma):
    response = send_request("get_lista_alunos_turma", [turma])
    alunos_turma = response if isinstance(response, dict) else {}
    
    if not alunos_turma:
        print(f"\nNenhum aluno cadastrado na turma {turma}.")
        return

    presenca_list = {}
    print(f"\nLista de chamada - Turma {turma}")
    
    for ra, info in alunos_turma.items():
        resp = input(f"Aluno {info['nome']} presente? (S/N): ").strip().upper()
        presenca_list[ra] = resp == "S"
            
    response_server = send_request("lista_chamada", [turma, presenca_list])
    print(response_server.get("message", "Erro ao registrar chamada."))

def gerar_topicos_ia(disciplina):
    print("\n--- GERAÇÃO DE CONTEÚDO (IA) ---")
    tema = input(f"Digite o TEMA principal da aula para {disciplina}: ").strip()
    
    if not tema:
        print("[AVISO DA IA] Tema não fornecido. Voltando ao menu.")
        return

    response = send_request("gerar_topicos_ia", [disciplina, tema])
    limpar_tela()
    
    print(f"\n--- RESPOSTA DA IA: 5 Tópicos para '{disciplina}' ---")
    print(response.get("content", "Erro na IA, tente novamente."))
    
    input("\nPressione ENTER para voltar ao menu da disciplina.") 
    limpar_tela()

def enviar_atividade(disciplina, turma):
    nome_atividade = input("Nome da atividade: ")
    link_atividade = input("Cole o link (URL) da atividade no Google Drive: ")
    
    response = send_request("enviar_atividade", [disciplina, turma, nome_atividade, link_atividade])
    print(response.get("message", "Erro ao enviar atividade."))

def lancar_np_grades(disciplina, turma):
    response = send_request("get_lista_alunos_turma", [turma])
    alunos = response if isinstance(response, dict) else {}
    
    if not alunos:
        print(f"Nenhum aluno na turma {turma}.")
        return
        
    while True:
        print("\nQual nota deseja lançar?")
        print("1. NP1 (35%)")
        print("2. NP2 (35%)")
        escolha = input("Escolha a opção: ")
        limpar_tela()

        if escolha == "1":
            tipo_nota = "NP1"
            break
        elif escolha == "2":
            tipo_nota = "NP2"
            break
        else:
            print("Opção inválida! Digite 1 ou 2.")

    lancamentos = {}
    print(f"\n--- Lançamento de {tipo_nota} para {disciplina} (Turma {turma}) ---")
    
    for ra, info in alunos.items():
        notas_atuais = info.get("notas", {}).get(disciplina, {})
        nota_atual = notas_atuais.get(tipo_nota, "PENDENTE")
        
        while True:
            nota = input(f"Nota de {info['nome']} ({tipo_nota}: {nota_atual}). Digite a nota (0-10) ou ENTER para pular: ").strip()
            
            if not nota:
                break
                
            try:
                nota_float = float(nota)
                if 0.0 <= nota_float <= 10.0:
                    lancamentos[ra] = nota_float
                    break
                else:
                    print("Nota fora do intervalo (0 a 10). Tente novamente.")
            except ValueError:
                print("Valor inválido. Digite um número.")

    response_server = send_request("lancar_np_grades", [disciplina, turma, tipo_nota, lancamentos])
    limpar_tela()
    print(response_server.get("message", "Erro ao lançar notas."))

def corrigir_e_atribuir_nota_atividade(disciplina, turma):
    response_atividades = send_request("get_atividades_disciplina", [disciplina, turma])
    atividades = response_atividades if isinstance(response_atividades, dict) else {}

    if not atividades:
        print("Nenhuma atividade cadastrada para esta disciplina.")
        return

    ativ_list = list(atividades.keys())
    while True:
        print(f"\n--- Atividades de {disciplina} ---")
        for i, nome_atividade in enumerate(ativ_list, 1):
            print(f"{i}. {nome_atividade}")

        escolha_atividade = input("Escolha o número da atividade para correção (ou 'V' para voltar): ").strip().upper()
        limpar_tela()
        
        if escolha_atividade == 'V':
            return
            
        if escolha_atividade.isdigit() and 1 <= int(escolha_atividade) <= len(ativ_list):
            nome_atividade = ativ_list[int(escolha_atividade) - 1]
            break
        else:
            print("Opção inválida!")
            continue

    while True:
        response_entregas = send_request("get_entregas_atividade", [disciplina, turma, nome_atividade])
        entregas_listadas = response_entregas if isinstance(response_entregas, list) else []

        if not entregas_listadas:
            print(f"\nNenhum aluno enviou a atividade '{nome_atividade}' ainda.")
            break

        print(f"\n--- Entregas de '{nome_atividade}' ---")
        
        for i, entrega in enumerate(entregas_listadas, 1):
            print(f"{i}. {entrega['nome']} (Nota Atual: {entrega['nota_atual']})")

        print("\nDigite o número do aluno para abrir o trabalho e atribuir nota (ou 'V' para voltar):")
        escolha_aluno = input("Sua escolha: ").strip().upper()
        
        if escolha_aluno == 'V':
            limpar_tela()
            break
            
        if escolha_aluno.isdigit():
            escolha_int = int(escolha_aluno)
            if 1 <= escolha_int <= len(entregas_listadas):
                entrega_selecionada = entregas_listadas[escolha_int - 1]
                ra = entrega_selecionada["ra"]
                link = entrega_selecionada["link"]
                
                print(f"Abrindo o trabalho de {entrega_selecionada['nome']} no seu navegador...")
                webbrowser.open(link)
                
                while True:
                    try:
                        nota = input(f"Atribuir nota (0-10) para {entrega_selecionada['nome']} na atividade '{nome_atividade}': ").strip()
                        if not nota:
                            print("Nota não atribuída. Voltando à lista de entregas...")
                            break
                            
                        nota_float = float(nota)
                        if 0.0 <= nota_float <= 10.0:
                            response_atribui = send_request("atribuir_nota_atividade", [disciplina, turma, nome_atividade, ra, nota_float])
                            print(response_atribui.get("message", "Erro ao atribuir nota."))
                            limpar_tela()
                            break
                        else:
                            print("Nota fora do intervalo (0 a 10).")
                    except ValueError:
                        print("Entrada inválida. Digite um número.")
            else:
                limpar_tela()
                print("Opção inválida!")
        else:
            limpar_tela()
            print("Opção inválida. Digite o número ou 'V'.")

def calcular_nota_final_turma(disciplina, turma):
    response = send_request("calcular_nota_final_turma", [disciplina, turma])
    print(response.get("message", "Erro ao calcular notas finais."))
    print("Verifique o resultado na opção 'Ver notas e faltas da turma'.")

def ver_notas_faltas_turma(disciplina, turma):
    response = send_request("ver_notas_faltas_turma", [disciplina, turma])
    relatorio = response if isinstance(response, list) else []
    
    print(f"\nNotas e faltas da turma {turma} - Disciplina {disciplina}")
    
    if not relatorio:
        print("Nenhum dado de aluno encontrado ou erro no servidor.")
        return
        
    for aluno in relatorio:
        print(f"Nome: {aluno['nome']} | RA: {aluno['ra']} | NP1: {aluno['np1']} | NP2: {aluno['np2']} | Ativ. Média: {aluno['media_ativ']} | FINAL: {aluno['final']} | Faltas: {aluno['faltas']}")
        
    input("\nPressione ENTER para voltar ao menu.") 
    limpar_tela()

def ver_atividades(ra):
    response = send_request("get_atividades_aluno_turma", [ra])
    
    if not response.get("success"):
        print(response.get("message", "Erro ao buscar atividades."))
        return
        
    atividades_listadas = response["atividades"]
    
    if not atividades_listadas:
        print("Nenhuma atividade disponível no momento.")
        input("\nPressione ENTER para voltar ao menu.")
        limpar_tela()
        return
        
    print("\n--- ATIVIDADES DISPONÍVEIS ---")
    
    for i, ativ in enumerate(atividades_listadas, 1):
        status = "ENTREGUE" if ativ["enviada"] else "PENDENTE"
        print(f"{i}. {ativ['nome']} (Disciplina: {ativ['disciplina']}) - Status: {status}")
    
    while True:
        escolha = input("\nDigite o número da atividade para **abrir no navegador** (ou 'V' para voltar): ").strip().upper()
        
        if escolha == 'V':
            limpar_tela()
            return
            
        if escolha.isdigit():
            escolha_int = int(escolha)
            if 1 <= escolha_int <= len(atividades_listadas):
                atividade_selecionada = atividades_listadas[escolha_int - 1]
                link = atividade_selecionada["link"]
                
                print(f"Abrindo a atividade '{atividade_selecionada['nome']}' no seu navegador...")
                webbrowser.open(link)
                input("\nPressione ENTER para voltar ao menu.")
                limpar_tela()
                return
            else:
                print("Opção inválida!")
        else:
            print("Opção inválida. Digite o número ou 'V'.")

def enviar_atividade_aluno(ra):
    response = send_request("get_atividades_aluno_turma", [ra])
    
    if not response.get("success"):
        print(response.get("message", "Erro ao buscar disciplinas/atividades."))
        return

    turma = response["turma"]
    disciplinas = response["disciplinas_turma"]
    
    if not disciplinas:
        print("Não há disciplinas cadastradas para sua turma.")
        return

    disc_list = disciplinas
    while True:
        print("\nDisciplinas disponíveis:")
        for i, disc in enumerate(disc_list,1):
            print(f"{i}. {disc}")
            
        escolha_disc = input("Escolha o número da disciplina: ")
        if escolha_disc.isdigit() and 1 <= int(escolha_disc) <= len(disc_list):
            disc_sel = disc_list[int(escolha_disc)-1]
            limpar_tela()
            break
        else:
            print("Opção inválida de disciplina!")
            continue
    
    atividades_disc = [ativ for ativ in response["atividades"] if ativ["disciplina"] == disc_sel]
    
    if not atividades_disc:
        print(f"Nenhuma atividade disponível em {disc_sel}!")
        return
        
    print(f"\nAtividades de {disc_sel}:")
    ativ_list = [ativ["nome"] for ativ in atividades_disc]
    while True:
        for i, nome_atividade in enumerate(ativ_list,1):
            print(f"{i}. {nome_atividade}")
            
        escolha_atividade = input("Escolha o número da atividade para enviar a resposta: ")
        if escolha_atividade.isdigit() and 1 <= int(escolha_atividade) <= len(ativ_list):
            nome_atividade = ativ_list[int(escolha_atividade)-1]
            limpar_tela()
            break
        else:
            print("Opção inválida de atividade!")
            continue
            
    print("\n--- ENVIO DE ATIVIDADE ---")
    print("Para enviar seu trabalho, use um link do Google Drive.")
    print("Certifique-se de que o link do seu arquivo esteja com o acesso liberado para o professor.")
    resposta_link = input("Cole aqui o **link do seu trabalho concluído**: ")
    
    response_server = send_request("enviar_atividade_aluno", [ra, disc_sel, nome_atividade, resposta_link])
    limpar_tela()
    print(response_server.get("message", "Erro ao enviar atividade."))

def registrar_aula(disciplina, turma):
    print(f"\n--- Registrar Aula para {disciplina} ({turma}) ---")
    data = input("Digite a DATA da aula (formato DD/MM/AAAA): ")
    descricao = input("Digite a DESCRIÇÃO da aula (ex: 'Revisão NP1 e Exercícios'): ")
    
    response = send_request("registrar_aula", [disciplina, turma, data, descricao])
    print(response.get("message", "Erro desconhecido ao registrar aula."))

def listar_aulas(disciplina, turma):
    response = send_request("listar_aulas", [disciplina, turma])
    
    if not response.get("success"):
        print(response.get("message", "Erro ao buscar aulas."))
        return
        
    aulas = response["aulas"]
    
    print(f"\n--- Aulas Registradas em {disciplina} ({turma}) ---")
    if not aulas:
        print("Nenhuma aula registrada nesta disciplina.")
    else:
        for aula in aulas:
            print(f"DATA: {aula['data']} - DESCRIÇÃO: {aula['descricao']}")
            
    input("\nPressione ENTER para voltar ao menu.")
    limpar_tela()

def main():
    if not connect_to_server():
        return
        
    while True:
        print("MENU PRINCIPAL")
        print("1. Administrador")
        print("2. Aluno")
        print("3. Professor")
        print("4. Sair")
        opcao = input("Escolha uma opção: ")
        
        limpar_tela()

        if opcao == "1":
            login_administrador()
        elif opcao == "2":
            login_aluno()
        elif opcao == "3":
            login_professor()
        elif opcao == "4":
            print("Encerrando programa...")
            break
        else:
            print("Opção inválida!")

    if SESSAO_CONEXAO:
        SESSAO_CONEXAO.close()

if __name__ == "__main__":
    main()