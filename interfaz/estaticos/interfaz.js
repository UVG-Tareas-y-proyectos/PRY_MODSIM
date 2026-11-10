(() => {
  function iniciar() {
    const raiz = document.getElementById('traza-app');
    if (!raiz || !window.TrazaGraficas) return false;
    if (raiz.dataset.iniciada) return true;
    raiz.dataset.iniciada = 'true';
    const $ = id => raiz.querySelector(`#${id}`);
    const estado = {instancia: null, trabajo: null, activo: false, serie: [], seriesEnVivo: {},
      informes: [], archivos: [], informe: null, corrida: null, ruta: null, reproduccion: null,
      consulta: null, ultimaSolicitud: null, escenarioVisible: null};
    const formato = (valor, decimales = 3) => valor === null || valor === undefined ? '—' : Number(valor).toLocaleString('es-GT', {maximumFractionDigits: decimales});

    async function api(ruta, opciones = {}) {
      const respuesta = await fetch(ruta, opciones);
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.detail || datos.mensaje || 'No se pudo completar la operación.');
      return datos;
    }
    const enviar = (ruta, datos = {}) => api(ruta, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(datos)});
    function aviso(mensaje) { $('avisos').textContent = mensaje; }
    function error(mensaje) { $('error-formulario').textContent = mensaje; $('error-formulario').hidden = !mensaje; }
    function cambiarEstado(nombre, detalle = '') {
      $('estado').textContent = nombre; $('detalle-estado').textContent = detalle;
      $('estado').classList.toggle('activo', estado.activo);
    }
    function detenerReproduccion() {
      clearInterval(estado.reproduccion); estado.reproduccion = null;
      $('reproducir').textContent = 'Reproducir';
    }
    function bloquear(valor) {
      estado.activo = valor;
      raiz.querySelectorAll('#formulario input, #formulario select, #cargar, #crear').forEach(el => el.disabled = valor);
      $('ejecutar').disabled = valor; $('detener').hidden = !valor;
      $('detener').disabled = false;
      $('historial').disabled = valor;
      $('escenario').disabled = valor;
      $('estado').classList.toggle('activo', valor);
    }
    function mostrarInstancia(instancia) {
      estado.instancia = instancia;
      $('nombre-escenario').textContent = instancia.nombre === 'demo10' ? 'Prueba de diez ciudades' : instancia.nombre;
      $('descripcion-escenario').textContent = 'Un recorrido cerrado. Todas las ciudades, una vez.';
      $('contexto').textContent = `${instancia.cantidad} ciudades / ${instancia.tipo === 'GEO' ? 'distancia geográfica' : instancia.tipo === 'EUC_2D' ? 'distancia euclidiana redondeada' : 'distancia euclidiana real'}`;
      $('pie-referencia').textContent = instancia.optimo !== null ? `Óptimo publicado: ${formato(instancia.optimo, 0)} / TSPLIB` : 'La referencia se obtiene cuando el modelo demuestra el óptimo.';
    }
    function referencia() {
      if (estado.informe?.tabla?.length) return estado.informe.tabla[0].optimo_teorico;
      return estado.instancia?.optimo;
    }
    function pintar(ruta = estado.ruta, metodo = 'ga') {
      if (!estado.instancia) return;
      estado.ruta = ruta;
      if ($('vista-simulacion').hidden) return;
      const lp = metodo === 'lp' ? null : estado.informe?.lp?.ruta;
      window.TrazaGraficas.ruta($('grafica-ruta'), estado.instancia, ruta, lp, metodo);
    }
    function convergencia() {
      if ($('vista-simulacion').hidden) return;
      const series = estado.informe ? estado.informe.corridas : Object.values(estado.seriesEnVivo);
      window.TrazaGraficas.convergencia($('grafica-convergencia'), series, referencia());
    }
    function metricas(distancia, generacion, tipo = 'ga') {
      $('distancia').textContent = formato(distancia);
      $('etiqueta-generacion').textContent = tipo === 'lp' ? 'Restricciones del modelo' : 'Generación';
      $('generacion').textContent = generacion === null || generacion === undefined ? '—' : formato(generacion, 0);
      const optimo = referencia();
      $('error').textContent = optimo !== null && optimo !== undefined && distancia !== null
        ? (optimo === 0 && distancia !== 0 ? '—' : `${formato(optimo === 0 ? 0 : Math.max(0, (distancia - optimo) / optimo * 100), 2)} %`) : '—';
    }
    function limpiar() {
      detenerReproduccion(); estado.informe = null; estado.corrida = null; estado.ruta = null;
      estado.seriesEnVivo = {}; $('reproducir').disabled = true; $('fotograma').disabled = true;
      $('corrida').parentElement.hidden = true;
      $('rotulo-ruta').textContent = 'CIUDADES DEL ESCENARIO';
      $('estado-modelo').textContent = 'Sin ejecución todavía';
      $('posicion-reproduccion').textContent = 'Sin recorrido guardado';
      metricas(null, null); pintar(null); convergencia();
    }
    async function seleccionarEscenario() {
      try {
        const nombre = $('escenario').value === 'todos' ? 'eil101' : $('escenario').value;
        const instancia = await api(`/api/escenario/${encodeURIComponent(nombre)}`);
        mostrarInstancia(instancia); limpiar(); error('');
        if ($('escenario').value === 'todos') aviso('Se ejecutarán eil101, gr229 y el escenario propio, en ese orden.');
        else aviso('');
      } catch (e) { error(e.message); }
    }
    function actualizarMetodo() {
      const metodo = $('metodo').value;
      $('parametros-ga').hidden = metodo === 'lp'; $('parametros-lp').hidden = metodo === 'ga';
      $('parametros-ga').querySelectorAll('input, select').forEach(el => el.disabled = metodo === 'lp');
    }
    function solicitud() {
      if ($('metodo').value === 'lp') return {
        escenario: $('escenario').value, metodo: 'lp', configuracion: {}, semillas: [11],
        limite_lp: Number($('limite-lp').value), exportar_graficas: $('exportar-graficas').checked,
        exportar_gif: false};
      const entero = id => {
        const valor = Number($(id).value);
        if (!Number.isInteger(valor)) throw new Error(`${$(id).previousElementSibling?.textContent || id} debe ser un entero.`);
        return valor;
      };
      const partes = $('semillas').value.split(',').map(s => s.trim());
      if (partes.some(s => !/^-?\d+$/.test(s))) throw new Error('Las semillas deben ser enteros separados por coma.');
      return {escenario: $('escenario').value, metodo: $('metodo').value,
        configuracion: {poblacion: entero('poblacion'), iteraciones: entero('iteraciones'), seleccion: $('seleccion').value,
          sobrevivientes: Number($('sobrevivientes').value) / 100, cruce: Number($('cruce').value) / 100,
          mutacion: Number($('mutacion').value) / 100, torneo: entero('torneo'),
          inicializacion: $('inicializacion').value, mejora_local: entero('mejora-local')},
        semillas: partes.map(Number), limite_lp: Number($('limite-lp').value),
        exportar_graficas: $('exportar-graficas').checked, exportar_gif: $('exportar-gif').checked};
    }
    async function ejecutar(evento) {
      evento.preventDefault(); error(''); detenerReproduccion();
      try {
        const datos = solicitud();
        const respuesta = await enviar('/api/ejecuciones', datos);
        estado.trabajo = respuesta.id; estado.ultimaSolicitud = datos; estado.informes = [];
        estado.archivos = []; tabla(); archivos();
        estado.escenarioVisible = null; limpiar(); bloquear(true);
        $('descargar-todo').disabled = true; $('descargar-comparacion').disabled = true;
        cambiarEstado('En ejecución', 'Preparando el cálculo');
        await actualizarHistorial();
        consultar();
      } catch (e) { error(e.message); bloquear(false); actualizarMetodo(); }
    }
    async function consultar() {
      try {
        const datos = await api(`/api/ejecuciones/${estado.trabajo}`);
        for (const evento of datos.eventos) {
          if (evento.tipo === 'escenario') {
            mostrarInstancia(evento.instancia); estado.escenarioVisible = evento.instancia.nombre;
            limpiar(); cambiarEstado('En ejecución', `Escenario ${evento.numero} de ${evento.total}`);
          } else if (evento.tipo === 'progreso') {
            if (evento.etapa === 'ga') {
              const clave = `${evento.escenario}/${evento.semilla}`;
              if (!estado.seriesEnVivo[clave]) estado.seriesEnVivo[clave] = {semilla: evento.semilla, historial: []};
              estado.seriesEnVivo[clave].historial.push({generacion: evento.generacion, mejor: evento.mejor});
              estado.ruta = evento.ruta;
              metricas(evento.mejor, evento.generacion);
              $('rotulo-ruta').textContent = `GA / SEMILLA ${evento.semilla}`;
              cambiarEstado('Buscando recorrido', `Generación ${evento.generacion} de ${evento.iteraciones}`);
              $('estado-modelo').textContent = 'Mejor ruta de la generación actual';
            } else if (evento.etapa === 'lp') {
              estado.ruta = evento.ruta; metricas(evento.mejor, evento.restricciones, 'lp');
              $('rotulo-ruta').textContent = 'PROGRAMACIÓN ENTERA';
              cambiarEstado('Resolviendo modelo', `${evento.variables} variables / ${evento.restricciones} restricciones`);
              $('estado-modelo').textContent = evento.optima_demostrada ? 'Óptimo demostrado' : 'Ruta factible; todavía sin prueba de optimalidad';
            } else if (evento.etapa === 'exportando') cambiarEstado('Guardando resultados', evento.mensaje);
          }
        }
        const ultimo = datos.ultimo;
        if (estado.ruta) pintar(estado.ruta, ultimo?.etapa === 'lp' ? 'lp' : 'ga');
        convergencia();
        if (datos.estado === 'ejecutando') {
          estado.consulta = setTimeout(consultar, 250);
          return;
        }
        bloquear(false); actualizarMetodo();
        cambiarEstado(datos.estado === 'completo' ? 'Experimento terminado' : datos.estado === 'cancelado' ? 'Ejecución detenida' : 'No se pudo completar', datos.mensaje);
        if (datos.estado === 'error') error(datos.mensaje);
        await cargarResultados(); await actualizarHistorial();
      } catch (e) {
        error(`Se perdió la comunicación: ${e.message}`);
        if (estado.activo) estado.consulta = setTimeout(consultar, 1500);
      }
    }
    function agregarOpcion(selector, valor, texto) {
      const opcion = document.createElement('option'); opcion.value = valor; opcion.textContent = texto;
      selector.append(opcion);
    }
    async function cargarResultados() {
      const datos = await api(`/api/ejecuciones/${estado.trabajo}/resultados`);
      estado.informes = datos.informes; estado.archivos = datos.archivos;
      const selector = $('corrida'); selector.replaceChildren();
      estado.informes.forEach((informe, i) => {
        informe.corridas.forEach((corrida, j) => agregarOpcion(selector, `${i}/ga/${j}`, `${informe.instancia.nombre} · GA ${corrida.semilla}`));
        if (informe.lp) agregarOpcion(selector, `${i}/lp/0`, `${informe.instancia.nombre} · Modelo entero`);
      });
      selector.parentElement.hidden = !selector.options.length;
      if (selector.options.length) {
        let mejor = 0;
        if (estado.informes[0].corridas.length) mejor = estado.informes[0].corridas.reduce((indice, r, i, array) => r.distancia < array[indice].distancia ? i : indice, 0);
        selector.value = estado.informes[0].corridas.length ? `0/ga/${mejor}` : '0/lp/0';
        seleccionarCorrida();
      }
      tabla(); archivos();
      $('descargar-todo').disabled = !datos.archivos.includes('resultados.zip');
      $('descargar-comparacion').disabled = !datos.archivos.includes('comparacion_total.csv');
    }
    function seleccionarCorrida() {
      detenerReproduccion();
      const [i, metodo, j] = $('corrida').value.split('/');
      const informe = estado.informes[Number(i)]; if (!informe) return;
      estado.informe = informe;
      const instancia = informe.instancia;
      mostrarInstancia({...instancia, tipo: instancia.tipo_distancia, cantidad: instancia.ciudades.length, optimo: instancia.optimo_publicado});
      estado.corrida = metodo === 'lp' ? null : informe.corridas[Number(j)];
      const fotogramas = estado.corrida?.instantaneas || [];
      $('fotograma').max = Math.max(0, fotogramas.length - 1); $('fotograma').value = $('fotograma').max;
      $('fotograma').disabled = !fotogramas.length; $('reproducir').disabled = !fotogramas.length;
      if (metodo === 'lp') {
        const lp = informe.lp; pintar(lp.ruta, 'lp'); metricas(lp.distancia, lp.restricciones, 'lp');
        $('rotulo-ruta').textContent = 'PROGRAMACIÓN ENTERA';
        $('posicion-reproduccion').textContent = 'Resultado del modelo';
      } else mostrarFotograma();
      const lp = informe.lp;
      $('estado-modelo').textContent = lp ? (lp.optima_demostrada ? 'Modelo entero: óptimo demostrado' : lp.origen === 'inicio_factible' ? 'Modelo entero: se conservó el inicio factible' : 'Modelo entero: factible, sin prueba de optimalidad') : 'Modelo entero no ejecutado';
      convergencia();
    }
    function mostrarFotograma() {
      const corrida = estado.corrida; if (!corrida) return;
      const indice = Number($('fotograma').value), fotograma = corrida.instantaneas[indice];
      pintar(fotograma.ruta); metricas(fotograma.distancia, fotograma.generacion);
      $('rotulo-ruta').textContent = `${corrida.metodo} / SEMILLA ${corrida.semilla}`;
      $('posicion-reproduccion').textContent = `Generación ${fotograma.generacion} / ${corrida.configuracion.iteraciones}`;
    }
    function tabla() {
      const cuerpo = $('filas-comparacion'); cuerpo.replaceChildren();
      const filas = estado.informes.flatMap(informe => informe.tabla);
      if (!filas.length) {
        const fila = cuerpo.insertRow(); const celda = fila.insertCell(); celda.colSpan = 5;
        celda.textContent = 'No hay resultados completos todavía.'; celda.className = 'vacio';
      }
      filas.forEach(fila => {
        const tr = cuerpo.insertRow();
        const esLP = fila.metodo === 'LP';
        const etiqueta = esLP ? (fila.optima_demostrada_lp ? 'Óptimo demostrado' : fila.origen === 'inicio_factible' ? 'Inicio factible' : 'Factible, sin prueba') : 'Heurística';
        const celdas = [`${fila.escenario} / ${esLP ? 'Modelo entero' : `${fila.metodo} #${fila.puesto_ga}`}`,
          formato(fila.distancia_encontrada), `${formato(fila.tiempo_s, 2)} s`, fila.error_pct === null ? '—' : `${formato(fila.error_pct, 2)} %`, etiqueta];
        celdas.forEach(texto => {tr.insertCell().textContent = texto;});
      });
      $('referencia-comparacion').textContent = 'Tres recorridos GA distintos y resultado del modelo. El error usa TSPLIB o un óptimo demostrado; sin referencia queda vacío.';
      const detalles = $('detalle-modelo'); detalles.replaceChildren();
      estado.informes.filter(i => i.lp).forEach(informe => {
        const lp = informe.lp, p = document.createElement('p');
        p.textContent = `${informe.instancia.nombre}: ${lp.variables} variables, ${lp.restricciones} restricciones, ${lp.cortes} cortes. Cota inferior: ${formato(lp.cota_inferior)}. Brecha del solver: ${lp.gap_pct === null ? '—' : `${formato(lp.gap_pct, 2)} %`}.`;
        detalles.append(p);
      });
    }
    function descargar(nombre) {
      const enlace = document.createElement('a');
      enlace.href = `/api/ejecuciones/${estado.trabajo}/archivo?nombre=${encodeURIComponent(nombre)}`;
      enlace.download = nombre.split('/').pop(); document.body.append(enlace); enlace.click(); enlace.remove();
    }
    function archivos() {
      const lista = $('lista-archivos'); lista.replaceChildren();
      if (!estado.archivos.length) {const p = document.createElement('p'); p.textContent = 'Todavía no se generaron archivos.'; p.className = 'vacio'; lista.append(p);}
      estado.archivos.forEach(nombre => {
        const fila = document.createElement('div'), texto = document.createElement('span'), boton = document.createElement('button');
        fila.className = 'fila-archivo'; texto.textContent = nombre;
        boton.className = 'boton-texto'; boton.type = 'button'; boton.textContent = 'Descargar ↗';
        boton.setAttribute('aria-label', `Descargar ${nombre}`); boton.addEventListener('click', () => descargar(nombre));
        fila.append(texto, boton); lista.append(fila);
      });
    }
    async function actualizarHistorial() {
      const trabajos = await api('/api/historial'); const selector = $('historial'); selector.replaceChildren();
      agregarOpcion(selector, '', 'Selecciona una ejecución');
      trabajos.forEach((trabajo, i) => agregarOpcion(selector, trabajo.id, `${trabajo.escenario} / ${trabajo.metodo.toUpperCase()} / ${trabajos.length - i}`));
      if (estado.trabajo) selector.value = estado.trabajo;
      selector.parentElement.hidden = !trabajos.length;
    }
    function incorporarEscenario(datos) {
      agregarOpcion($('escenario'), datos.id, `${datos.instancia.nombre} / ${datos.instancia.cantidad} ciudades`);
      $('escenario').value = datos.id; mostrarInstancia(datos.instancia); limpiar(); error('');
    }
    $('formulario').addEventListener('submit', ejecutar);
    $('escenario').addEventListener('change', seleccionarEscenario);
    $('metodo').addEventListener('change', actualizarMetodo);
    $('detener').addEventListener('click', async () => {
      try {const datos = await enviar(`/api/ejecuciones/${estado.trabajo}/detener`); aviso(datos.mensaje); $('detener').disabled = true;}
      catch (e) {error(e.message);}
    });
    $('corrida').addEventListener('change', seleccionarCorrida);
    $('fotograma').addEventListener('input', () => {detenerReproduccion(); mostrarFotograma();});
    $('reproducir').addEventListener('click', () => {
      if (estado.reproduccion) {detenerReproduccion(); return;}
      if (Number($('fotograma').value) === Number($('fotograma').max)) $('fotograma').value = 0;
      mostrarFotograma(); $('reproducir').textContent = 'Pausar';
      estado.reproduccion = setInterval(() => {
        $('fotograma').value = Number($('fotograma').value) + 1; mostrarFotograma();
        if (Number($('fotograma').value) >= Number($('fotograma').max)) detenerReproduccion();
      }, 250);
    });
    $('descargar-comparacion').addEventListener('click', () => descargar('comparacion_total.csv'));
    $('descargar-todo').addEventListener('click', () => descargar('resultados.zip'));
    $('historial').addEventListener('change', async () => {
      if (estado.activo || !$('historial').value) return;
      estado.trabajo = $('historial').value;
      try {
        const trabajo = await api(`/api/ejecuciones/${estado.trabajo}`);
        if (trabajo.estado === 'ejecutando') {
          if (trabajo.instancia) mostrarInstancia(trabajo.instancia);
          limpiar(); bloquear(true); consultar();
        } else {
          await cargarResultados(); cambiarEstado('Ejecución guardada', 'Resultados de esta sesión');
        }
      }
      catch (e) {error(e.message);}
    });
    $('cargar').addEventListener('click', () => $('archivo').click());
    $('archivo').addEventListener('change', async () => {
      const archivo = $('archivo').files[0]; if (!archivo) return;
      try {
        if (archivo.size > 2 * 1024 * 1024) throw new Error('El archivo no puede superar 2 MB.');
        const datos = await api(`/api/cargar?nombre=${encodeURIComponent(archivo.name)}`, {method: 'POST', body: archivo});
        incorporarEscenario(datos); aviso('Archivo cargado y validado.');
      } catch (e) {error(e.message);} finally {$('archivo').value = '';}
    });
    $('crear').addEventListener('click', () => {$('error-generar').hidden = true; $('dialogo-generar').showModal();});
    $('cerrar-dialogo').addEventListener('click', () => $('dialogo-generar').close());
    $('formulario-generar').addEventListener('submit', async evento => {
      evento.preventDefault();
      try {
        const datos = await enviar('/api/generar', {ciudades: Number($('ciudades-nuevas').value), semilla: Number($('semilla-nueva').value)});
        incorporarEscenario(datos); $('dialogo-generar').close(); aviso('Escenario propio creado. Los archivos originales se conservaron.');
      } catch (e) {$('error-generar').textContent = e.message; $('error-generar').hidden = false;}
    });
    raiz.querySelectorAll('[role=tab]').forEach(tab => tab.addEventListener('click', () => {
      raiz.querySelectorAll('[role=tab]').forEach(otro => {
        const seleccionado = otro === tab;
        otro.setAttribute('aria-selected', String(seleccionado)); $(otro.getAttribute('aria-controls')).hidden = !seleccionado;
      });
      if (tab.id === 'tab-simulacion') {pintar(); convergencia();}
    }));
    raiz.querySelectorAll('[role=tab]').forEach((tab, indice, pestañas) => tab.addEventListener('keydown', evento => {
      let siguiente;
      if (evento.key === 'ArrowRight') siguiente = (indice + 1) % pestañas.length;
      if (evento.key === 'ArrowLeft') siguiente = (indice + pestañas.length - 1) % pestañas.length;
      if (siguiente !== undefined) {evento.preventDefault(); pestañas[siguiente].focus(); pestañas[siguiente].click();}
    }));
    $('tema').addEventListener('click', () => {
      const oscuro = raiz.classList.toggle('tema-oscuro');
      $('tema').textContent = oscuro ? 'Tema claro' : 'Tema oscuro';
      localStorage.setItem('traza-tema', oscuro ? 'oscuro' : 'claro'); pintar(); convergencia();
    });
    if (localStorage.getItem('traza-tema') === 'oscuro') {raiz.classList.add('tema-oscuro'); $('tema').textContent = 'Tema claro';}
    let esperaResize;
    window.addEventListener('resize', () => {clearTimeout(esperaResize); esperaResize = setTimeout(() => {pintar(); convergencia();}, 150);});
    actualizarMetodo(); seleccionarEscenario(); actualizarHistorial().catch(e => aviso(e.message));
    return true;
  }
  let intentos = 0;
  function esperarPagina() {if (!iniciar() && intentos++ < 100) setTimeout(esperarPagina, 100);}
  esperarPagina();
})();
