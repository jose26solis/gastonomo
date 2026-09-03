import { useState } from "react";
import type { Usuario } from "../types";
import { Ajustes } from "../pages/Ajustes";
import { Bancos } from "../pages/Bancos";
import { Categorias } from "../pages/Categorias";
import { ConectarCorreo } from "../pages/ConectarCorreo";
import { Presupuestos } from "../pages/Presupuestos";
import { Reportes } from "../pages/Reportes";
import { Resumen } from "../pages/Resumen";
import { Sinpe } from "../pages/Sinpe";
import { Header } from "./Header";
import { type Pantalla, Sidebar } from "./Sidebar";

const TITULOS: Record<Pantalla, [string, string]> = {
  resumen: ["Panorama", "Resumen de gastos"],
  categorias: ["Clasificación", "Categorías inteligentes"],
  presupuestos: ["Control", "Presupuestos y alertas"],
  reportes: ["Salida", "Reportes exportables"],
  conectar: ["Fuentes", "Conectar Gmail y Outlook"],
  bancos: ["Fuentes", "Bancos y cuentas"],
  sinpe: ["Fuentes", "Transferencias SINPE"],
  ajustes: ["Cuenta", "Ajustes"],
};

/**
 * Arma la aplicación: barra lateral, encabezado y el contenido de la
 * pantalla activa. La navegación es estado de React, no rutas de URL -como
 * en el prototipo original- porque no hay nada que un enlace externo
 * necesite apuntar aquí dentro (a diferencia de los callbacks de OAuth, que
 * sí son rutas reales en `App.tsx`).
 */
export function AppShell({
  usuario,
  onCerrarSesion,
  onActualizarUsuario,
}: {
  usuario: Usuario;
  onCerrarSesion: () => void;
  onActualizarUsuario: (usuario: Usuario) => void;
}) {
  const [pantalla, setPantalla] = useState<Pantalla>("resumen");
  const usuarioId = usuario.id;
  const [sincronizando, setSincronizando] = useState(false);
  const [lineaEstado, setLineaEstado] = useState("Sin buzones vinculados todavía");
  // Solo importa en pantallas angostas -en el escritorio el CSS ignora este
  // estado y el sidebar siempre está visible (ver `.sidebar` en index.css).
  const [menuAbierto, setMenuAbierto] = useState(false);

  const [kicker, titulo] = TITULOS[pantalla];

  return (
    <div className="app-shell">
      <Sidebar
        pantalla={pantalla}
        onNavegar={setPantalla}
        lineaEstado={lineaEstado}
        sincronizando={sincronizando}
        abierto={menuAbierto}
        onCerrar={() => setMenuAbierto(false)}
      />
      <div className="app-main">
        <Header
          kicker={kicker}
          titulo={titulo}
          usuario={usuario}
          onCerrarSesion={onCerrarSesion}
          onAbrirMenu={() => setMenuAbierto(true)}
        />
        <div className="app-content">
          {pantalla === "resumen" && (
            <Resumen
              usuarioId={usuarioId}
              onEstadoDeSincronizacion={(linea, activa) => {
                setLineaEstado(linea);
                setSincronizando(activa);
              }}
              onIrAConectar={() => setPantalla("conectar")}
            />
          )}
          {pantalla === "categorias" && (
            <Categorias usuarioId={usuarioId} onIrAConectar={() => setPantalla("conectar")} />
          )}
          {pantalla === "presupuestos" && (
            <Presupuestos usuarioId={usuarioId} onIrAConectar={() => setPantalla("conectar")} />
          )}
          {pantalla === "reportes" && (
            <Reportes usuarioId={usuarioId} onIrAConectar={() => setPantalla("conectar")} />
          )}
          {pantalla === "conectar" && <ConectarCorreo usuarioId={usuarioId} />}
          {pantalla === "bancos" && (
            <Bancos usuarioId={usuarioId} onIrAConectar={() => setPantalla("conectar")} />
          )}
          {pantalla === "sinpe" && (
            <Sinpe
              usuarioId={usuarioId}
              usuario={usuario}
              onActualizarUsuario={onActualizarUsuario}
              onIrAConectar={() => setPantalla("conectar")}
            />
          )}
          {pantalla === "ajustes" && (
            <Ajustes usuario={usuario} onActualizarUsuario={onActualizarUsuario} />
          )}
        </div>
      </div>
    </div>
  );
}
