# Mercado y Banca CATAN (Django)

Aplicativo web para gestionar una partida de CATAN con cuentas monetarias por jugador y mercado de recursos dinamico.

## Que implementa

- Alta de jugadores con cuenta individual y saldo inicial.
- Recursos comerciables con dinero:
   - Madera
   - Ladrillo
   - Trigo
   - Lana
   - Mineral
- Compra y venta de recursos por jugador.
- Ajuste de precios por recurso usando regresion lineal:
   - `Q estimada = a + bP`
   - `Delta Q = Q real - Q estimada`
   - `P nuevo = P actual + k * Delta Q`
   - Recalculo de `a` y `b` cada 5 turnos por recurso.
- Inventario por jugador y recurso.
- Transferencias de dinero entre jugadores con validaciones:
  - origen y destino deben ser diferentes
  - saldo suficiente en la cuenta origen
  - monto mayor que cero
- Dashboard con:
   - saldo por jugador
   - estado de precio por recurso
   - inventarios
   - operaciones de mercado recientes
   - transferencias recientes
- Historial del mercado filtrable por jugador, recurso y turnos.
- Seccion de reglas del sistema economico.

## Instalacion y ejecucion

1. Instalar dependencias:

   ```bash
   pip install -r requirements.txt
   ```

2. Migrar base de datos:

   ```bash
   python manage.py migrate
   ```

3. Ejecutar servidor:

   ```bash
   python manage.py runserver
   ```

4. Abrir en navegador:

   ```
   http://127.0.0.1:8000/
   ```

## Flujo recomendado de uso

1. Ir a **Jugadores** y crear cuentas con saldo inicial.
2. Configurar en la misma pantalla los precios base de recursos.
3. Ir a **Mercado** para registrar compras y ventas.
4. Usar **Transferir** para pagos directos entre jugadores.
5. Revisar **Panel** e **Historial** para analizar precios, inventarios y movimientos.

## Nota de alcance

El sistema integra dinero e intercambio de recursos, aplicando ajuste de precios por regresion lineal segun la dinamica de compra/venta.
