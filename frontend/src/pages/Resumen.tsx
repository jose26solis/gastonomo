import { ArrowDownRight, ArrowUpRight, EnvelopeSimple, Minus, Storefront } from "@phosphor-icons/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { formatearFechaCorta, formatearMes, formatearMonto } from "../lib/formato";
import type {
  ComprobanteConFuente,
  CuentaCorreo,
  ResumenFinancieroConFuente,
  ResumenMensual,
  TipoDeCambio,
} from "../types";

const ACENTOS = ["#b5abfc", "#968ae0", "#796cbf", "#5d5294", "#423a6a", "#7972a9"];

const NOMBRE_PROVEEDOR: Record<string, string> = { OUTLOOK: "Outlook", GMAIL: "Gmail" };

function esSumable(c: ComprobanteConFuente): c is ComprobanteConFuente & {
  fecha: string;
  moneda: string;
  monto: string;
} {
  return c.es_compra && c.es_confiable && c.monto != null && c.fecha != null && c.moneda != null;
}

/** Un mismo mes puede traer una entrada por moneda -las monedas nunca se
 * suman entre sí. Dentro de un período, prefiere colones (la moneda del
 * resto de la app: los presupuestos, por ejemplo, solo se crean en CRC) y
 * cae a la que haya si ese mes no tuvo ningún movimiento en colones.
 */
function entradaPreferidaDelPeriodo(
  entradas: ResumenMensual[],
  anio: number,
  mes: number,
): ResumenMensual {
  const delPeriodo = entradas.filter((e) => e.anio === anio && e.mes === mes);
  return delPeriodo.find((e) => e.moneda === "CRC") ?? delPeriodo[0];
}

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

export function Resumen({
  usuarioId,
  onEstadoDeSincronizacion,
  onIrAConectar,
}: {
  usuarioId: number;
  onEstadoDeSincronizacion: (linea: string, activa: boolean) => void;
  onIrAConectar: () => void;
}) {
  const [cuentas, setCuentas] = useState<CuentaCorreo[] | null>(null);
  const [resumen, setResumen] = useState<ResumenFinancieroConFuente | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // null = "el más reciente" (comportamiento por defecto); se llena cuando
  // el titular elige explícitamente un mes anterior en el selector.
  const [periodoElegido, setPeriodoElegido] = useState<{ anio: number; mes: number } | null>(null);
  const [tipoDeCambio, setTipoDeCambio] = useState<TipoDeCambio | null>(null);
  // "" = sin convertir, cada movimiento en su moneda (el comportamiento
  // honesto por defecto). Con "CRC" o "USD", el backend pasa todo a esa
  // moneda para poder dar un balance único.
  const [monedaUnica, setMonedaUnica] = useState<"" | "CRC" | "USD">("");

  useEffect(() => {
    let cancelado = false;
    setCuentas(null);
    setResumen(null);
    setError(null);
    api
      .listarCuentas(usuarioId)
      .then((c) => {
        if (!cancelado) setCuentas(c);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(mensajeDeError(e));
      });
    return () => {
      cancelado = true;
    };
  }, [usuarioId]);

  // Todas las cuentas activas, no solo "la" activa: con Outlook y Gmail
  // vinculados a la vez, el resumen combina el historial de ambas -antes
  // esta pantalla elegía arbitrariamente la primera que encontrara, y el
  // resto del historial parecía desaparecer aunque siguiera vinculado.
  const cuentasActivas = cuentas?.filter((c) => c.estado === "ACTIVA") ?? [];
  const hayCuentaActiva = cuentasActivas.length > 0;
  // Clave estable del conjunto de cuentas activas: cambia si se vincula,
  // desvincula o reconecta una cuenta, y solo entonces -no en cada
  // re-render- hay que volver a pedir el resumen combinado.
  const claveCuentasActivas = cuentasActivas
    .map((c) => c.id)
    .sort((a, b) => a - b)
    .join(",");

  useEffect(() => {
    if (cuentas === null) return;
    if (!hayCuentaActiva) {
      onEstadoDeSincronizacion("Sin buzones vinculados todavía", false);
      return;
    }
    const direcciones = cuentasActivas.map((c) => c.direccion).join(" y ");
    onEstadoDeSincronizacion(`${direcciones} · leyendo comprobantes…`, true);
    let cancelado = false;
    setCargando(true);
    api
      .resumenFinanciero(usuarioId, monedaUnica || undefined)
      .then((r) => {
        if (cancelado) return;
        setResumen(r);
        onEstadoDeSincronizacion(
          `${direcciones} · ${r.comprobantes.length} comprobantes leídos`,
          false,
        );
      })
      .catch((e: unknown) => {
        if (cancelado) return;
        setError(mensajeDeError(e));
        onEstadoDeSincronizacion(`${direcciones} · error al leer`, false);
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });
    return () => {
      cancelado = true;
    };
    // onEstadoDeSincronizacion es un canal de salida, no una dependencia de datos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cuentas === null, claveCuentasActivas, usuarioId, monedaUnica]);

  const datos = useMemo(() => {
    if (!resumen || resumen.por_mes.length === 0) return null;

    // resumen.por_mes viene ordenado por (año, mes, moneda) descendente, no
    // por período: un mes con movimientos en dos monedas ocupa dos filas
    // seguidas. Los períodos distintos, del más al menos reciente:
    const periodos: { anio: number; mes: number }[] = [];
    for (const entrada of resumen.por_mes) {
      if (!periodos.some((p) => p.anio === entrada.anio && p.mes === entrada.mes)) {
        periodos.push({ anio: entrada.anio, mes: entrada.mes });
      }
    }

    // El período que se muestra es el elegido en el selector, si sigue
    // existiendo en los datos actuales -si no (una cuenta nueva, por
    // ejemplo), cae al más reciente.
    const indiceElegido = periodoElegido
      ? periodos.findIndex((p) => p.anio === periodoElegido.anio && p.mes === periodoElegido.mes)
      : -1;
    const periodoActual = indiceElegido >= 0 ? periodos[indiceElegido] : periodos[0];
    const periodoAnterior = periodos[(indiceElegido >= 0 ? indiceElegido : 0) + 1] ?? null;
    const mesActual = entradaPreferidaDelPeriodo(
      resumen.por_mes,
      periodoActual.anio,
      periodoActual.mes,
    );
    const mesAnterior = periodoAnterior
      ? entradaPreferidaDelPeriodo(resumen.por_mes, periodoAnterior.anio, periodoAnterior.mes)
      : null;
    // Otras monedas que también tuvieron movimiento este mes: la tarjeta de
    // KPI solo puede mostrar un total en una moneda a la vez, así que esto
    // se muestra aparte para que esa plata no desaparezca en silencio.
    const otrasMonedasDelMes = resumen.por_mes.filter(
      (e) => e.anio === periodoActual.anio && e.mes === periodoActual.mes && e !== mesActual,
    );
    const prefijoMes = `${mesActual.anio}-${String(mesActual.mes).padStart(2, "0")}`;

    // Todo lo del mes, sumable, sin importar la moneda -para la lista de
    // movimientos: un tracker de gastos no debería esconder una compra real
    // solo porque quedó en una moneda distinta a la del resto del mes.
    const comprobantesDelMesTodasLasMonedas = resumen.comprobantes
      .filter(esSumable)
      .filter((c) => c.fecha.startsWith(prefijoMes));

    // Lo mismo, pero solo en la moneda que se está totalizando arriba: los
    // gráficos y KPIs sí necesitan una sola moneda para poder sumar de forma
    // honesta (por comercio, por día, promedio...).
    const comprobantesDelMes = comprobantesDelMesTodasLasMonedas.filter(
      (c) => c.moneda === mesActual.moneda,
    );

    const totalMes = Number(mesActual.total);
    const cantidadMes = mesActual.cantidad_transacciones;
    const promedioMes = cantidadMes > 0 ? totalMes / cantidadMes : 0;

    // Con muy pocas transacciones el mes anterior no es una base seria para
    // comparar -un mes con 2 movimientos puede dar un "+8000%" que es
    // aritméticamente correcto y comunica mal. Se prefiere admitir que no
    // hay suficiente historial en vez de mostrar un porcentaje absurdo.
    const MIN_TRANSACCIONES_PARA_COMPARAR = 5;
    const mesAnteriorComparable =
      mesAnterior && mesAnterior.cantidad_transacciones >= MIN_TRANSACCIONES_PARA_COMPARAR
        ? mesAnterior
        : null;
    const deltaPct = mesAnteriorComparable
      ? (totalMes / Number(mesAnteriorComparable.total) - 1) * 100
      : null;

    const porComercio = new Map<string, number>();
    for (const c of comprobantesDelMes) {
      const nombre = c.comercio ?? "Sin identificar";
      porComercio.set(nombre, (porComercio.get(nombre) ?? 0) + Number(c.monto));
    }
    const comerciosOrdenados = [...porComercio.entries()].sort((a, b) => b[1] - a[1]);
    const topComercios = comerciosOrdenados.slice(0, 6);
    const comercioFrecuente = topComercios[0]?.[0] ?? "—";

    const diasEnMes = new Date(mesActual.anio, mesActual.mes, 0).getDate();
    const primerDiaSemana = new Date(mesActual.anio, mesActual.mes - 1, 1).getDay();
    const porDia = new Array<number>(diasEnMes + 1).fill(0);
    for (const c of comprobantesDelMes) {
      const dia = new Date(c.fecha).getDate();
      porDia[dia] += Number(c.monto);
    }

    // Del período que se está viendo, no de toda la bandeja -si no, elegir
    // un mes anterior en el selector de arriba seguiría mostrando lo último
    // de hoy acá abajo, que es justo lo contrario de lo que se pidió ver.
    // Todas las monedas del mes, a propósito (ver comprobantesDelMesTodasLasMonedas).
    const movimientosRecientes = [...comprobantesDelMesTodasLasMonedas]
      .sort((a, b) => b.fecha.localeCompare(a.fecha))
      .slice(0, 8);

    // Un punto por período, no por fila: dos monedas del mismo mes no pueden
    // graficarse en una sola línea (las escalas no son comparables), así que
    // la tendencia usa la misma moneda preferida que el resto del panel.
    const tendencia = periodos
      .map((p) => entradaPreferidaDelPeriodo(resumen.por_mes, p.anio, p.mes))
      .reverse();

    return {
      mesActual,
      mesAnterior,
      mesAnteriorComparable,
      otrasMonedasDelMes,
      totalMes,
      cantidadMes,
      promedioMes,
      deltaPct,
      topComercios,
      comercioFrecuente,
      diasEnMes,
      primerDiaSemana,
      porDia,
      movimientosRecientes,
      tendencia,
      periodos,
      hayMovimientosEnUsd: comprobantesDelMesTodasLasMonedas.some((c) => c.moneda === "USD"),
      esMesActual: periodoActual.anio === periodos[0].anio && periodoActual.mes === periodos[0].mes,
    };
  }, [resumen, periodoElegido]);

  const intentoTipoDeCambio = useRef(false);
  useEffect(() => {
    const necesitaConversion = datos?.hayMovimientosEnUsd ?? false;
    if (!necesitaConversion || intentoTipoDeCambio.current) return;
    intentoTipoDeCambio.current = true;
    api
      .tipoDeCambio()
      .then(setTipoDeCambio)
      .catch(() => {
        // El Banco Central no está configurado o no respondió: la
        // conversión es un extra, no algo que deba impedir ver el resto
        // del panel -se sigue mostrando el monto en dólares, sin más.
      });
  }, [datos]);

  if (error) {
    return <p className="mensaje-error">{error}</p>;
  }

  if (cuentas === null) {
    return <p className="vacio">Cargando…</p>;
  }

  if (!hayCuentaActiva) {
    return (
      <div className="card stack" style={{ maxWidth: 480 }}>
        <div className="section-title">Todavía no hay ningún buzón vinculado</div>
        <p className="section-subtitle" style={{ margin: 0 }}>
          Vinculá Outlook o Gmail para ver acá tus gastos reales, leídos y sumados desde tus
          comprobantes de BAC.
        </p>
        <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} onClick={onIrAConectar}>
          <EnvelopeSimple size={14} /> Conectar correo
        </button>
      </div>
    );
  }

  if (cargando || !datos) {
    return (
      <div className="stack">
        <p className="vacio">
          Leyendo comprobantes de {cuentasActivas.map((c) => c.direccion).join(" y ")}… puede tardar
          varios segundos, cada uno es una petición aparte al proveedor.
        </p>
      </div>
    );
  }

  const periodoActualElegido = { anio: datos.mesActual.anio, mes: datos.mesActual.mes };

  const estiloSelect = {
    padding: "6px 8px",
    background: "var(--color-surface-2)",
    border: "1px solid var(--color-border)",
    borderRadius: 8,
    color: "var(--color-text)",
    fontSize: 11.5,
  };

  return (
    <div className="stack">
      <div className="card" style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        {datos.periodos.length > 1 && (
          <>
            <span style={{ fontSize: 11.5, color: "var(--color-text-dim)" }}>Período</span>
            <select
              value={`${periodoActualElegido.anio}-${periodoActualElegido.mes}`}
              onChange={(e) => {
                const [anio, mes] = e.target.value.split("-").map(Number);
                setPeriodoElegido({ anio, mes });
              }}
              style={estiloSelect}
            >
              {datos.periodos.map((p) => (
                <option key={`${p.anio}-${p.mes}`} value={`${p.anio}-${p.mes}`}>
                  {formatearMes(p.anio, p.mes)}
                </option>
              ))}
            </select>
          </>
        )}
        <span style={{ fontSize: 11.5, color: "var(--color-text-dim)" }}>Moneda</span>
        <select
          value={monedaUnica}
          onChange={(e) => setMonedaUnica(e.target.value as "" | "CRC" | "USD")}
          style={estiloSelect}
        >
          <option value="">Cada una en la suya</option>
          <option value="CRC">Todo en colones (₡)</option>
          <option value="USD">Todo en dólares ($)</option>
        </select>
        {resumen?.conversion && (
          <span style={{ fontSize: 10.5, color: "var(--color-text-dim)", flex: 1, minWidth: 220 }}>
            Convertido a ₡{resumen.conversion.venta} por dólar, tipo de cambio de venta del{" "}
            {resumen.conversion.fecha} (Banco Central). Los meses anteriores se convierten con esa
            misma tasa, no con la de su fecha.
          </span>
        )}
      </div>

      <div className="grid grid-4">
        <KpiCard
          label={datos.esMesActual ? "Gasto de este mes" : `Gasto de ${formatearMes(datos.mesActual.anio, datos.mesActual.mes)}`}
          valor={formatearMonto(datos.totalMes, datos.mesActual.moneda)}
          delta={
            datos.deltaPct === null
              ? datos.mesAnterior
                ? `${formatearMes(datos.mesAnterior.anio, datos.mesAnterior.mes)} tuvo muy pocos movimientos para comparar`
                : "Sin mes anterior para comparar"
              : `${datos.deltaPct >= 0 ? "+" : ""}${datos.deltaPct.toFixed(0)}% vs. ${formatearMes(
                  datos.mesAnteriorComparable!.anio,
                  datos.mesAnteriorComparable!.mes,
                )}`
          }
          tendenciaDelta={datos.deltaPct === null ? "neutral" : datos.deltaPct > 0 ? "arriba" : "abajo"}
        />
        <KpiCard label="Transacciones" valor={String(datos.cantidadMes)} delta={formatearMes(datos.mesActual.anio, datos.mesActual.mes)} tendenciaDelta="neutral" />
        <KpiCard
          label="Promedio por compra"
          valor={formatearMonto(datos.promedioMes, datos.mesActual.moneda)}
          delta={datos.esMesActual ? "Este mes" : formatearMes(datos.mesActual.anio, datos.mesActual.mes)}
          tendenciaDelta="neutral"
        />
        <KpiCard label="Comercio más frecuente" valor={datos.comercioFrecuente} delta="Por monto acumulado" tendenciaDelta="neutral" />
      </div>

      {datos.otrasMonedasDelMes.length > 0 && (
        <p className="section-subtitle" style={{ margin: 0 }}>
          {formatearMes(datos.mesActual.anio, datos.mesActual.mes)} también tuvo movimientos en{" "}
          {datos.otrasMonedasDelMes
            .map((m) => {
              const texto = formatearMonto(Number(m.total), m.moneda);
              // Tipo "venta": es la referencia de cuántos colones costaría
              // comprar esos dólares -la lectura natural para "cuánto me
              // costó esto en colones" en un tracker de gastos.
              if (m.moneda === "USD" && tipoDeCambio) {
                const equivalente = Number(m.total) * Number(tipoDeCambio.venta);
                return `${texto} (≈ ${formatearMonto(equivalente, "CRC")})`;
              }
              return texto;
            })
            .join(" y ")}
          {" "}
          -no se suma acá arriba para no mezclar monedas, pero sí cuenta en Movimientos recientes.
          {tipoDeCambio && (
            <>
              {" "}
              Conversión de referencia: ₡{tipoDeCambio.venta} por dólar, tipo de cambio de venta del{" "}
              {tipoDeCambio.fecha} según el Banco Central.
            </>
          )}
        </p>
      )}

      <div className="grid" style={{ gridTemplateColumns: "1.35fr 1fr" }}>
        <TendenciaMensual tendencia={datos.tendencia} />
        <PorComercio topComercios={datos.topComercios} totalMes={datos.totalMes} moneda={datos.mesActual.moneda} />
      </div>

      <div className="grid grid-3">
        <TopComerciosBarras topComercios={datos.topComercios} moneda={datos.mesActual.moneda} />
        <CalendarioDeGastos
          anio={datos.mesActual.anio}
          mes={datos.mesActual.mes}
          diasEnMes={datos.diasEnMes}
          primerDiaSemana={datos.primerDiaSemana}
          porDia={datos.porDia}
          moneda={datos.mesActual.moneda}
        />
        <ResumenCuenta cuentas={cuentasActivas} comprobantes={resumen?.comprobantes ?? []} />
      </div>

      {/* Con el panel en una sola moneda, el equivalente suelto sobra: lo que
          hace falta ver al lado de cada monto convertido es el original, y de
          eso se encarga `monto_original`. */}
      <MovimientosRecientes
        movimientos={datos.movimientosRecientes}
        tipoDeCambio={monedaUnica ? null : tipoDeCambio}
      />
    </div>
  );
}

function KpiCard({
  label,
  valor,
  delta,
  tendenciaDelta,
}: {
  label: string;
  valor: string;
  delta: string;
  tendenciaDelta: "arriba" | "abajo" | "neutral";
}) {
  const Icono = tendenciaDelta === "arriba" ? ArrowUpRight : tendenciaDelta === "abajo" ? ArrowDownRight : Minus;
  return (
    <div className="card stack" style={{ gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--color-text-muted)" }}>
        {label}
      </div>
      <div style={{ fontSize: 25, fontWeight: 500, letterSpacing: "-0.02em" }}>{valor}</div>
      <div style={{ fontSize: 11, color: "var(--color-text-dim)", display: "flex", alignItems: "center", gap: 4 }}>
        <Icono size={11} />
        {delta}
      </div>
    </div>
  );
}

function TendenciaMensual({ tendencia }: { tendencia: ResumenMensual[] }) {
  const ancho = 560;
  const alto = 180;
  const valores = tendencia.map((t) => Number(t.total));
  const maximo = Math.max(...valores, 1) * 1.12;
  const puntos = tendencia.map((t, i) => ({
    x: tendencia.length > 1 ? 10 + (i * (ancho - 20)) / (tendencia.length - 1) : ancho / 2,
    y: alto - 10 - (Number(t.total) / maximo) * (alto - 30),
    etiqueta: formatearMes(t.anio, t.mes),
  }));
  const linea = puntos.map((p, i) => (i ? "L" : "M") + p.x.toFixed(1) + " " + p.y.toFixed(1)).join(" ");
  const area = puntos.length > 1 ? `${linea} L${ancho - 10} ${alto - 2} L10 ${alto - 2} Z` : "";

  return (
    <section className="card">
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 17 }}>
        <div>
          <div className="section-title">Tendencia mensual</div>
          <div className="section-subtitle">Gasto total de BAC, por mes</div>
        </div>
      </div>
      {tendencia.length === 0 ? (
        <p className="vacio">Todavía no hay suficientes meses para trazar una tendencia.</p>
      ) : (
        <>
          <svg viewBox={`0 0 ${ancho} ${alto}`} preserveAspectRatio="none" style={{ width: "100%", height: 180, display: "block" }}>
            <defs>
              <linearGradient id="tendenciaArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#968ae0" stopOpacity={0.32} />
                <stop offset="100%" stopColor="#968ae0" stopOpacity={0} />
              </linearGradient>
            </defs>
            {[30, 66, 102, 138].map((y) => (
              <line key={y} x1={0} x2={ancho} y1={y} y2={y} stroke="#292b31" strokeWidth={1} />
            ))}
            {area && <path d={area} fill="url(#tendenciaArea)" />}
            <path d={linea} fill="none" stroke="#968ae0" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            {puntos.map((p) => (
              <circle key={p.etiqueta} cx={p.x} cy={p.y} r={3} fill="#161826" stroke="#b5abfc" strokeWidth={2} />
            ))}
          </svg>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
            {puntos.map((p) => (
              <div key={p.etiqueta} style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
                {p.etiqueta}
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function PorComercio({
  topComercios,
  totalMes,
  moneda,
}: {
  topComercios: [string, number][];
  totalMes: number;
  moneda: string;
}) {
  const circunferencia = 2 * Math.PI * 58;
  // Las fracciones se calculan primero, sin efectos secundarios; el offset de
  // cada segmento es la suma de arco de los segmentos anteriores. Nada de un
  // acumulador `let` mutado dentro del map.
  const fracciones = topComercios.map(([, monto]) => (totalMes > 0 ? monto / totalMes : 0));
  const segmentos = topComercios.map(([nombre, monto], i) => {
    const fraccion = fracciones[i];
    const largo = circunferencia * fraccion - 2;
    const arcoPrevio = fracciones.slice(0, i).reduce((suma, f) => suma + f, 0) * circunferencia;
    return {
      nombre,
      monto,
      color: ACENTOS[i % ACENTOS.length],
      dash: `${Math.max(largo, 0)} ${circunferencia - Math.max(largo, 0)}`,
      offset: -arcoPrevio,
      pct: Math.round(fraccion * 100) + "%",
    };
  });

  return (
    <section className="card stack">
      <div>
        <div className="section-title">Por comercio</div>
        <div className="section-subtitle">Este mes, extraído de tus comprobantes reales de BAC</div>
      </div>
      {topComercios.length === 0 ? (
        <p className="vacio">Sin compras este mes.</p>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 17 }}>
          <div style={{ position: "relative", width: 150, height: 150, flex: "0 0 150px" }}>
            <svg viewBox="0 0 150 150" style={{ width: 150, height: 150, transform: "rotate(-90deg)" }}>
              {segmentos.map((s) => (
                <circle key={s.nombre} cx={75} cy={75} r={58} fill="none" stroke={s.color} strokeWidth={17} strokeDasharray={s.dash} strokeDashoffset={s.offset} />
              ))}
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <div style={{ fontSize: 16, fontWeight: 500 }}>{formatearMonto(totalMes, moneda)}</div>
              <div style={{ fontSize: 10, color: "var(--color-text-dim)" }}>este mes</div>
            </div>
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 7, minWidth: 0 }}>
            {segmentos.map((s) => (
              <div key={s.nombre} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 11.5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, flex: "0 0 8px", background: s.color }} />
                <span style={{ flex: 1, color: "var(--color-text-bright-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {s.nombre}
                </span>
                <span style={{ color: "var(--color-text-muted)" }}>{s.pct}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function TopComerciosBarras({ topComercios, moneda }: { topComercios: [string, number][]; moneda: string }) {
  const max = topComercios[0]?.[1] ?? 1;
  return (
    <section className="card stack">
      <div>
        <div className="section-title">Top comercios</div>
        <div className="section-subtitle">Por monto acumulado este mes</div>
      </div>
      {topComercios.length === 0 ? (
        <p className="vacio">Sin compras este mes.</p>
      ) : (
        <div className="stack" style={{ gap: 11 }}>
          {topComercios.map(([nombre, monto]) => (
            <div key={nombre} className="stack" style={{ gap: 5 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5 }}>
                <span style={{ color: "var(--color-text-bright-muted)" }}>{nombre}</span>
                <span style={{ color: "var(--color-text-muted)" }}>{formatearMonto(monto, moneda)}</span>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ background: "var(--color-accent-400)", width: `${Math.round((monto / max) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function CalendarioDeGastos({
  anio,
  mes,
  diasEnMes,
  primerDiaSemana,
  porDia,
  moneda,
}: {
  anio: number;
  mes: number;
  diasEnMes: number;
  primerDiaSemana: number;
  porDia: number[];
  moneda: string;
}) {
  const maxDia = Math.max(...porDia, 1);
  const heatFor = (v: number) => {
    if (!v) return "#232532";
    const r = v / maxDia;
    if (r < 0.2) return "#2b2741";
    if (r < 0.4) return "#423a6a";
    if (r < 0.62) return "#5d5294";
    if (r < 0.85) return "#796cbf";
    return "#b5abfc";
  };
  const diaPico = porDia.indexOf(maxDia);

  return (
    <section className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <div className="section-title">Calendario de gastos</div>
          <div className="section-subtitle">{formatearMes(anio, mes)}</div>
        </div>
        {maxDia > 1 && (
          <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
            Pico: {diaPico} · {formatearMonto(maxDia, moneda)}
          </div>
        )}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, marginTop: 14 }}>
        {["D", "L", "K", "M", "J", "V", "S"].map((d) => (
          <div key={d} style={{ fontSize: 9.5, color: "var(--color-text-dimmer)", textAlign: "center" }}>
            {d}
          </div>
        ))}
        {Array.from({ length: primerDiaSemana }).map((_, i) => (
          <div key={`vacio-${i}`} />
        ))}
        {Array.from({ length: diasEnMes }, (_, i) => i + 1).map((dia) => (
          <div
            key={dia}
            title={`${dia} · ${formatearMonto(porDia[dia], moneda)}`}
            style={{
              aspectRatio: "1",
              borderRadius: 3,
              display: "grid",
              placeItems: "center",
              fontSize: 9.5,
              color: porDia[dia] / maxDia > 0.6 ? "#161826" : "var(--color-text-dim)",
              background: heatFor(porDia[dia]),
            }}
          >
            {dia}
          </div>
        ))}
      </div>
    </section>
  );
}

function ResumenCuenta({
  cuentas,
  comprobantes,
}: {
  cuentas: CuentaCorreo[];
  comprobantes: ComprobanteConFuente[];
}) {
  // Cuántos comprobantes aportó cada buzón. Una cuenta vinculada que aparece
  // en 0 es información útil, no un error: significa que a esa dirección BAC
  // no le está mandando notificaciones -que es lo que pasa si el banco tiene
  // registrada la otra.
  const porCuenta = cuentas.map((cuenta) => ({
    cuenta,
    total: comprobantes.filter((c) => c.cuenta_correo_id === cuenta.id).length,
  }));

  return (
    <section className="card stack">
      <div className="section-title">Fuente de estos datos</div>
      <div className="stack" style={{ gap: 7 }}>
        {porCuenta.map(({ cuenta, total }) => (
          <div key={cuenta.id} className="stack" style={{ gap: 2 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
              <span style={{ fontSize: 11.5, color: "var(--color-text-bright-muted)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {cuenta.direccion}
              </span>
              <EtiquetaFuente proveedor={cuenta.proveedor} />
            </div>
            <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
              {total === 0
                ? "Sin comprobantes de BAC en esta bandeja"
                : `${total} comprobantes de BAC leídos`}
            </div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: "var(--color-text-dim)", lineHeight: 1.6 }}>
        Solo se cuentan los comprobantes que el parser entendió con confianza. Transferencias u
        otros formatos que todavía no se reconocen quedan fuera de estos totales, a propósito.
      </div>
    </section>
  );
}

/** Pastilla chica que dice de qué buzón salió un movimiento. */
function EtiquetaFuente({ proveedor }: { proveedor: string }) {
  return (
    <span
      style={{
        fontSize: 9.5,
        padding: "1px 6px",
        borderRadius: 999,
        background: "var(--color-surface-2)",
        color: "var(--color-text-muted)",
        whiteSpace: "nowrap",
      }}
    >
      {NOMBRE_PROVEEDOR[proveedor] ?? proveedor}
    </span>
  );
}

function MovimientosRecientes({
  movimientos,
  tipoDeCambio,
}: {
  movimientos: ComprobanteConFuente[];
  tipoDeCambio: TipoDeCambio | null;
}) {
  return (
    <section className="card card--tight">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: 17 }}>
        <div>
          <div className="section-title">Movimientos recientes</div>
          <div className="section-subtitle">
            De todas tus bandejas vinculadas, en cualquier moneda
          </div>
        </div>
      </div>
      {movimientos.length === 0 ? (
        <p className="vacio" style={{ padding: "0 17px 17px" }}>
          Sin movimientos reconocidos todavía.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {movimientos.map((m, i) => {
            // Nunca se muestra solo el número convertido: o se ve el monto
            // real con su equivalente al lado, o -si el panel está en una
            // sola moneda- se ve el convertido con el original debajo. El
            // dato de lo que el banco cobró de verdad no desaparece.
            const referencia = m.moneda_original
              ? `${formatearMonto(-Number(m.monto_original), m.moneda_original)} reales`
              : m.moneda === "USD" && tipoDeCambio
                ? `≈ ${formatearMonto(-Number(m.monto) * Number(tipoDeCambio.venta), "CRC")}`
                : null;
            return (
              <div
                key={`${m.autorizacion}-${i}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "30px 1.6fr 1fr 130px",
                  alignItems: "center",
                  gap: 11,
                  padding: "11px 17px",
                  borderTop: "1px solid var(--color-surface-2)",
                }}
              >
                <span
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: 8,
                    background: "var(--color-surface-2)",
                    display: "grid",
                    placeItems: "center",
                    color: "var(--color-accent-200)",
                  }}
                >
                  <Storefront size={14} />
                </span>
                <span style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                  <span style={{ fontSize: 12.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {m.comercio ?? "Sin identificar"}
                  </span>
                  <span style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
                    {formatearFechaCorta(m.fecha!)} · {m.marca_tarjeta} ••{m.ultimos_cuatro}
                  </span>
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
                  <EtiquetaFuente proveedor={m.proveedor} />
                  <span style={{ fontSize: 10.5, color: "var(--color-text-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {m.ciudad ?? ""}
                  </span>
                </span>
                <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 1 }}>
                  <span style={{ fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
                    {formatearMonto(-Number(m.monto), m.moneda!)}
                  </span>
                  {referencia && (
                    <span style={{ fontSize: 10, color: "var(--color-text-dim)", fontVariantNumeric: "tabular-nums" }}>
                      {referencia}
                    </span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
