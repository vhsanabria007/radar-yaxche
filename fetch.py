# -*- coding: utf-8 -*-
"""
Baja las cotizaciones del Radar de Mercado y escribe datos.json.

POR QUÉ ESTO VIVE EN GITHUB Y NO EN LA NUBE DE CLAUDE
El contenedor donde corren las tareas programadas no alcanza ninguna
fuente de precios: Yahoo, CoinGecko, Stooq, Banxico y los proveedores de
divisas devuelven cero. Lo único que responde es GitHub. Así que la
descarga se hace aquí, en los servidores de GitHub, que sí tienen
internet abierto, y el resultado queda en un archivo que la tarea de la
nube lee por raw.githubusercontent.com.

Antes esto dependía de que la Mac de Víctor estuviera encendida a las
8:47. Ya no.

SALIDA
El formato es el que espera radar_actualiza.py, ni uno más:
  referencias  {TK: {precio, min52, max52, sello, desvio?}}
  series       {TK: {d: primer timestamp, h: último, c: [cierres]}}
  cripto       [[SÍMBOLO, id, precio, variación 24h], ...]
  sello_refs, sello_cripto
"""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

# El orden de la tabla lo decide el generador; el de la cinta de cripto
# es el que Víctor fijó y se respeta tal cual.
SIMBOLOS = ["EWY", "IBIT", "GDX", "GLD", "MCHI", "SMH", "INDA", "EEM",
            "EWT", "IXN", "QQQ", "HYG", "ACWI", "URTH", "SPY"]

CRIPTO = [("BTC", "bitcoin"), ("ETH", "ethereum"), ("XRP", "ripple"),
          ("BNB", "binancecoin"), ("SOL", "solana"), ("TRX", "tron"),
          ("SEI", "sei-network"), ("HYPE", "hyperliquid"), ("NEAR", "near"),
          ("HBAR", "hedera-hashgraph"), ("ONDO", "ondo-finance"),
          ("XLM", "stellar"), ("XPL", "plasma"), ("SUI", "sui"),
          ("UNI", "uniswap"), ("DAI", "dai"), ("TAO", "bittensor")]

MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul",
       "ago", "sep", "oct", "nov", "dic"]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def cdmx():
    return datetime.now(timezone(timedelta(hours=-6)))


def sello(fmt="%d %b"):
    """Mes en español y día sin cero a la izquierda: el generador compara
    «2 nov» con «02 nov» para decidir si la tabla está desfasada, y con el
    cero puesto la página se contradecía sola el mismo día en que todo se
    acababa de actualizar."""
    t = cdmx()
    s = t.strftime(fmt).replace(t.strftime("%b"), MES[t.month - 1])
    return s.lstrip("0") if s[0] == "0" else s


def baja(url, intentos=4):
    """Reintenta con espera creciente. Yahoo y CoinGecko limitan por
    ritmo, y un 429 aislado no debe tumbar la corrida entera."""
    ultimo = None
    for n in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # noqa: BLE001
            ultimo = e
            if n < intentos - 1:
                time.sleep(2 ** n * 1.5)
    raise ultimo


def una_referencia(tk):
    d = baja("https://query1.finance.yahoo.com/v8/finance/chart/"
             f"{tk}?range=1y&interval=1wk")
    res = d["chart"]["result"][0]
    meta, ts = res["meta"], res["timestamp"]
    cierres = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    if not cierres:
        raise ValueError(f"{tk}: la serie vino vacía")

    precio = meta["regularMarketPrice"]
    mn, mx = meta["fiftyTwoWeekLow"], meta["fiftyTwoWeekHigh"]
    for v, nom in ((precio, "precio"), (mn, "mínimo"), (mx, "máximo")):
        if not isinstance(v, (int, float)) or v <= 0:
            raise ValueError(f"{tk}: {nom} inservible ({v!r})")
    if mn >= mx:
        raise ValueError(f"{tk}: el mínimo no puede ser mayor que el máximo")

    # Control de sanidad: si el precio de meta y el último cierre semanal
    # se separan más de 2%, una de las dos lecturas viene rezagada y la
    # fila se marca. Marcarlo es mejor que elegir en silencio.
    desvio = abs(precio / cierres[-1] - 1) * 100
    ref = {"precio": round(precio, 2), "min52": round(mn, 2),
           "max52": round(mx, 2), "sello": sello() + " cierre"}
    if desvio > 2:
        ref["desvio"] = round(desvio, 1)
    serie = {"d": ts[0], "h": ts[-1], "c": [round(c, 2) for c in cierres]}
    return ref, serie


def referencias(previo):
    refs, series, fallos = {}, {}, []
    for tk in SIMBOLOS:
        try:
            refs[tk], series[tk] = una_referencia(tk)
            print(f"  {tk:5} {refs[tk]['precio']:>10,.2f}"
                  f"   {len(series[tk]['c']):>3} semanas"
                  + ("   ⚠ desvío" if "desvio" in refs[tk] else ""))
        except Exception as e:                      # noqa: BLE001
            # Se arrastra el valor de la corrida anterior CON SU SELLO
            # ORIGINAL. Omitirlo sin más no sirve: el generador rehace
            # la tabla entera con lo que reciba, así que un símbolo que
            # falta desaparece de la página —se comprobó— y la fila se
            # pierde sin que nadie lo note. Arrastrarlo con su fecha
            # vieja mantiene la tabla completa y deja a la vista que ese
            # renglón no es de hoy.
            fallos.append(f"{tk} ({type(e).__name__})")
            print(f"  {tk:5} FALLÓ · {e}", file=sys.stderr)
            if tk in previo.get("referencias", {}):
                refs[tk] = previo["referencias"][tk]
                if tk in previo.get("series", {}):
                    series[tk] = previo["series"][tk]
                print(f"  {tk:5} se arrastra del {refs[tk]['sello']}",
                      file=sys.stderr)
        time.sleep(0.4)
    return refs, series, fallos


def criptos():
    ids = ",".join(i for _, i in CRIPTO)
    d = baja("https://api.coingecko.com/api/v3/coins/markets"
             f"?vs_currency=usd&price_change_percentage=24h&ids={ids}")
    por_id = {x["id"]: x for x in d}
    fila, fallos = [], []
    for sim, cid in CRIPTO:
        x = por_id.get(cid)
        if not x or x.get("current_price") is None:
            fallos.append(sim)
            continue
        fila.append([sim, cid, x["current_price"],
                     round(x.get("price_change_percentage_24h") or 0.0, 2)])
    print(f"  cripto: {len(fila)} de {len(CRIPTO)}")
    return fila, fallos


def main():
    print(f"Radar · descarga {sello('%d %b %H:%M')} CDMX")
    # La corrida anterior sirve de red: si hoy falla un símbolo, se
    # arrastra su último valor bueno en lugar de borrarlo de la tabla.
    try:
        previo = json.load(open("datos.json", encoding="utf-8"))
    except Exception:                               # noqa: BLE001
        previo = {}
    refs, series, f1 = referencias(previo)
    try:
        cripto, f2 = criptos()
    except Exception as e:                          # noqa: BLE001
        print(f"  cripto: FALLÓ · {e}", file=sys.stderr)
        cripto, f2 = [], ["todos"]

    # Una corrida que trae menos de dos tercios de la tabla no se publica:
    # un radar a medias describe un mercado que no existe.
    frescas = len(SIMBOLOS) - len(f1)
    if frescas < len(SIMBOLOS) * 2 // 3:
        print(f"\nSólo {frescas} de {len(SIMBOLOS)} referencias se bajaron hoy. "
              "No se escribe el archivo: más de un tercio arrastrado deja de "
              "ser un radar de hoy.", file=sys.stderr)
        return 1

    salida = {"referencias": refs, "series": series,
              "sello_refs": sello("%d %b %H:%M")}
    if cripto:
        salida["cripto"] = cripto
        salida["sello_cripto"] = sello("%d %b %H:%M") + " CDMX"
    salida["_meta"] = {"generado": cdmx().isoformat(timespec="seconds"),
                       "fallos": f1 + [f"cripto:{x}" for x in f2]}

    with open("datos.json", "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"\ndatos.json · {len(refs)} referencias ({frescas} de hoy) · "
          f"{len(cripto)} criptos"
          + (f" · arrastradas: {', '.join(f1)}" if f1 else "")
          + (f" · cripto sin dato: {', '.join(f2)}" if f2 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
