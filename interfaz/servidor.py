from pathlib import Path

from .servicio import Laboratorio


ESTATICOS = Path(__file__).parent / "estaticos"


def iniciar_servidor(puerto=8080, carpeta=None):
    from fastapi import HTTPException, Request
    from fastapi.responses import FileResponse
    from nicegui import app, ui

    laboratorio = Laboratorio(carpeta)
    app.add_static_files("/laboratorio", ESTATICOS)

    def respuesta(accion):
        try:
            return accion()
        except (ValueError, TypeError, KeyError, OSError, RuntimeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/escenario/{nombre}")
    def escenario(nombre: str):
        return respuesta(lambda: laboratorio.vista_escenario(nombre))

    @app.post("/api/ejecuciones")
    async def ejecutar(request: Request):
        solicitud = await request.json()
        return respuesta(lambda: laboratorio.iniciar(solicitud))

    @app.get("/api/ejecuciones/{identificador}")
    def consultar(identificador: str):
        return respuesta(lambda: laboratorio.buscar(identificador).consultar())

    @app.post("/api/ejecuciones/{identificador}/detener")
    def detener(identificador: str):
        respuesta(lambda: laboratorio.buscar(identificador).detener())
        return {"mensaje": "Se detendrá al terminar el cálculo en curso"}

    @app.get("/api/ejecuciones/{identificador}/resultados")
    def resultados(identificador: str):
        return respuesta(lambda: laboratorio.buscar(identificador).resultados())

    @app.get("/api/ejecuciones/{identificador}/archivo")
    def descargar(identificador: str, nombre: str):
        archivo = respuesta(lambda: laboratorio.archivo(identificador, nombre))
        return FileResponse(archivo, filename=archivo.name)

    @app.get("/api/historial")
    def historial():
        return laboratorio.historial()

    @app.post("/api/cargar")
    async def cargar(request: Request, nombre: str):
        contenido = bytearray()
        async for parte in request.stream():
            contenido.extend(parte)
            if len(contenido) > 2 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="El archivo no puede superar 2 MB.")
        return respuesta(lambda: laboratorio.cargar(bytes(contenido), nombre))

    @app.post("/api/generar")
    async def generar(request: Request):
        datos = await request.json()
        return respuesta(lambda: laboratorio.generar(datos.get("ciudades"), datos.get("semilla")))

    @app.get("/laboratorio-plotly.js")
    def plotly_js():
        import plotly
        return FileResponse(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", media_type="application/javascript")

    @ui.page("/")
    def pagina():
        ui.add_head_html('<link rel="stylesheet" href="/laboratorio/estilos.css">')
        ui.add_head_html('<script defer src="/laboratorio-plotly.js"></script>')
        ui.html((ESTATICOS / "index.html").read_text(encoding="utf-8"))
        ui.add_body_html('<script defer src="/laboratorio/graficas.js"></script>')
        ui.add_body_html('<script defer src="/laboratorio/interfaz.js"></script>')

    app.on_shutdown(laboratorio.cerrar)
    ui.run(host="127.0.0.1", port=puerto, title="TRAZA · Laboratorio TSP", reload=False, show=False)
