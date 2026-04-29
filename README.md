#  Leitor do Diário Oficial da União (DOU) — INLABS

Ferramenta para busca de palavras-chave nas publicações do Diário Oficial da União, utilizando a API do [INLABS](https://inlabs.in.gov.br/). Disponível em duas versões: terminal e interface gráfica.

---

##  Arquivos

| Arquivo | Versão |
|---|---|
| `LeitorDOU.py` | Terminal (CLI) |
| `LeitorDOU_GUI.py` | Interface gráfica (GUI) |

---

##  Pré-requisitos

- Python 3.8 ou superior
- Conta ativa no [INLABS](https://inlabs.in.gov.br/)
- Bibliotecas Python:

```bash
pip install requests
```

---

##  Como usar

### Versão Terminal (`LeitorDOU.py`)

Execute o script diretamente no terminal:

```bash
python LeitorDOU.py
```

O programa irá solicitar, em sequência:

1. **E-mail** cadastrado no INLABS
2. **Senha** (digitação oculta)
3. **Palavras-chave adicionais** para busca (além das padrão `ANVISA` e `GLAXOSMITHKLINE`) — digite `n` para pular
4. **Data inicial** e **data final** do intervalo a ser consultado (formato `DD/MM/AAAA`)

Os resultados serão exibidos diretamente no terminal com destaque colorido para as palavras encontradas e um trecho do contexto ao redor de cada ocorrência.

Ao final, o programa exibe o **total de ocorrências** e a contagem por palavra-chave, e pergunta se deseja realizar uma nova consulta.

---

### Versão Interface Gráfica (`LeitorDOU_GUI.py`)

Execute o script para abrir a janela da aplicação:

```bash
python LeitorDOU_GUI.py
```

**Preenchendo o formulário (painel lateral):**

| Campo | Descrição |
|---|---|
| E-mail | Seu e-mail cadastrado no INLABS |
| Senha | Sua senha do INLABS |
| Data Inicial / Final | Intervalo de datas no formato `DD/MM/AAAA` |
| Seções | Seções do DOU a consultar (ex: `DO1 DO1E DO2`) |
| Palavras-chave | Uma palavra por linha |

Clique em **▶ Iniciar Busca** para começar.

**Abas de resultado:**

- **Resultados** — tabela com todas as ocorrências encontradas (data, palavra, seção, página, órgão e título). Clique em uma linha para ver os detalhes completos no painel inferior.
- **Log** — acompanhe o progresso da busca em tempo real.

Os links para o PDF da publicação são clicáveis diretamente no painel de detalhes.

---

##  Configurações padrão

Ambas as versões buscam, por padrão, nas seções **DO1** e **DO1E**. Para alterar:

- **Terminal:** edite a variável `tipo_dou` no início do arquivo `LeitorDOU.py`.
- **GUI:** altere o campo **Seções** diretamente na interface antes de iniciar a busca.

As palavras-chave padrão (`ANVISA`, `GLAXOSMITHKLINE`) podem ser editadas na variável `palavras` em `LeitorDOU.py`. Na versão GUI, basta digitar as palavras desejadas na caixa correspondente.

---

##  Seções do DOU disponíveis

| Código | Descrição |
|---|---|
| `DO1` | Diário Oficial — Seção 1 |
| `DO1E` | Diário Oficial — Seção 1 Extra |
| `DO2` | Diário Oficial — Seção 2 |
| `DO2E` | Diário Oficial — Seção 2 Extra |
| `DO3` | Diário Oficial — Seção 3 |
| `DO3E` | Diário Oficial — Seção 3 Extra |

---

##  Exemplo de saída (Terminal)

```
Palavra encontrada: ANVISA
Seção: DO1
Página: 42
Órgão: MINISTÉRIO DA SAÚDE
Título: RESOLUÇÃO - RDC Nº 123
Link: https://...
Trecho: ...conforme regulamentação da ANVISA referente ao processo...
--------------------------------------------------------------------------------
```

---

##  Observações

- A ferramenta requer conexão com a internet e credenciais válidas no INLABS.
- Intervalos superiores a 31 dias na versão GUI exibem um aviso de confirmação, pois a busca pode demorar.
- Finais de semana e feriados geralmente não possuem publicações; nesses casos, o programa informa a ausência e segue para a próxima data.
- As senhas nunca são armazenadas em disco, são usadas apenas durante a sessão ativa.
