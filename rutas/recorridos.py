def validar_ruta(ruta, cantidad):
    if len(ruta) != cantidad or set(ruta) != set(range(cantidad)):
        raise ValueError("La ruta debe visitar cada ciudad exactamente una vez.")


def distancia_total(ruta, matriz):
    return sum(matriz[ruta[i]][ruta[(i + 1) % len(ruta)]] for i in range(len(ruta)))


def ruta_canonica(ruta):
    posicion = ruta.index(0)
    directa = tuple(ruta[posicion:] + ruta[:posicion])
    inversa = (0,) + tuple(reversed(directa[1:]))
    return min(directa, inversa)


def vecino_cercano(matriz, inicio, rng):
    pendientes = set(range(len(matriz))) - {inicio}
    ruta = [inicio]
    while pendientes:
        mejor = min(matriz[ruta[-1]][j] for j in pendientes)
        candidatos = sorted(j for j in pendientes if matriz[ruta[-1]][j] == mejor)
        siguiente = rng.choice(candidatos)
        ruta.append(siguiente)
        pendientes.remove(siguiente)
    return ruta


def mejorar_2opt(ruta, matriz, max_cambios):
    ruta = ruta.copy()
    n = len(ruta)
    cambios = 0
    while cambios < max_cambios:
        encontrado = False
        for i in range(n - 2):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue
                a, b = ruta[i], ruta[i + 1]
                c, d = ruta[j], ruta[(j + 1) % n]
                if matriz[a][c] + matriz[b][d] < matriz[a][b] + matriz[c][d] - 1e-9:
                    ruta[i + 1:j + 1] = reversed(ruta[i + 1:j + 1])
                    cambios += 1
                    encontrado = True
                    break
            if encontrado:
                break
        if not encontrado:
            break
    return ruta
