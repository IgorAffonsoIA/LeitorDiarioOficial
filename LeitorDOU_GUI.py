from datetime import date, datetime
import requests
import zipfile
import io
import xml.etree.ElementTree as ET
import re
import threading
import webbrowser
import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk, scrolledtext, messagebox

URL_LOGIN    = "https://inlabs.in.gov.br/logar.php"
URL_DOWNLOAD = "https://inlabs.in.gov.br/index.php?p="

CORES = {
    "bg":           "#0F1117",
    "sidebar":      "#161B27",
    "card":         "#1C2333",
    "border":       "#2A3347",
    "accent":       "#3B82F6",
    "accent_dark":  "#2563EB",
    "text":         "#E2E8F0",
    "text_muted":   "#64748B",
    "success":      "#22C55E",
    "warning":      "#F59E0B",
    "danger":       "#EF4444",
    "highlight":    "#FACC15",
}


def limpar_html(texto):
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def _gerar_datas(data_ini, data_fim):
    """Gera todas as datas (inclusive) entre data_ini e data_fim."""
    from datetime import timedelta
    delta = (data_fim - data_ini).days
    for d in range(delta + 1):
        yield data_ini + timedelta(days=d)


def fazer_download(session, data_ini, data_fim, tipo_dou, palavras,
                   callback_resultado, callback_log,
                   callback_progresso, callback_fim):

    cookie = session.cookies.get('inlabs_session_cookie')
    if not cookie:
        callback_log("Sessão inválida.", "danger")
        callback_fim(None)
        return

    secoes    = tipo_dou.split()
    total_enc = 0
    datas     = list(_gerar_datas(data_ini, data_fim))
    total     = len(datas) * len(secoes)
    passo     = 0

    for data_obj in datas:
        data_completa = data_obj.strftime("%Y-%m-%d")
        callback_log(f"━━  {data_obj.strftime('%d/%m/%Y')}  ━━", "warning")

        for secao in secoes:
            passo += 1
            callback_progresso(passo / total, f"{data_completa} — {secao}…")
            callback_log(f"▶  Seção {secao}", "accent")

            url = (URL_DOWNLOAD + data_completa
                   + "&dl=" + data_completa + "-" + secao + ".zip")
            cab = {"Cookie": f"inlabs_session_cookie={cookie}",
                   "origem": "736372697074"}

            try:
                resp = session.get(url, headers=cab, timeout=15)
            except requests.exceptions.RequestException:
                callback_log(f"  Erro de rede em {secao}.", "danger")
                continue

            if resp.status_code != 200 or not resp.content:
                callback_log(f"  Sem publicação para {secao}.", "muted")
                continue

            try:
                with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                    xmls = [n for n in z.namelist() if n.endswith(".xml")]
                    for nome in xmls:
                        try:
                            xml_data = z.read(nome).decode("utf-8")
                            enc = _analisar_xml(
                                xml_data, palavras,
                                callback_resultado, callback_log
                            )
                            total_enc += enc
                        except Exception as e:
                            callback_log(f"  Erro XML {nome}: {e}", "danger")
            except zipfile.BadZipFile:
                callback_log(f"  ZIP inválido em {secao}.", "danger")

    callback_progresso(1.0, "Concluído.")
    callback_fim(total_enc)


def _analisar_xml(xml_data, palavras, callback_resultado, callback_log):
    encontrados = 0
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return 0

    for article in root.findall(".//article"):
        secao     = article.attrib.get("pubName",     "—")
        pagina    = article.attrib.get("numberPage",  "—")
        orgao_raw = article.attrib.get("artCategory", "—")
        # Exibe apenas o órgão principal (primeira parte antes de "/" ou "-")
        orgao = re.split(r'[/\-]', orgao_raw)[0].strip() if orgao_raw != "—" else "—"
        link      = article.attrib.get("pdfPage",     "")
        titulo    = article.findtext(".//Identifica") or "—"

        # Data de publicação, tenta pubDate no article
        pub_date_raw = article.attrib.get("pubDate", "")
        if not pub_date_raw:
            parent = root.find(".//body")
            pub_date_raw = parent.attrib.get("pubDate", "") if parent is not None else ""
        try:
            pub_date = datetime.strptime(pub_date_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pub_date = pub_date_raw or "—"

        texto = article.findtext(".//Texto")

        if not texto:
            continue

        texto_limpo = limpar_html(texto)

        for palavra in palavras:
            pos = texto_limpo.lower().find(palavra.lower())
            if pos == -1:
                continue

            encontrados += 1
            ini    = max(pos - 120, 0)
            fim    = pos + 120
            trecho = texto_limpo[ini:fim]
            pos_rel = pos - ini

            callback_resultado({
                "palavra":     palavra,
                "secao":       secao,
                "pagina":      pagina,
                "orgao":       orgao,
                "orgao_raw":   orgao_raw,
                "titulo":      titulo,
                "link":        link,
                "trecho":      trecho,
                "pos_rel":     pos_rel,
                "palavra_len": len(palavra),
                "pub_date":    pub_date,
            })

    return encontrados


#Interface

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Leitor do DOU — INLABS")
        self.geometry("1280x720")
        self.minsize(900, 600)
        self.configure(bg=CORES["bg"])

        self.session    = requests.Session()
        self.resultados = []

        self._build_fonts()
        self._build_layout()

    #Fontes

    def _build_fonts(self):
        self.font_title   = tkFont.Font(family="Segoe UI", size=15, weight="bold")
        self.font_label   = tkFont.Font(family="Segoe UI", size=9)
        self.font_mono    = tkFont.Font(family="Consolas",  size=9)
        self.font_small   = tkFont.Font(family="Segoe UI", size=8)
        self.font_section = tkFont.Font(family="Segoe UI", size=8, weight="bold")
        self.font_meta_lbl= tkFont.Font(family="Segoe UI", size=7, weight="bold")
        self.font_meta_val= tkFont.Font(family="Segoe UI", size=9)

    #Layout principal

    def _build_layout(self):
        self.sidebar = tk.Frame(self, bg=CORES["sidebar"], width=300)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.content = tk.Frame(self, bg=CORES["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_content()

    #Sidebar

    def _build_sidebar(self):
        pad = {"padx": 20}

        tk.Frame(self.sidebar, bg=CORES["accent"], height=3).pack(fill="x")

        tk.Label(
            self.sidebar, text="Leitor Diário Oficial",
            font=self.font_title, fg=CORES["text"], bg=CORES["sidebar"],
        ).pack(anchor="w", padx=20, pady=(18, 2))

        sub_row = tk.Frame(self.sidebar, bg=CORES["sidebar"])
        sub_row.pack(anchor="w", padx=20, pady=(0, 16), fill="x")

        tk.Label(
            sub_row, text="INLABS",
            font=self.font_small, fg=CORES["text_muted"], bg=CORES["sidebar"],
        ).pack(side="left")

        self.lbl_conexao = tk.Label(
            sub_row, text="● Desconectado",
            font=self.font_small, fg=CORES["danger"], bg=CORES["sidebar"],
        )
        self.lbl_conexao.pack(side="right", padx=(0, 4))

        self._separator(self.sidebar)

        #Credenciais
        self._section_label(self.sidebar, "CREDENCIAIS")
        self._field_label(self.sidebar, "E-mail INLABS")
        self.entry_email = self._entry(self.sidebar)
        self.entry_email.pack(fill="x", **pad, pady=(2, 10))

        self._field_label(self.sidebar, "Senha")
        self.entry_senha = self._entry(self.sidebar, show="*")
        self.entry_senha.pack(fill="x", **pad, pady=(2, 10))

        self._separator(self.sidebar)

        #Parâmetros
        self._section_label(self.sidebar, "PARÂMETROS")

        #Linha
        row_datas = tk.Frame(self.sidebar, bg=CORES["sidebar"])
        row_datas.pack(fill="x", padx=20, pady=(0, 10))

        col_de = tk.Frame(row_datas, bg=CORES["sidebar"])
        col_de.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(col_de, text="De", font=self.font_small,
                 fg=CORES["text_muted"], bg=CORES["sidebar"]).pack(anchor="w")
        self.entry_data_ini = tk.Entry(
            col_de, font=self.font_label,
            bg=CORES["card"], fg=CORES["text"],
            insertbackground=CORES["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=CORES["border"],
            highlightcolor=CORES["accent"],
        )
        self.entry_data_ini.insert(0, date.today().strftime("%d/%m/%Y"))
        self.entry_data_ini.pack(fill="x", pady=(2, 0))

        col_ate = tk.Frame(row_datas, bg=CORES["sidebar"])
        col_ate.pack(side="left", fill="x", expand=True)
        tk.Label(col_ate, text="Até", font=self.font_small,
                 fg=CORES["text_muted"], bg=CORES["sidebar"]).pack(anchor="w")
        self.entry_data_fim = tk.Entry(
            col_ate, font=self.font_label,
            bg=CORES["card"], fg=CORES["text"],
            insertbackground=CORES["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=CORES["border"],
            highlightcolor=CORES["accent"],
        )
        self.entry_data_fim.insert(0, date.today().strftime("%d/%m/%Y"))
        self.entry_data_fim.pack(fill="x", pady=(2, 0))

        self._field_label(self.sidebar, "Seções do DOU")
        self.entry_secoes = self._entry(self.sidebar)
        self.entry_secoes.insert(0, "DO1 DO1E")
        self.entry_secoes.pack(fill="x", **pad, pady=(2, 10))

        self._separator(self.sidebar)

        #Palavras-chave
        self._section_label(self.sidebar, "PALAVRAS-CHAVE")
        tk.Label(
            self.sidebar, text="Uma por linha",
            font=self.font_small, fg=CORES["text_muted"], bg=CORES["sidebar"],
        ).pack(anchor="w", padx=20)

        self.text_palavras = tk.Text(
            self.sidebar, height=6,
            font=self.font_mono,
            bg=CORES["card"], fg=CORES["text"],
            insertbackground=CORES["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=CORES["border"],
            highlightcolor=CORES["accent"],
        )
        self.text_palavras.insert("1.0",
                                  )
        self.text_palavras.pack(fill="x", padx=20, pady=(4, 16))

        #Botão principal
        self.btn_buscar = tk.Button(
            self.sidebar,
            text="▶  Iniciar Busca",
            font=tkFont.Font(family="Segoe UI", size=10, weight="bold"),
            fg="white", bg=CORES["accent"],
            activebackground=CORES["accent_dark"],
            activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._iniciar_busca, pady=10,
        )
        self.btn_buscar.pack(fill="x", padx=20, pady=(0, 16))

    #Conteúdo

    def _build_content(self):
        top = tk.Frame(self.content, bg=CORES["bg"], height=48)
        top.pack(fill="x")
        top.pack_propagate(False)

        self.lbl_contagem = tk.Label(
            top, text="0 resultados",
            font=tkFont.Font(family="Segoe UI", size=10, weight="bold"),
            fg=CORES["text_muted"], bg=CORES["bg"],
        )
        self.lbl_contagem.pack(side="left", padx=20, pady=12)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=CORES["bg"], borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=CORES["card"], foreground=CORES["text_muted"],
            padding=[14, 6], borderwidth=0,
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", CORES["accent"])],
            foreground=[("selected", "white")],
        )

        self.notebook = ttk.Notebook(self.content, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.frame_resultados = tk.Frame(self.notebook, bg=CORES["bg"])
        self.notebook.add(self.frame_resultados, text="  Resultados  ")
        self._build_aba_resultados()

        self.frame_log = tk.Frame(self.notebook, bg=CORES["bg"])
        self.notebook.add(self.frame_log, text="  Log  ")
        self._build_aba_log()

    def _build_aba_resultados(self):
        cols = ("Data", "Palavra", "Secao", "Pagina", "Orgao", "Titulo")

        frame = tk.Frame(self.frame_resultados, bg=CORES["bg"])
        frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure(
            "Dark.Treeview",
            background=CORES["card"], foreground=CORES["text"],
            fieldbackground=CORES["card"], rowheight=28, borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Dark.Treeview.Heading",
            background=CORES["sidebar"], foreground=CORES["text_muted"],
            relief="flat", font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "Dark.Treeview",
            background=[("selected", CORES["accent"])],
            foreground=[("selected", "white")],
        )

        self.tree = ttk.Treeview(
            frame, columns=cols, show="headings", style="Dark.Treeview",
        )

        labels = ("Data",   "Palavra", "Seção", "Página", "Órgão",  "Título")
        widths = (90,       90,        60,      60,       180,      300)
        for col, lbl, w in zip(cols, labels, widths):
            self.tree.heading(col, text=lbl)
            self.tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("par",   background="#1C2333")
        self.tree.tag_configure("impar", background="#19202E")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        #Painel de detalhe
        self.frame_detalhe = tk.Frame(
            self.frame_resultados, bg=CORES["sidebar"], height=350
        )
        self.frame_detalhe.pack(fill="x")
        self.frame_detalhe.pack_propagate(False)

        # Borda superior de destaque
        tk.Frame(self.frame_detalhe, bg=CORES["border"], height=1).pack(fill="x")

        #Cabeçalho
        tk.Label(
            self.frame_detalhe, text="DETALHES DA OCORRÊNCIA",
            font=self.font_section, fg=CORES["accent"], bg=CORES["sidebar"],
        ).pack(anchor="w", padx=16, pady=(8, 6))

        #Linha 1 de metadados: Data | Palavra | Seção | Página
        row1 = tk.Frame(self.frame_detalhe, bg=CORES["sidebar"])
        row1.pack(fill="x", padx=16, pady=(0, 4))

        self._lbl_meta_data    = self._meta_field(row1, "DATA",    "—")
        self._lbl_meta_palavra = self._meta_field(row1, "PALAVRA", "—")
        self._lbl_meta_secao   = self._meta_field(row1, "SEÇÃO",   "—")
        self._lbl_meta_pagina  = self._meta_field(row1, "PÁGINA",  "—")

        #Linha 2 de metadados: Órgão
        row2 = tk.Frame(self.frame_detalhe, bg=CORES["sidebar"])
        row2.pack(fill="x", padx=16, pady=(0, 4))

        self._lbl_meta_orgao = self._meta_field(row2, "ÓRGÃO", "—", expand=True)

        #Linha 3 de metadados: Título
        row3 = tk.Frame(self.frame_detalhe, bg=CORES["sidebar"])
        row3.pack(fill="x", padx=16, pady=(0, 6))

        self._lbl_meta_titulo = self._meta_field(row3, "TÍTULO", "—", expand=True)

        #Separador
        tk.Frame(self.frame_detalhe, bg=CORES["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 6)
        )

        #Label TRECHO
        tk.Label(
            self.frame_detalhe, text="TRECHO",
            font=self.font_section, fg=CORES["text_muted"], bg=CORES["sidebar"],
        ).pack(anchor="w", padx=16, pady=(0, 2))

        self.txt_trecho = tk.Text(
            self.frame_detalhe,
            font=self.font_mono, bg=CORES["sidebar"], fg=CORES["text"],
            relief="flat", bd=0, wrap="word", height=4, state="disabled",
        )
        self.txt_trecho.pack(fill="x", padx=16, pady=(0, 10))
        self.txt_trecho.tag_configure(
            "destaque", foreground=CORES["highlight"],
            font=tkFont.Font(family="Consolas", size=9, weight="bold")
        )
        self.txt_trecho.tag_configure(
            "link", foreground=CORES["accent"],
            font=tkFont.Font(family="Consolas", size=9, underline=True)
        )
        self.txt_trecho.tag_bind("link", "<Enter>",
            lambda e: self.txt_trecho.configure(cursor="hand2"))
        self.txt_trecho.tag_bind("link", "<Leave>",
            lambda e: self.txt_trecho.configure(cursor=""))
        self.txt_trecho.tag_bind("link", "<Button-1>", self._abrir_link)

    #Helper para campo de metadado

    def _meta_field(self, parent, label, valor_inicial, expand=False):
        """Cria um bloco label+valor inline. Retorna o Label de valor."""
        bloco = tk.Frame(parent, bg=CORES["card"],
                         highlightthickness=1,
                         highlightbackground=CORES["border"])
        bloco.pack(side="left", padx=(0, 6), ipadx=8, ipady=4,
                   fill="x" if expand else "none",
                   expand=expand)

        tk.Label(
            bloco, text=label,
            font=self.font_meta_lbl,
            fg=CORES["text_muted"], bg=CORES["card"],
        ).pack(anchor="w", padx=6, pady=(3, 0))

        lbl_val = tk.Label(
            bloco, text=valor_inicial,
            font=self.font_meta_val,
            fg=CORES["text"], bg=CORES["card"],
            anchor="w",
        )
        lbl_val.pack(anchor="w", padx=6, pady=(0, 3))
        return lbl_val

    def _build_aba_log(self):
        self.txt_log = scrolledtext.ScrolledText(
            self.frame_log,
            font=self.font_mono, bg=CORES["card"], fg=CORES["text"],
            insertbackground=CORES["accent"],
            relief="flat", bd=0, state="disabled",
        )
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=10)

        self.txt_log.tag_configure("accent",  foreground=CORES["accent"])
        self.txt_log.tag_configure("success", foreground=CORES["success"])
        self.txt_log.tag_configure("warning", foreground=CORES["warning"])
        self.txt_log.tag_configure("danger",  foreground=CORES["danger"])
        self.txt_log.tag_configure("muted",   foreground=CORES["text_muted"])

    #Helpers de UI

    def _entry(self, parent, **kw):
        return tk.Entry(
            parent,
            font=self.font_label,
            bg=CORES["card"], fg=CORES["text"],
            insertbackground=CORES["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=CORES["border"],
            highlightcolor=CORES["accent"],
            **kw,
        )

    def _separator(self, parent):
        tk.Frame(parent, bg=CORES["border"], height=1).pack(
            fill="x", padx=20, pady=10
        )

    def _section_label(self, parent, text):
        tk.Label(
            parent, text=text,
            font=self.font_section, fg=CORES["accent"], bg=CORES["sidebar"],
        ).pack(anchor="w", padx=20, pady=(6, 4))

    def _field_label(self, parent, text):
        tk.Label(
            parent, text=text,
            font=self.font_small, fg=CORES["text_muted"], bg=CORES["sidebar"],
        ).pack(anchor="w", padx=20)

    #Ações
    def _iniciar_busca(self):
        email        = self.entry_email.get().strip()
        senha        = self.entry_senha.get().strip()
        data_ini_str = self.entry_data_ini.get().strip()
        data_fim_str = self.entry_data_fim.get().strip()
        secoes       = self.entry_secoes.get().strip()
        palavras_raw = self.text_palavras.get("1.0", "end").strip()
        palavras     = [p.strip() for p in palavras_raw.splitlines() if p.strip()]

        if not email or not senha:
            messagebox.showwarning("Atenção", "Preencha e-mail e senha.")
            return

        fmt = "%d/%m/%Y"
        try:
            data_ini = datetime.strptime(data_ini_str, fmt).date()
            data_fim = datetime.strptime(data_fim_str, fmt).date()
        except ValueError:
            messagebox.showwarning("Atenção", "Datas inválidas. Use DD/MM/AAAA.")
            return

        if data_ini > data_fim:
            messagebox.showwarning("Atenção", "A data inicial não pode ser maior que a final.")
            return

        n_dias = (data_fim - data_ini).days + 1
        if n_dias > 31:
            if not messagebox.askyesno(
                "Intervalo longo",
                f"O intervalo cobre {n_dias} dias. Isso pode demorar bastante.\nContinuar?"
            ):
                return

        if not palavras:
            messagebox.showwarning("Atenção", "Informe ao menos uma palavra-chave.")
            return

        self._limpar()
        self.btn_buscar.configure(state="disabled", text="Buscando...")
        self._log("Iniciando sessão…", "muted")
        self.notebook.select(self.frame_log)

        def run():
            try:
                self.session.post(
                    URL_LOGIN,
                    data={"email": email, "password": senha},
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                    timeout=15,
                )
                cookie = self.session.cookies.get("inlabs_session_cookie")
                if not cookie:
                    self._log("Login ou senha incorretos.", "danger")
                    self.after(0, lambda: self.lbl_conexao.configure(
                        text="● Desconectado", fg=CORES["danger"]))
                    self._finalizar_busca(None)
                    return

                self._log("Login realizado com sucesso.", "success")
                self.after(0, lambda: self.lbl_conexao.configure(
                    text="● Conectado", fg=CORES["success"]))

                fazer_download(
                    session=self.session,
                    data_ini=data_ini,
                    data_fim=data_fim,
                    tipo_dou=secoes,
                    palavras=palavras,
                    callback_resultado=self._adicionar_resultado,
                    callback_log=self._log,
                    callback_progresso=self._atualizar_progresso,
                    callback_fim=self._finalizar_busca,
                )
            except requests.exceptions.ConnectionError:
                self._log("Erro de conexão. Verifique a internet.", "danger")
                self.after(0, lambda: self.lbl_conexao.configure(
                    text="● Desconectado", fg=CORES["danger"]))
                self._finalizar_busca(None)

        threading.Thread(target=run, daemon=True).start()

    def _limpar(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.resultados.clear()
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")
        self._limpar_detalhe()
        self.lbl_contagem.configure(text="0 resultados", fg=CORES["text_muted"])

    def _limpar_detalhe(self):
        """Reseta todos os campos do painel de detalhes."""
        for lbl in (
            self._lbl_meta_data, self._lbl_meta_palavra,
            self._lbl_meta_secao, self._lbl_meta_pagina,
            self._lbl_meta_orgao, self._lbl_meta_titulo,
        ):
            lbl.configure(text="—")
        self.txt_trecho.configure(state="normal")
        self.txt_trecho.delete("1.0", "end")
        self.txt_trecho.configure(state="disabled")

    #Callbacks (thread-safe via after)
    def _log(self, msg, tag="text"):
        def _do():
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", msg + "\n", tag)
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        self.after(0, _do)

    def _atualizar_progresso(self, valor, label=""):
        pass  # barra de progresso removida

    def _adicionar_resultado(self, r):
        def _do():
            self.resultados.append(r)
            n = len(self.resultados)
            tag = "par" if n % 2 == 0 else "impar"
            self.tree.insert(
                "", "end",
                values=(
                    r["pub_date"],
                    r["palavra"],
                    r["secao"],
                    r["pagina"],
                    r["orgao"],
                    r["titulo"],
                ),
                tags=(tag,),
            )
            self.lbl_contagem.configure(
                text=f"{n} resultado{'s' if n != 1 else ''}",
                fg=CORES["success"],
            )
            self._log(f'  ✔ "{r["palavra"]}" — {r["orgao"]}', "success")
        self.after(0, _do)

    def _finalizar_busca(self, total):
        def _do():
            self.btn_buscar.configure(state="normal", text="▶  Iniciar Busca")
            if total is not None:
                self._log(
                    f"\n{'─'*50}\n Busca concluída — {total} ocorrência(s) encontrada(s).",
                    "success",
                )
                self.notebook.select(self.frame_resultados)
            else:
                self._log("Busca encerrada com erro.", "danger")
        self.after(0, _do)

    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if idx >= len(self.resultados):
            return
        r = self.resultados[idx]

        #Atualiza metadados
        self._lbl_meta_data.configure(text=r["pub_date"])
        self._lbl_meta_palavra.configure(text=r["palavra"])
        self._lbl_meta_secao.configure(text=r["secao"])
        self._lbl_meta_pagina.configure(text=r["pagina"])
        self._lbl_meta_orgao.configure(text=r["orgao_raw"])
        self._lbl_meta_titulo.configure(text=r["titulo"])

        #Atualiza trecho
        self.txt_trecho.configure(state="normal")
        self.txt_trecho.delete("1.0", "end")

        trecho  = r["trecho"]
        pos     = r["pos_rel"]
        tam     = r["palavra_len"]

        self.txt_trecho.insert("end", trecho[:pos])
        self.txt_trecho.insert("end", trecho[pos:pos + tam], "destaque")
        self.txt_trecho.insert("end", trecho[pos + tam:])

        if r["link"]:
            self.txt_trecho.insert("end", "\n\n🔗 ")
            self.txt_trecho.insert("end", r["link"], "link")

        self.txt_trecho.configure(state="disabled")

    def _abrir_link(self, event):
        idx = self.txt_trecho.index(tk.CURRENT)
        tags = self.txt_trecho.tag_names(idx)
        if "link" in tags:
            range_ = self.txt_trecho.tag_prevrange("link", idx + "+1c")
            if range_:
                url = self.txt_trecho.get(*range_)
                webbrowser.open(url.strip())


#Main

if __name__ == "__main__":
    app = App()
    app.mainloop()
