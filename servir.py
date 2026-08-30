"""
servir.py - serve o dashboard_frota.html em localhost e o mantém atualizado
automaticamente: vigia a planilha de KM e, sempre que ela muda, regenera o
HTML e avisa as páginas abertas (SSE), que recarregam sozinhas.

Uso:
    python servir.py [planilha.xlsx] [porta]

  - planilha (padrão): "PA - CONTROLE DE KM (version 1).xlsx" ao lado deste
    arquivo (pode apontar outra, inclusive a (CORRIGIDO)).
  - porta (padrão): 8723.

Basta inserir os novos KM no Excel e salvar: em ~1,5s o dashboard regenera
e a aba aberta no navegador atualiza sozinha, preservando a rolagem.
"""
import argparse
import queue
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(DIR))

for _stream in (sys.stdout, sys.stderr):  # console pode ser cp1252 (Start-Process)
    try:
        _stream.reconfigure(errors="replace", line_buffering=True)
    except Exception:
        pass

from frota_utils import processar_planilha  # noqa: E402
from gerar_html import build_html  # noqa: E402

CLIENTES: set[queue.Queue] = set()
LOCK = threading.Lock()


def planilha_padrao() -> Path:
    return DIR / "PA - CONTROLE DE KM (version 1).xlsx"


def assinatura(path: Path):
    """Identifica o arquivo: (mtime, tamanho) — mudou = salvou/alteração."""
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def regenerar(path: Path) -> bool:
    try:
        df = processar_planilha(path)
    except Exception as e:
        print(f"! falha ao ler a planilha: {e}")
        return False
    if df.empty:
        print("! planilha sem abas mensais válidas; HTML não atualizado")
        return False
    try:
        html = build_html(df)
        (DIR / "dashboard_frota.html").write_text(html, encoding="utf-8")
    except Exception as e:
        print(f"! falha ao gerar o HTML: {e}")
        return False
    return True


def avisar() -> None:
    with LOCK:
        for fila in list(CLIENTES):
            fila.put("atualizar")


def vigiar(path: Path, intervalo: float = 1.5) -> None:
    ult = assinatura(path)
    if ult is None:
        print(f"! planilha não encontrada: {path}")
    else:
        print(f"  vigiando: {path.name} (muda o mês -> HTML regenera sozinho)")
    while True:
        time.sleep(intervalo)
        try:
            novo = assinatura(path)
            if novo is None or novo == ult:
                continue
            ult = novo
            if regenerar(path):
                avisar()
                print(f"-> {path.name} mudou: dashboard atualizado às {time.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"! erro no vigia: {e!r}")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIR), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/dashboard_frota.html")
            self.end_headers()
            return
        if self.path == "/eventos":
            self._eventos()
            return
        super().do_GET()

    def _eventos(self):
        fila: queue.Queue = queue.Queue()
        with LOCK:
            CLIENTES.add(fila)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                try:
                    msg = fila.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                try:
                    self.wfile.write(("data: " + msg + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with LOCK:
                CLIENTES.discard(fila)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Serve o dashboard e atualiza sozinho quando a planilha muda.")
    ap.add_argument("planilha", nargs="?", default=None)
    ap.add_argument("porta", nargs="?", type=int, default=8723)
    args = ap.parse_args(argv)

    planilha = Path(args.planilha) if args.planilha else planilha_padrao()
    porta = args.porta

    print("=" * 58)
    print("  Dashboard de Frota Carajás — atualização automática")
    print("=" * 58)
    if regenerar(planilha):
        print(f"  HTML gerado em: {DIR / 'dashboard_frota.html'}")

    threading.Thread(target=vigiar, args=(planilha,), daemon=True).start()

    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    url = f"http://localhost:{porta}/dashboard_frota.html"
    print(f"  abra: {url}")
    print("  (salve a planilha e a aba recarrega sozinha; Ctrl+C para parar)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print("=" * 58)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n encerrado.")


if __name__ == "__main__":
    main()