import os

from django.core.management.base import BaseCommand, CommandError

from logistics.mcp_server import BearerTokenMiddleware, build_server


class Command(BaseCommand):
    help = "Run the Route Tracker MCP server over stdio (local clients) or Streamable HTTP (remote clients)."

    def add_arguments(self, parser):
        parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
        parser.add_argument("--host", default="127.0.0.1", help="HTTP only.")
        parser.add_argument("--port", type=int, default=8001, help="HTTP only.")

    def handle(self, *args, **options):
        server = build_server()
        if options["transport"] == "stdio":
            # stdout carries the protocol, so nothing else may print to it.
            server.run("stdio")
            return

        token = os.environ.get("MCP_TOKEN")
        if not token:
            raise CommandError("Set MCP_TOKEN before serving over HTTP. Clients send it as a bearer token.")

        import uvicorn
        from mcp.server.transport_security import TransportSecuritySettings

        allowed_hosts = os.environ.get("MCP_ALLOWED_HOSTS", f"localhost:{options['port']},127.0.0.1:{options['port']}")
        security = TransportSecuritySettings(allowed_hosts=[h.strip() for h in allowed_hosts.split(",") if h.strip()])
        # Stateless JSON responses: no session affinity, so it scales like any other HTTP service.
        app = server.streamable_http_app(
            stateless_http=True, json_response=True, transport_security=security, host=options["host"]
        )
        self.stderr.write(f"MCP server on http://{options['host']}:{options['port']}/mcp")
        uvicorn.run(BearerTokenMiddleware(app, token), host=options["host"], port=options["port"], log_level="info")
