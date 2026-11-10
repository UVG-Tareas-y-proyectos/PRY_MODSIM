def preparar_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def puntos_para_grafica(instancia):
    if instancia.tipo != "GEO":
        return instancia.coordenadas, "x", "y"
    puntos = []
    for latitud, longitud in instancia.coordenadas:
        lat = int(latitud) + 5 * (latitud - int(latitud)) / 3
        lon = int(longitud) + 5 * (longitud - int(longitud)) / 3
        puntos.append((lon % 360, lat))
    return puntos, "Longitud (°E, 0–360)", "Latitud (°)"


def dibujar_ruta(ax, instancia, ruta, titulo):
    puntos, etiqueta_x, etiqueta_y = puntos_para_grafica(instancia)
    ax.scatter(*zip(*puntos), s=15, zorder=3)
    if ruta is not None:
        cerrada = ruta + [ruta[0]]
        ax.plot([puntos[i][0] for i in cerrada], [puntos[i][1] for i in cerrada], linewidth=1)
    if instancia.cantidad <= 30:
        for nombre, (x, y) in zip(instancia.ciudades, puntos):
            ax.annotate(nombre, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set(title=titulo, xlabel=etiqueta_x, ylabel=etiqueta_y, aspect="equal")
    ax.grid(alpha=0.2)


def guardar_graficas(instancia, corridas, lp, carpeta, referencia=None):
    plt = preparar_matplotlib()
    soluciones = []
    if corridas:
        mejor = min(corridas, key=lambda corrida: corrida["distancia"])
        soluciones.append((mejor["ruta"], f"{mejor['metodo']} | D = {mejor['distancia']:.2f}"))
    if lp:
        estado = "Óptimo demostrado" if lp["optima_demostrada"] else "Factible, sin prueba de optimalidad"
        if lp["origen"] == "inicio_factible":
            estado = "Ruta inicial; el solver no la mejoró"
        soluciones.append((lp["ruta"], f"LP | D = {lp['distancia']:.2f}\n{estado}"))
    fig, ejes = plt.subplots(1, len(soluciones), figsize=(6 * len(soluciones), 5), squeeze=False, layout="constrained")
    for ax, (ruta, titulo) in zip(ejes[0], soluciones):
        dibujar_ruta(ax, instancia, ruta, titulo)
    fig.suptitle(instancia.nombre)
    fig.savefig(carpeta / "rutas.png", dpi=150)
    plt.close(fig)
    if not corridas:
        return
    fig, ejes = plt.subplots(2, 1, figsize=(8, 6), sharex=True, layout="constrained")
    for corrida in corridas:
        historia = corrida["historial"]
        generaciones = [fila["generacion"] for fila in historia]
        ejes[0].plot(generaciones, [fila["mejor"] for fila in historia], label=f"Semilla {corrida['semilla']}")
        ejes[1].plot(generaciones, [fila["diversidad"] for fila in historia])
    if referencia is not None:
        ejes[0].axhline(referencia, color="black", linestyle="--", label="Óptimo de referencia")
    ejes[0].set_ylabel("Distancia de la mejor ruta")
    ejes[0].legend(fontsize=8)
    ejes[1].set(xlabel="Generación", ylabel="Fracción de rutas únicas", ylim=(0, 1.05))
    fig.savefig(carpeta / "convergencia.png", dpi=150)
    plt.close(fig)


def guardar_animacion(instancia, corrida, archivo):
    plt = preparar_matplotlib()
    from matplotlib.animation import FuncAnimation, PillowWriter
    fig, ax = plt.subplots(figsize=(7, 5), layout="constrained")
    fotogramas = corrida["instantaneas"]

    def actualizar(indice):
        ax.clear()
        estado = fotogramas[indice]
        titulo = f"{instancia.nombre} | Generación {estado['generacion']} | D = {estado['distancia']:.2f}"
        dibujar_ruta(ax, instancia, estado["ruta"], titulo)

    animacion = FuncAnimation(fig, actualizar, frames=len(fotogramas), interval=200)
    animacion.save(archivo, writer=PillowWriter(fps=5))
    plt.close(fig)
