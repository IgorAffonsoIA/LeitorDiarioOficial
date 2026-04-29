from datetime import date
import requests
import zipfile
import io
import xml.etree.ElementTree as ET
import re
import getpass
from datetime import datetime, timedelta

#login = input("Digite seu email do INLABS: ")
#senha = getpass.getpass("Digite sua senha: ")
#senha = input("Digite sua senha INLABS: ")

tipo_dou = "DO1 DO1E"

palavras = [
]

total_encontrados = 0
contador_palavras = {palavra: 0 for palavra in palavras}

url_login = "https://inlabs.in.gov.br/logar.php"
url_download = "https://inlabs.in.gov.br/index.php?p="

#payload = {"email": login, "password": senha}

headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

s = requests.Session()

def limpar_html(texto):

    texto = re.sub(r'<[^>]+>', '', texto)
    texto = re.sub(r'\s+', ' ', texto)

    return texto.strip()


def destacar_palavra(texto, palavra):

    return re.sub(
        palavra,
        f"\033[91m{palavra}\033[0m",
        texto,
        flags=re.IGNORECASE
    )

def pedir_intervalo_datas():

    while True:

        data_inicio = input("\nDigite a data INICIAL (DD/MM/AAAA): ")
        data_fim = input("Digite a data FINAL (DD/MM/AAAA): ")

        try:

            inicio = datetime.strptime(data_inicio, "%d/%m/%Y")
            fim = datetime.strptime(data_fim, "%d/%m/%Y")

            if fim < inicio:
                print("\033[91mA data final não pode ser menor que a inicial.\033[0m")
                continue

            datas = []

            data_atual = inicio

            while data_atual <= fim:

                datas.append(data_atual.strftime("%Y-%m-%d"))
                data_atual += timedelta(days=1)

            return datas

        except ValueError:
            print("\033[91mFormato inválido. Use DD/MM/AAAA.\033[0m")

def adicionar_palavras():

    print("\nAdicione palavras extras para busca.")
    print("Digite 'n' para finalizar.\n")

    palavras_adicionadas = []

    while True:

        nova_palavra = input("Palavra: ")

        if nova_palavra.lower() == "n":
            break

        palavras.append(nova_palavra)
        palavras_adicionadas.append(nova_palavra)

    if palavras_adicionadas:
        print("\nPalavras adicionadas:")
        for p in palavras_adicionadas:
            print("-", p)
    else:
        print("\nNenhuma palavra foi adicionada.\n")

def analisar_xml(xml_data):

    global total_encontrados

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        print("XML inválido ignorado.")
        return

    for article in root.findall(".//article"):

        secao = article.attrib.get("pubName", "Não informado")
        pagina = article.attrib.get("numberPage", "Não informado")
        orgao = article.attrib.get("artCategory", "Não informado")
        link = article.attrib.get("pdfPage", "")

        titulo = article.findtext(".//Identifica")
        texto = article.findtext(".//Texto")

        if texto is None:
            continue

        texto_limpo = limpar_html(texto)

        for palavra in palavras:

            if palavra.lower() in texto_limpo.lower():

                total_encontrados += 1
                contador_palavras[palavra] += 1

                pos = texto_limpo.lower().find(palavra.lower())
                inicio = max(pos - 120, 0)
                fim = pos + 120

                trecho = texto_limpo[inicio:fim]

                trecho = destacar_palavra(trecho, palavra)

                print("\nPalavra encontrada:", palavra)
                print("Seção:", secao)
                print("Página:", pagina)
                print("Órgão:", orgao)
                print("Título:", titulo)
                print("Link:", f"\033[94m{link}\033[0m")
                print("Trecho:", trecho)
                print("-" * 80)


def download(data_completa):

    cookie = s.cookies.get('inlabs_session_cookie')

    if not cookie:
        print("Sessão inválida. Faça login novamente.")
        return

    for dou_secao in tipo_dou.split():

        print("\nAnalisando seção:", dou_secao)

        ocorrencias_secao = 0  # contador da seção

        url_arquivo = (
            url_download
            + data_completa
            + "&dl="
            + data_completa
            + "-"
            + dou_secao
            + ".zip"
        )

        cabecalho = {
            "Cookie": "inlabs_session_cookie=" + cookie,
            "origem": "736372697074"
        }

        try:
            response = s.get(url_arquivo, headers=cabecalho, timeout=15)
        except requests.exceptions.RequestException:
            print(f"Erro ao acessar {data_completa}. Pulando...")
            return

        if response.status_code == 200 and len(response.content) > 0:

            try:
                zip_bytes = io.BytesIO(response.content)

                with zipfile.ZipFile(zip_bytes) as z:

                    for nome_arquivo in z.namelist():

                        if nome_arquivo.endswith(".xml"):

                            try:
                                xml_data = z.read(nome_arquivo).decode("utf-8")

                                antes = total_encontrados
                                analisar_xml(xml_data)
                                depois = total_encontrados

                                ocorrencias_secao += (depois - antes)

                            except Exception:
                                print(f"Erro ao processar XML: {nome_arquivo}")
                                continue

            except zipfile.BadZipFile:
                print(f"Arquivo ZIP inválido em {data_completa} - {dou_secao}")

        else:
            print(f"Sem publicação para {data_completa} na seção {dou_secao}.")
            continue

        if ocorrencias_secao == 0:
            print(f"Nenhuma ocorrência encontrada na seção {dou_secao}.")


def login():

    global contador_palavras, total_encontrados

    while True:

        login_usuario = input("Digite seu email do INLABS: ")
        senha_usuario = getpass.getpass("Digite sua senha: ")

        payload = {
            "email": login_usuario,
            "password": senha_usuario
        }

        try:

            response = s.post(url_login, data=payload, headers=headers)

            cookie = s.cookies.get('inlabs_session_cookie')

            if cookie:
                print("\nLogin realizado com sucesso.\n")

                adicionar_palavras()

                # reseta contadores
                total_encontrados = 0
                contador_palavras = {palavra: 0 for palavra in palavras}

                datas = pedir_intervalo_datas()

                for data in datas:
                    print(f"\n========== Analisando DOU de {data} ==========")

                    try:
                        download(data)
                    except Exception as e:
                        print(f"Erro no dia {data}: {e}")

                print("\n========== RESULTADO DA BUSCA ==========\n")

                print("Total de ocorrências:", total_encontrados)

                print("\nOcorrências por palavra:\n")

                for palavra, quantidade in contador_palavras.items():
                    print(f"{palavra}: {quantidade}")

                break

            else:
                print("\nLogin ou senha incorretos. Tente novamente.\n")

        except requests.exceptions.RequestException:
            print("\nErro de conexão. Tentando novamente...\n")

while True:

    login()

    opcao = input("\nDeseja realizar uma nova consulta? (s/n): ").lower()

    if opcao != "s":
        print("\nEncerrando programa...")
        break
