import http.server
import socketserver
from pathlib import Path

PORT = 8000
DIRECTORY = Path(__file__).resolve().parent

class ReportHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)


def main():
    print(f"Serving files from: {DIRECTORY}")
    print(f"Open this link in your browser:\nhttp://127.0.0.1:{PORT}/emerging_players_report.md")
    print("Press Ctrl+C to stop.")

    with socketserver.TCPServer(("", PORT), ReportHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Stopping server...")
            httpd.server_close()


if __name__ == "__main__":
    main()
