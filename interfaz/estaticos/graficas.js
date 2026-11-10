(() => {
  function colores() {
    const estilo = getComputedStyle(document.getElementById('traza-app'));
    const color = nombre => estilo.getPropertyValue(nombre).trim();
    return {papel: color('--papel'), fondo: color('--fondo'), tinta: color('--tinta'),
      suave: color('--suave'), linea: color('--rejilla'), ga: color('--naranja'), lp: color('--verde')};
  }

  function puntos(instancia) {
    return instancia.coordenadas.map(([x, y]) => {
      if (instancia.tipo !== 'GEO') return [x, y];
      const lat = Math.trunc(x) + 5 * (x - Math.trunc(x)) / 3;
      const lon = Math.trunc(y) + 5 * (y - Math.trunc(y)) / 3;
      return [((lon % 360) + 360) % 360, lat];
    });
  }

  function disposicion(elemento, x, y) {
    const c = colores();
    return {height: elemento.clientHeight, margin: {l: 55, r: 24, t: 18, b: 46},
      paper_bgcolor: c.papel, plot_bgcolor: c.papel, font: {family: 'Segoe UI, sans-serif', color: c.tinta, size: 11},
      showlegend: false, hovermode: 'closest', uirevision: 'escenario',
      xaxis: {title: {text: x}, gridcolor: c.linea, zeroline: false, nticks: 6},
      yaxis: {title: {text: y}, gridcolor: c.linea, zeroline: false, nticks: 5}};
  }

  function pintarRuta(elemento, instancia, ruta, lp = null, metodo = 'ga') {
    const coords = puntos(instancia), c = colores();
    const trazas = [];
    function recorrido(indices, nombre, color, guiones) {
      if (!indices || !indices.length) return;
      const cerrada = [...indices, indices[0]].map(i => coords[i]);
      trazas.push({type: 'scatter', mode: 'lines', name: nombre, x: cerrada.map(p => p[0]),
        y: cerrada.map(p => p[1]), line: {color, width: 2, dash: guiones ? 'dash' : 'solid'},
        hoverinfo: 'skip'});
    }
    recorrido(lp, 'Modelo entero', c.lp, true);
    recorrido(ruta, metodo === 'lp' ? 'Modelo entero' : 'GA', metodo === 'lp' ? c.lp : c.ga, false);
    trazas.push({type: 'scatter', mode: coords.length <= 30 ? 'markers+text' : 'markers',
      x: coords.map(p => p[0]), y: coords.map(p => p[1]), name: 'Ciudades',
      text: instancia.ciudades, textposition: 'top right', textfont: {size: 10},
      marker: {color: c.tinta, size: coords.length > 100 ? 4 : 6},
      customdata: instancia.ciudades, hovertemplate: 'Ciudad %{customdata}<extra></extra>'});
    const geo = instancia.tipo === 'GEO';
    const layout = disposicion(elemento, geo ? 'Longitud (°E, 0–360)' : 'x (unidades)', geo ? 'Latitud (°)' : 'y (unidades)');
    layout.yaxis.scaleanchor = 'x';
    layout.uirevision = instancia.nombre;
    if (window.Plotly) {
      window.Plotly.react(elemento, trazas, layout, {responsive: true, displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'], toImageButtonOptions: {filename: 'ruta_tsp'}});
    } else {
      graficaSVG(elemento, trazas, layout);
    }
  }

  function pintarConvergencia(elemento, series, referencia) {
    const c = colores();
    const trazas = series.filter(s => s.historial.length).map((serie, i) => ({type: 'scatter', mode: 'lines',
      name: `Semilla ${serie.semilla}`, x: serie.historial.map(p => p.generacion),
      y: serie.historial.map(p => p.mejor), line: {color: c.ga, width: 1.8, dash: i % 2 ? 'dot' : 'solid'},
      opacity: Math.max(.45, 1 - i * .12), hovertemplate: `Semilla ${serie.semilla}<br>Generación %{x}<br>Distancia %{y:.3f}<extra></extra>`}));
    const mayor = Math.max(1, ...trazas.flatMap(t => t.x));
    if (referencia !== null && referencia !== undefined) {
      trazas.push({type: 'scatter', mode: 'lines', name: 'Óptimo de referencia', x: [0, mayor],
        y: [referencia, referencia], line: {color: c.lp, width: 1.5, dash: 'dash'}});
    }
    const layout = disposicion(elemento, 'Generación', 'Distancia');
    layout.paper_bgcolor = c.fondo;
    layout.plot_bgcolor = c.fondo;
    layout.hovermode = 'x unified';
    layout.margin = {l: 58, r: 20, t: 10, b: 44};
    if (window.Plotly) window.Plotly.react(elemento, trazas, layout, {responsive: true, displaylogo: false});
    else graficaSVG(elemento, trazas, layout);
  }

  // La vista SVG permite conservar las gráficas si Plotly todavía está cargando.
  function graficaSVG(elemento, trazas, layout) {
    const c = colores(), ancho = Math.max(elemento.clientWidth, 260), alto = Math.max(elemento.clientHeight, 160);
    const m = layout.margin, datos = trazas.flatMap(t => t.x.map((x, i) => [x, t.y[i]]));
    let xs = datos.map(p => p[0]), ys = datos.map(p => p[1]);
    if (!xs.length) {xs = [0, 1]; ys = [0, 1];}
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const rangoX = maxX - minX || 1, rangoY = maxY - minY || 1;
    const px = x => m.l + 10 + (x - minX) / rangoX * (ancho - m.l - m.r - 20);
    const py = y => alto - m.b - 10 - (y - minY) / rangoY * (alto - m.t - m.b - 20);
    const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('width', ancho); svg.setAttribute('height', alto);
    svg.setAttribute('viewBox', `0 0 ${ancho} ${alto}`);
    function agregar(tipo, atributos, texto) {
      const nodo = document.createElementNS(ns, tipo);
      Object.entries(atributos).forEach(([k, v]) => nodo.setAttribute(k, v));
      if (texto !== undefined) nodo.textContent = texto;
      svg.append(nodo); return nodo;
    }
    for (let i = 0; i <= 4; i++) {
      const y = minY + rangoY * i / 4, x = minX + rangoX * i / 4;
      agregar('line', {x1: m.l, x2: ancho - m.r, y1: py(y), y2: py(y), stroke: c.linea});
      agregar('text', {x: m.l - 8, y: py(y) + 4, fill: c.suave, 'font-size': 10, 'text-anchor': 'end'}, y.toFixed(rangoY > 20 ? 0 : 1));
      agregar('text', {x: px(x), y: alto - m.b + 18, fill: c.suave, 'font-size': 10, 'text-anchor': 'middle'}, x.toFixed(rangoX > 20 ? 0 : 1));
    }
    trazas.forEach(traza => {
      if (traza.mode.includes('lines')) {
        agregar('polyline', {points: traza.x.map((x, i) => `${px(x)},${py(traza.y[i])}`).join(' '),
          fill: 'none', stroke: traza.line.color, 'stroke-width': traza.line.width,
          'stroke-dasharray': traza.line.dash === 'solid' ? '' : '5 4', opacity: traza.opacity || 1});
      }
      if (traza.mode.includes('markers')) traza.x.forEach((x, i) => {
        const circulo = agregar('circle', {cx: px(x), cy: py(traza.y[i]), r: traza.marker.size / 2, fill: c.tinta});
        const titulo = document.createElementNS(ns, 'title'); titulo.textContent = `Ciudad ${traza.text[i]}`; circulo.append(titulo);
        if (traza.mode.includes('text')) agregar('text', {x: px(x) + 6, y: py(traza.y[i]) - 6, fill: c.tinta, 'font-size': 10}, traza.text[i]);
      });
    });
    agregar('text', {x: ancho / 2, y: alto - 6, fill: c.suave, 'font-size': 10, 'text-anchor': 'middle'}, layout.xaxis.title.text);
    agregar('text', {x: 15, y: alto / 2, fill: c.suave, 'font-size': 10, 'text-anchor': 'middle', transform: `rotate(-90 15 ${alto / 2})`}, layout.yaxis.title.text);
    elemento.replaceChildren(svg);
  }

  window.TrazaGraficas = {ruta: pintarRuta, convergencia: pintarConvergencia};
})();
