const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const base = process.env.TRAZA_URL || 'http://127.0.0.1:8765';
const capturas = process.env.TRAZA_CAPTURAS;

(async () => {
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
  const errores = [];
  page.on('pageerror', error => errores.push(error.message));
  try {
    await page.goto(base);
    await page.waitForFunction(() => document.querySelector('#contexto')?.textContent.includes('10 ciudades'));
    await page.waitForSelector('#grafica-ruta svg');
    if (capturas) {fs.mkdirSync(capturas, {recursive: true}); await page.screenshot({path: path.join(capturas, 'inicio.png'), fullPage: true});}
    await page.fill('#poblacion', '40');
    await page.fill('#iteraciones', '40');
    await page.fill('#semillas', '11,22');
    await page.uncheck('#exportar-graficas');
    await page.click('#ejecutar');
    await page.waitForFunction(() => document.querySelector('#estado').textContent === 'Experimento terminado', null, {timeout: 30000});
    await page.waitForFunction(() => !document.querySelector('#reproducir').disabled);
    assert.notEqual(await page.textContent('#distancia'), '—');
    await page.locator('#fotograma').evaluate(el => {
      el.value = '0';
      el.dispatchEvent(new Event('input', {bubbles: true}));
    });
    assert.match(await page.textContent('#posicion-reproduccion'), /Generación 0/);
    await page.click('#reproducir');
    await page.waitForFunction(() => Number(document.querySelector('#fotograma').value) > 0);
    await page.click('#reproducir');
    await page.click('#tab-comparacion');
    assert.equal(await page.locator('#filas-comparacion tr').count(), 3);
    const descarga = page.waitForEvent('download');
    await page.click('#descargar-comparacion');
    assert.equal((await descarga).suggestedFilename(), 'comparacion_total.csv');
    await page.click('#tab-archivos');
    assert.ok(await page.locator('.fila-archivo').count() > 3);
    const zip = page.waitForEvent('download');
    await page.click('#descargar-todo');
    assert.equal((await zip).suggestedFilename(), 'resultados.zip');
    await page.click('#tab-simulacion');
    await page.click('#tema');
    assert.ok(await page.locator('#traza-app').evaluate(el => el.classList.contains('tema-oscuro')));
    if (capturas) await page.screenshot({path: path.join(capturas, 'oscuro.png'), fullPage: true});
    await page.click('#tema');
    await page.selectOption('#escenario', 'gr229');
    await page.waitForFunction(() => document.querySelector('#contexto').textContent.includes('229 ciudades'));
    await page.setViewportSize({width: 390, height: 844});
    await page.waitForTimeout(200);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'La vista móvil tiene desbordamiento horizontal.');
    if (capturas) await page.screenshot({path: path.join(capturas, 'movil.png'), fullPage: true});
    await page.setViewportSize({width: 1440, height: 1100});
    await page.click('#crear');
    await page.fill('#ciudades-nuevas', '60');
    await page.click('#formulario-generar button[type=submit]');
    await page.waitForFunction(() => document.querySelector('#contexto').textContent.includes('60 ciudades'));
    await page.setInputFiles('#archivo', {name: 'cuadrado.csv', mimeType: 'text/csv', buffer: Buffer.from('ciudad,x,y\nA,0,0\nB,1,0\nC,1,1\nD,0,1\n')});
    await page.waitForFunction(() => document.querySelector('#contexto').textContent.includes('4 ciudades'));
    await page.selectOption('#escenario', 'eil101');
    await page.waitForFunction(() => document.querySelector('#contexto').textContent.includes('101 ciudades'));
    await page.fill('#iteraciones', '10000');
    await page.click('#ejecutar');
    await page.waitForSelector('#detener:not([hidden])');
    await page.click('#detener');
    await page.waitForFunction(() => document.querySelector('#estado').textContent === 'Ejecución detenida', null, {timeout: 30000});
    await page.selectOption('#metodo', 'ga');
    await page.locator('.ajustes summary').first().click();
    await page.fill('#cruce', '90');
    await page.click('#ejecutar');
    await page.waitForSelector('#error-formulario:not([hidden])');
    assert.match(await page.textContent('#error-formulario'), /sumar 1/);
    assert.deepEqual(errores, []);
    console.log('Navegador: ejecución real, reproducción, tabla, descargas, temas, móvil, carga, generación y cancelación aprobados.');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
